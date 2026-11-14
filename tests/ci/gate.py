# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original execution receipts and fail-closed completion validation, not attestations."""
import base64
import json
import hashlib
import math
import re
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from payload import preflight, sha
from native import run as native, SUITES

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from source_inputs import inventory

LANES=['specification','helper-regressions','linux-amd64-release','linux-amd64-sanitizers',
       'linux-arm64-release','linux-arm64-sanitizers','macos-arm64-development','host-panel-arm64']


def identity():
    event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    pr=event.get('pull_request',{})
    source=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    if source!=os.environ['GITHUB_SHA']:
        raise ValueError('checked out source differs from event SHA')
    fingerprint=hashlib.sha256(json.dumps(inventory(ROOT),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(source_inputs_sha256=fingerprint,source_commit=source,event=os.environ['GITHUB_EVENT_NAME'],
                pr_head=pr.get('head',{}).get('sha'),pr_base=pr.get('base',{}).get('sha'),
                pr_merge=pr.get('merge_commit_sha'),workflow_ref=os.environ['GITHUB_WORKFLOW_REF'],
                workflow_sha=os.environ['GITHUB_WORKFLOW_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
                run_attempt=os.environ['GITHUB_RUN_ATTEMPT'])


def proof(lane, checks):
    expected_machine='arm64' if lane.startswith('macos') else ('aarch64' if 'arm64' in lane else 'x86_64')
    expected_system='Darwin' if lane.startswith('macos') else 'Linux'
    def native_proof(row, kind):
        return isinstance(row,dict) and row.get('status')=='passed' and row.get('kind')==kind and row.get('machine')==expected_machine and row.get('system')==expected_system and len(row.get('suites',[]))==6 and set(row.get('suites',[]))==SUITES and row.get('counts')==dict(passed=48,unresolved_reference_characterization=9)
    if lane.startswith('linux-'):
        release=lane.endswith('release')
        valid=len(checks)==(2 if release else 1) and native_proof(checks[0],'release' if release else 'sanitize')
        if valid and release:
            floor=checks[1]
            valid=floor.get('status')=='passed' and floor.get('source_git') is False and floor.get('reference_checkouts') is False and native_proof(floor.get('build'),'release') and floor['build'].get('cmake')=='cmake version 3.16.9' and floor['build'].get('python','').startswith('3.9.25')
    elif lane=='macos-arm64-development':
        valid=len(checks)==2+len(HELPERS) and native_proof(checks[0],'debug') and native_proof(checks[1],'sanitize') and checks[2:]==HELPERS
    else:
        expected={'specification':['specification','original-source-SPDX'],
                  'helper-regressions':HELPERS,
                  'host-panel-arm64':['17 host/panel workflows','reference/source integrity','owned container removal']}[lane]
        valid=checks==expected
    if not valid:raise ValueError('missing named execution proof: '+lane)


HELPERS=['tests/integration/checks.py','tests/qualification/launcher_checks.py','tests/qualification/checks.py','tests/ci/checks.py','release/checks.py']

def validate(needs, expected, candidate=None):
    fingerprint=expected.get('source_inputs_sha256','')
    if len(fingerprint)!=64 or any(c not in '0123456789abcdef' for c in fingerprint):
        raise ValueError('missing exact source input fingerprint')
    if set(needs)!=set(LANES):
        raise ValueError('missing or unexpected lane')
    for lane in LANES:
        job=needs[lane]
        if job.get('result')!='success':
            raise ValueError('lane did not execute successfully: '+lane)
        receipt=json.loads(base64.b64decode(job['outputs']['receipt'],validate=True))
        if receipt.get('identity')!=expected or receipt.get('lane')!=lane or receipt.get('status')!='passed':
            raise ValueError('wrong receipt identity or producer: '+lane)
        times=[receipt.get('started'),receipt.get('finished')]
        if any(type(v) not in [int,float] or not math.isfinite(v) or v<=0 for v in times):
            raise ValueError('invalid execution timestamps: '+lane)
        if receipt.get('producer')!='github-actions' or not receipt.get('checks') or times[1]<=times[0]:
            raise ValueError('missing execution evidence: '+lane)
        proof(lane,receipt['checks'])
        if candidate and (expected['source_commit']!=candidate or expected['event']=='pull_request'):
            raise ValueError('candidate requires exact frozen commit, not a PR merge')
    return dict(status='passed',identity=expected,lanes=LANES,candidate_acceptance=False)


def emit_receipt(report, output):
    encoded=base64.b64encode(json.dumps(report,separators=(',',':'),allow_nan=False).encode()).decode()
    # Eight receipts plus needs metadata must fit Linux's per-string exec limit.
    if len(encoded)>8192:raise ValueError('execution receipt exceeds bounded job-output budget')
    with Path(output).open('a') as stream:stream.write('receipt='+encoded+'\n')


def command(args, log, **kwargs):
    with Path(log).open('w') as output:
        subprocess.run([str(a) for a in args],check=True,stdout=output,stderr=subprocess.STDOUT,**kwargs)


def helpers(out):
    paths=HELPERS
    for path in paths:
        log=out/(Path(path).parent.name+'-'+Path(path).stem+'.log')
        try:command([sys.executable,ROOT/path],log)
        except subprocess.CalledProcessError:
            # These are original stdlib/mock helper diagnostics, never live client captures.
            print(log.read_text()[-16000:],file=sys.stderr)
            raise
    return paths


def integration_diagnostics(out):
    # Report original harness locations only, excluding captured response values.
    for name in ['integration-before-launcher-failure.json','integration-results.json']:
        path=out/'integration'/name
        if not path.exists():continue
        error=json.loads(path.read_text()).get('error') or ''
        for filename,line,function in re.findall(r'File "([^"]+)", line (\d+), in ([\w<>]+)',error):
            if '/tests/' in filename:
                print('Original harness failure location: '+Path(filename).name+':'+line+' in '+function,file=sys.stderr)
        break


def execute(lane, out):
    preflight()
    if lane=='helper-regressions':
        return helpers(out)
    if lane=='specification':
        command([sys.executable,ROOT/'tests/specification.py'],out/'specification.log')
        files=subprocess.check_output(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard'],text=True).splitlines()
        for name in files:
            path=ROOT/name
            if path.suffix in {'.py','.sh','.cpp','.hpp','.yml','.in'} and 'SPDX-License-Identifier: MIT' not in path.read_text():
                raise ValueError('missing MIT source marker: '+name)
        return ['specification','original-source-SPDX']
    if lane=='macos-arm64-development':
        if platform.system()!='Darwin' or platform.machine()!='arm64':raise ValueError('wrong macOS runner')
        reports=[native(ROOT,out/k,k) for k in ['debug','sanitize']]
        return reports+helpers(out)
    if lane.startswith('linux-'):
        _, arch, config=lane.split('-')
        expected={'amd64':'x86_64','arm64':'aarch64'}[arch]
        if platform.system()!='Linux' or platform.machine()!=expected:raise ValueError('wrong native guest')
        if os.environ.get('RMX_HOST_MACHINE')!=expected:raise ValueError('host/guest architecture differs')
        os_release=Path('/etc/os-release').read_text()
        if 'ID=debian' not in os_release or 'VERSION_ID="12"' not in os_release:raise ValueError('wrong Linux baseline')
        compiler=subprocess.check_output(['c++','-dumpversion'],text=True).strip()
        if compiler!='12':raise ValueError('expected GCC 12')
        command(['dpkg-query','-W'],out/'packages.txt')
        return [native(ROOT,out/'native','sanitize' if config=='sanitizers' else 'release')]
    if lane=='host-panel-arm64':
        if platform.machine()!='aarch64':raise ValueError('host-panel requires native ARM64 host')
        image=os.environ.get('RMX_INTEGRATION_IMAGE','brewpi-emulator-m4-tools:local')
        image_arch=subprocess.check_output(['docker','image','inspect','--format','{{.Architecture}}',image],text=True).strip()
        if image_arch!='arm64':raise ValueError('host-panel guest image must be ARM64')
        try:
            command(['bash',ROOT/'tests/integration/run-isolated.sh',ROOT.parent/'brewpi-script-rmx',
                     ROOT.parent/'brewpi-www-rmx',out/'integration'],out/'integration-launcher.log')
        except subprocess.CalledProcessError:
            integration_diagnostics(out)
            raise
        sys.path.insert(0,str(ROOT/'tests/qualification'))
        from evidence import validate_integration
        validate_integration(out/'integration')
        return ['17 host/panel workflows','reference/source integrity','owned container removal']
    raise ValueError('unknown lane')


def main():
    preflight()
    lane=sys.argv[1]
    out=Path(sys.argv[2]).resolve()
    out.mkdir(parents=True,exist_ok=False)
    started=time.time()
    try:
        ident=identity()
        if lane=='pr-validation':
            report=validate(json.loads(os.environ['RMX_NEEDS']),ident)
        else:
            before=inventory(ROOT)
            checks=execute(lane,out)
            if inventory(ROOT)!=before:raise ValueError('source changed during checks')
            report=dict(status='passed',producer='github-actions',lane=lane,identity=ident,
                        started=started,finished=time.time(),checks=checks,
                        host_machine=os.environ.get('RMX_HOST_MACHINE',platform.machine()),
                        guest_machine=platform.machine(),source_file_count=len(before))
            (out/'source-inventory.json').write_text(json.dumps(before,indent=2)+'\n')
        (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
        if lane!='pr-validation' and os.environ.get('RMX_DEFER_RECEIPT')!='1':
            emit_receipt(report,os.environ['GITHUB_OUTPUT'])
    except BaseException as exc:
        (out/'receipt.json').write_text(json.dumps(dict(status='failed',lane=lane,error=type(exc).__name__))+'\n')
        raise


if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'tests'))
    main()
