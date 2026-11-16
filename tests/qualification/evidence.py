# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Require complete passing child evidence and verified container removal."""
import json
import hashlib
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ci'))
from payload import FILES, payload_files, source_identity


INTEGRATION_NAMES=['startup', 'factory initialization', 'discovery and assignment', 'mode b', 'mode f', 'mode o', 'LCD bytes and alternation', 'temperature units', 'default actions retain persistence quirks', 'profile disabled segment and resumption', 'calibration, deactivation, and manual output', 'reset and rediscovery', 'evolving temperatures and control states', 'actual process restart', 'logs and chart', 'maintenance log viewer', 'browser execution']
RUNTIME_NAMES=['unprivileged ownership and nonconsuming readiness', 'readiness rejection and exclusive ownership', 'pacing and response 1', 'pacing and response 10', 'pacing and response 60', 'slow-reader backpressure', 'coherent checkpoint continuation', 'failed checkpoint preservation', 'forced-stop recovery and saved state']

def named(rows, expected):
    return len(rows)==len(expected) and {row.get('name') for row in rows}==set(expected) and all(row.get('status')=='passed' for row in rows)


def input_evidence(directory, kind):
    report=json.loads((directory/'execution-input.json').read_text())
    mode=os.environ.get('RMX_EXECUTION_MODE','source-build')
    if mode not in ['source-build','packaged-input'] or report.get('mode')!=mode:
        raise ValueError('wrong execution mode')
    manifest=json.loads(Path(os.environ['RMX_PAYLOAD_MANIFEST']).read_text()) if mode=='packaged-input' else None
    files=payload_files(manifest) if manifest is not None else FILES
    if manifest is not None and set(manifest.get('files',{}))!=files:
        raise ValueError('incorrect declared payload inventory')
    if kind=='qualification':
        integrity=json.loads((directory/'installed-integrity.json').read_text())
        if integrity.get('status')!='passed' or set(report.get('files',{}))!=files or integrity.get('files')!=report['files']:
            raise ValueError('missing installed-file integrity evidence')
    else:
        rows=[json.loads(row) for row in (directory/'executable-hashes.jsonl').read_text().splitlines()]
        if {r.get('phase') for r in rows}!={'restart-1','restart-2','restart-3','after-integration'} or len(rows)!=4 or not report.get('sha256') or any(r.get('sha256')!=report['sha256'] for r in rows):
            raise ValueError('missing executable restart/completion hash evidence')
    if mode!='packaged-input':return
    manifest_bytes=Path(os.environ['RMX_PAYLOAD_MANIFEST']).read_bytes()
    manifest=json.loads(manifest_bytes)
    expected_identity=dict(manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),**source_identity(manifest),
        candidate_version='0.0.1-rc.1',architecture=manifest['architecture'],files=manifest['files'])
    if manifest.get('candidate_version')!='0.0.1-rc.1':
        raise ValueError('wrong frozen payload manifest identity')
    def bound(row):
        return row.get('mode')=='packaged-input' and all(row.get(k)==v for k,v in expected_identity.items())
    records=[json.loads(row) for row in (directory/'payload-execution.jsonl').read_text().splitlines()]
    phases=[r.get('phase') for r in records]
    expected=['before-integration','restart-1','restart-2','restart-3','after-integration'] if kind=='integration' else ['before-runtime','service-start','service-end','after-runtime']
    if phases!=expected or any(not bound(r) for r in records):
        raise ValueError('missing or mismatched payload hash/restart evidence')
    if kind=='qualification':
        if report['files']!=manifest['files'] or report.get('architecture')!=manifest['architecture']:
            raise ValueError('installed payload differs from frozen manifest')
        starts=[json.loads(row) for row in (directory/'runtime-results/payload-execution.jsonl').read_text().splitlines()]
        if not starts or any(r.get('phase')!='runtime-process-start' or not bound(r) for r in starts):
            raise ValueError('missing runtime process hash evidence')
    elif report['sha256']!=manifest['files']['bin/brewpi-emulator-rmx'] or report.get('executable')!='/payload/bin/brewpi-emulator-rmx':
        raise ValueError('integration did not execute frozen payload')


def native_evidence(directory, kind):
    expected={'milestone3-model','milestone3-dynamics','milestone3-process','milestone2-fixtures','milestone2-edges','milestone2-pty'}
    execution=json.loads((directory/'execution.json').read_text())
    if execution.get('status')!='passed' or execution.get('kind')!=kind or len(execution.get('suites',[]))!=6 or set(execution['suites'])!=expected or execution.get('counts')!=dict(passed=48,unresolved_reference_characterization=9):
        raise ValueError('incomplete named native execution evidence: '+kind)


def validate(directory):
    def report(name):
        value=json.loads((directory/name).read_text())
        if value.get('status')!='passed':
            raise ValueError('nonpassing report: '+name)
        return value
    result=report('qualification-results.json')
    integrity=report('source-integrity.json')
    if integrity.get('unchanged') is not True or integrity.get('files',0)<=0:
        raise ValueError('source integrity was not verified')
    service=report('service-results.json')
    runtime=report('runtime-results/runtime-results.json')
    if not service.get('unit_commands_executed'):
        raise ValueError('service commands were not exercised')
    if not named(runtime.get('checks',[]),RUNTIME_NAMES):
        raise ValueError('incomplete runtime evidence')
    if result.get('runtime')!=runtime:
        raise ValueError('runtime summary differs from saved report')
    for kind in ['release','sanitize']:
        native_evidence(directory/('native-'+kind),kind)
        fixture=json.loads((directory/('native-'+kind)/'milestone3-fixtures.json').read_text())
        if fixture.get('counts')!=dict(passed=48,unresolved_reference_characterization=9):
            raise ValueError('incomplete native fixture evidence: '+kind)


def validate_integration(directory):
    def passed(name):
        value=json.loads((directory/name).read_text())
        if value.get('status')!='passed':raise ValueError('nonpassing report: '+name)
        return value
    result=passed('integration-results.json')
    workflows=result.get('workflows',[])
    if not named(workflows,INTEGRATION_NAMES) or result.get('browser_errors')!=[]:
        raise ValueError('incomplete integration workflow evidence')
    source=passed('source-integrity.json')
    if source.get('unchanged') is not True or source.get('files',0)<=0:
        raise ValueError('original source integrity was not verified')
    cleanup=passed('cleanup-results.json')
    if cleanup.get('errors')!=[] or not cleanup.get('host_exits') or any(code!=0 for code in cleanup['host_exits']):
        raise ValueError('application cleanup or host exit failed')
    integrity=json.loads((directory/'reference-code-integrity.json').read_text())
    if integrity.get('unchanged') is not True or integrity.get('checked_files',0)<=0:
        raise ValueError('reference integrity was not verified')
    native_evidence(directory/'native-test-results','debug')
    fixture=json.loads((directory/'native-test-results/milestone3-fixtures.json').read_text())
    if fixture.get('counts')!=dict(passed=48,unresolved_reference_characterization=9):
        raise ValueError('incomplete integration native fixture evidence')


def finish(directory, exit_code, cleanup_ok, kind="qualification"):
    error=None
    if exit_code==0:
        try:
            (validate_integration if kind=="integration" else validate)(directory)
            input_evidence(directory,kind)
            if not cleanup_ok:
                raise ValueError('owned container removal could not be verified')
        except Exception as exc:
            error=str(exc)
            exit_code=1
    if exit_code:
        primary=directory/(kind+'-results.json')
        if primary.exists():primary.rename(directory/(kind+'-before-launcher-failure.json'))
        primary.write_text(json.dumps(dict(status='failed',stage='launcher',exit_code=exit_code,error=error))+'\n')
    (directory/'launcher-results.json').write_text(json.dumps(dict(
        status='passed' if exit_code==0 else 'failed',exit_code=exit_code,
        cleanup_verified=cleanup_ok,error=error))+'\n')
    return exit_code


if __name__=='__main__':
    sys.exit(finish(Path(sys.argv[1]),int(sys.argv[2]),sys.argv[3]=='yes',sys.argv[4] if len(sys.argv)>4 else 'qualification'))
