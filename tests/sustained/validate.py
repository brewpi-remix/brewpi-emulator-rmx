# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Independent completeness gates for original sustained qualification evidence."""
import hashlib
import json
import math
from pathlib import Path
import statistics
from measurement import DURATIONS,validate_resources

KINDS={'clock','faults','lifecycle','normal','accelerated'}
FAULTS={'corrupt store','corrupt checkpoint','checkpoint/store mismatch','scenario/output direct','scenario/output hardlink','scenario/output symlink','fsync failure before replacement','fsync failure after replacement'}


def finite(value):
    return type(value) in [int,float] and math.isfinite(value)


def summary(result,acceptance,architecture,scope='full'):
    if scope not in ['full','accelerated-only']:raise ValueError('unknown qualification scope')
    required=KINDS if scope=='full' else KINDS-{'normal'}
    if result.get('status')!='passed' or result.get('qualification') is not acceptance or result.get('r3_complete') is not (acceptance and scope=='full') or result.get('scope','full')!=scope or result.get('architecture')!=architecture:
        raise ValueError('incomplete or wrong-scope sustained result')
    rows=result.get('workloads',[])
    if len(rows)!=len(required) or {r.get('kind') for r in rows}!=required or any(r.get('result',{}).get('status')!='passed' for r in rows):raise ValueError('missing or failed workload')
    values={r['kind']:r['result'] for r in rows}
    cycles=values['lifecycle'].get('cycles',[])
    if len(cycles)<(100 if acceptance else 3) or [r.get('cycle') for r in cycles]!=list(range(len(cycles))) or any(r.get('status')!='passed' or r.get('full_snapshot_equal') is not True for r in cycles):
        raise ValueError('missing complete lifecycle/snapshot cycles')
    shapes={(r['quiescent_fds'],r['quiescent_threads']) for r in cycles}
    if len(shapes)!=1 or any(a<=0 or b<=0 for a,b in shapes):raise ValueError('quiescent FD/thread growth')
    clock=values['clock'];cases=clock.get('cases',[])
    if clock.get('constructed_history') is not True or len(cases)!=8:raise ValueError('missing constructed boundary cases')
    for case in cases:
        expected=(case['start_millis']+(case['advance_millis']//100)*100)%(2**32)
        if case.get('status')!='passed' or case.get('expected_millis')!=expected or case.get('expected_seconds')!=(expected//1000)%65536:raise ValueError('wrong independent boundary oracle')
    expected_cases={(65534000,1000),(65535000,1000),(65535500,1500),(65536000,2000),(4294966000,2000),(4294967000,1000),(4294967295,1),(4294967295,100)}
    if {(c['start_millis'],c['advance_millis']) for c in cases}!=expected_cases:raise ValueError('missing unique clock boundary coverage')
    faults=values['faults'].get('checks',[])
    if len(faults)!=len(FAULTS) or {r.get('name') for r in faults}!=FAULTS or any(r.get('status')!='passed' for r in faults):raise ValueError('missing fault cases')
    for kind,speed in ([('normal',1),('accelerated',60)] if scope=='full' else [('accelerated',60)]):
        row=values[kind]
        if not finite(row.get('observed_wall_seconds')) or row['observed_wall_seconds']<=0:raise ValueError('invalid observed duration')
        if row.get('qualification') is not acceptance or row.get('requested_speed')!=speed or not .85*speed<row.get('achieved_speed',0)<1.15*speed:raise ValueError('wrong workload rate or scope')
        if acceptance and row.get('observed_wall_seconds',0)<DURATIONS[kind]:raise ValueError('insufficient continuous wall duration')
        if row.get('pid')!=row.get('lifetime',{}).get('emulator_pid') or row.get('resource',{}).get('same_pid')!=row.get('pid'):raise ValueError('different continuous process')
        if row['lifetime'].get('wait4_collected') is not True or row['lifetime'].get('exit_code')!=0 or row['lifetime'].get('interrupted')!=0:raise ValueError('missing lifetime resource accounting')
        timing=row.get('latency',{})
        maximum=timing.get('max_seconds');median=timing.get('median_seconds');partial=timing.get('partial_token_seconds')
        if timing.get('samples')!=30 or not all(finite(x) for x in [maximum,median,partial]) or not 0<=median<=maximum<1 or not .6<partial<2.5:raise ValueError('failed protocol timing gates')
        if 'seconds' in timing:
            seconds=timing['seconds']
            if not isinstance(seconds,list) or len(seconds)!=30 or any(not finite(x) or x<0 for x in seconds) or max(seconds)!=maximum or statistics.median(seconds)!=median:raise ValueError('inconsistent timing distribution')
        if acceptance and not (set(row.get('states',[]))&{3,9} and set(row.get('states',[]))&{4,8}):raise ValueError('missing heating/cooling demands')
    if scope=='full':
        normal=values['normal']
        if set(normal.get('profile_observations',[]))!={'active','disabled'} or normal.get('host',{}).get('unchanged') is not True:raise ValueError('missing real-host profile/reference evidence')
    pressures=values['accelerated'].get('backpressure',[])
    if not pressures or any(p.get('status')!='passed' or p.get('ordered_replies')!=2000 or p.get('pause_seconds')!=.5 for p in pressures):raise ValueError('missing controlled backpressure')
    if acceptance and len(pressures)<6:raise ValueError('missing hourly controlled backpressure')
    if acceptance and values['accelerated'].get('controller_second_wraps',0)<16:raise ValueError('missing repeated 16-bit-second wraps')
    return values


def saved(run,base,acceptance,architecture,scope='full'):
    run=Path(run);base=Path(base)
    result=json.loads((run/'evidence/result.json').read_text());values=summary(result,acceptance,architecture,scope)
    harness=json.loads((run/'evidence/harness-inputs.json').read_text())
    if harness!=json.loads((run/'harness/INPUTS.json').read_text()):raise ValueError('harness receipt mismatch')
    for name,digest in harness['files'].items():
        if hashlib.sha256((run/'harness'/name).read_bytes()).hexdigest()!=digest:raise ValueError('harness input changed')
    runtime=json.loads((run/'evidence/runtime-inputs.json').read_text())
    if not runtime.get('external_package_records') or len(runtime.get('test_tools',{}))!=3:raise ValueError('missing runtime/tool identities')
    for records,root in [(runtime['external_package_records'],base/'rootfs'),(runtime['test_tools'],run)]:
        for name,digest in records.items():
            if hashlib.sha256((root/name.lstrip('/')).read_bytes()).hexdigest()!=digest:raise ValueError('runtime/tool input changed')
    manifest=json.loads((base/'candidate.json').read_text());manifest_sha=hashlib.sha256((base/'candidate.json').read_bytes()).hexdigest()
    expected=dict(manifest_sha256=manifest_sha,candidate_version='0.0.1-rc.1',architecture=architecture,source_snapshot_sha256=manifest['source_snapshot_sha256'],files=manifest['files'])
    if any(result.get('candidate',{}).get(k)!=v for k,v in expected.items()):raise ValueError('candidate identity mismatch')
    receipts=[json.loads(line) for line in (run/'evidence/payload-execution.jsonl').read_text().splitlines()]
    if [r.get('phase') for r in receipts]!=['before-r3','after-r3'] or any(any(r.get(k)!=v for k,v in expected.items()) for r in receipts):raise ValueError('missing input integrity receipts')
    for kind in (['normal','accelerated'] if scope=='full' else ['accelerated']):
        folder=run/'lab'/kind;row=values[kind]
        lifetime=json.loads((folder/'lifetime-0000.json').read_text())
        if lifetime!=row['lifetime']:raise ValueError('lifetime summary differs from actual report')
        samples=[json.loads(line) for line in (folder/'resources-0000/samples.jsonl').read_text().splitlines()]
        validated=validate_resources(samples,lifetime,kind,samples[-1]['elapsed'],acceptance)
        if validated!=row['resource']:raise ValueError('resource summary differs from complete trend evidence')
        resource_summary=json.loads((folder/'resources-0000/summary.json').read_text())
        if resource_summary.get('status')!='passed' or resource_summary.get('samples')!=len(samples):raise ValueError('resource observer incomplete')
        if lifetime.get('wall_seconds',0)<row['observed_wall_seconds'] or abs(lifetime['wall_seconds']-samples[-1]['elapsed'])>2:raise ValueError('missing complete process trend coverage')
    return dict(status='passed',qualification=acceptance,scope=scope,r3_complete=acceptance and scope=='full',architecture=architecture,validated_workloads=sorted(values),candidate_manifest_sha256=manifest_sha)
