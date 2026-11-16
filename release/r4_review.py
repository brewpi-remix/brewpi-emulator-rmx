# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Offline reconciliation of saved rc.1 artifacts, Git source, and R4 evidence.

Reads retained evidence without executing source, changing packages, or rerunning
workloads. Checksums establish internal consistency, not authentication.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch
from artifacts import ROOT, STEM, preflight, sha, source_record, unpack
from local import verify_freeze, compare_builds
sys.path.insert(0,str(ROOT/'tests/qualification'))
from evidence import validate, validate_integration, input_evidence, named, RUNTIME_NAMES
sys.path.insert(0,str(ROOT/'tests/ci'))
from gate import LANES, validate as validate_ci
sys.path.insert(0,str(ROOT/'tests'))
from source_inputs import inventory


def require(condition, message):
    if not condition:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text())


def source_association(record, association, repo, commit, archive_digest):
    require(len(commit)==40 and all(c in '0123456789abcdef' for c in commit),'exact expected commit required')
    require(association.get('source_commit')==commit and association.get('source_snapshot_sha256')==record['source_snapshot_sha256'] and association.get('source_archive_sha256')==archive_digest,'source association identity mismatch')
    require(association.get('original_file_count')==len(record['files']) and association.get('status')=='passed','incomplete source association')
    rows=subprocess.check_output(['git','-C',str(repo),'ls-tree','-rz',commit]).split(b'\0')
    modes={row.split(b'\t',1)[1].decode():int(row.split(b' ',1)[0],8)&0o777 for row in rows if row}
    for name,entry in record['files'].items():
        original=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+name])
        require(hashlib.sha256(original).hexdigest()==entry['sha256'] and modes.get(name)==entry['mode'],'source differs from Git: '+name)


def capture(archive, directory):
    """Bind the parsed reports to the preserved raw archive, file by file."""
    directory=Path(directory);seen=set()
    with tarfile.open(archive,'r:gz') as stream:
        for member in stream:
            name=PurePosixPath(member.name)
            require(not name.is_absolute() and '..' not in name.parts and not member.issym() and not member.islnk() and (member.isdir() or member.isfile()),'unsafe evidence archive member')
            if member.isdir():continue
            require(str(name) not in seen,'duplicate evidence archive file');seen.add(str(name))
            path=directory/str(name)
            require(not path.is_symlink() and path.is_file() and sha(path)==hashlib.sha256(stream.extractfile(member).read()).hexdigest(),'extracted evidence differs from archive: '+str(name))
    paths=list(directory.rglob('*'))
    require(all(not p.is_symlink() and (p.is_file() or p.is_dir()) for p in paths),'nonregular extracted evidence')
    actual={str(p.relative_to(directory)) for p in paths if p.is_file()}
    require(seen==actual,'missing or extra extracted evidence')
    return sha(archive)


def native_launch(launcher, namespace, manifest, role, scoped):
    expected=dict(status='passed',exit_code=0,error=None,architecture='amd64',native_machine='x86_64',role=role,cleanup_verified=True,remaining_owned_pids=[],source_snapshot_sha256=manifest['source_snapshot_sha256'])
    require(all(launcher.get(k)==v for k,v in expected.items()),'incomplete or mismatched native launcher')
    times=[launcher.get(k) for k in ['started_utc','finished_utc']]
    require(all(type(t) in [int,float] and math.isfinite(t) and t>0 for t in times) and times[1]>times[0],'invalid native execution times')
    expected=dict(host_machine='x86_64',private_mounts=True,private_network=True,private_tool_filesystem=True,source_payload_references_readonly=True,physical_devices=False,systemd_activation=False)
    require(all(namespace.get(k)==v for k,v in expected.items()),'missing native isolation evidence')
    require(launcher.get('sanitizer_process_no_aslr',False) is scoped and namespace.get('sanitizer_process_no_aslr',False) is scoped,'wrong sanitizer execution condition')


def runtime_receipts(directory, manifest, digest):
    report=read(directory/'runtime-results.json');environment=read(directory/'clean-environment.json')
    require(report.get('status')=='passed' and named(report.get('checks',[]),RUNTIME_NAMES) and environment.get('status')=='passed' and environment.get('compiler_linker_build_tools_absent') is True,'incomplete clean runtime')
    owner=report['checks'][0]['details']
    require(owner.get('uid')==2001 and owner.get('gid')==2001,'native runtime did not use test account')
    rows=[json.loads(line) for line in (directory/'payload-execution.jsonl').read_text().splitlines()]
    expected=dict(mode='packaged-input',phase='runtime-process-start',manifest_sha256=digest,source_commit=None,base_commit=manifest['base_commit'],source_snapshot_sha256=manifest['source_snapshot_sha256'],candidate_version='0.0.1-rc.1',architecture='amd64',files=manifest['files'])
    require(bool(rows) and all(all(row.get(k)==v for k,v in expected.items()) for row in rows),'wrong clean-runtime payload identity')


def packet_files(packet):
    names={'acceptance.json','source-association.json','minimum-tools.json','sanitizer-environment.json','hosted-ci-verification.json'}
    require({p.name for p in packet.iterdir()}==names|{'SHA256SUMS'},'wrong acceptance packet inventory')
    lines=(packet/'SHA256SUMS').read_text().splitlines();seen=set()
    for line in lines:
        digest,name=line.split('  ',1)
        require(name in names and name not in seen and not (packet/name).is_symlink() and sha(packet/name)==digest,'acceptance packet checksum mismatch');seen.add(name)
    require(seen==names,'incomplete acceptance checksums')


def review(candidate, evidence, ci, commit, packet=None):
    preflight();candidate=Path(candidate);evidence=Path(evidence);ci=Path(ci)
    frozen=verify_freeze(candidate);association=read(evidence/'source-association.json')
    if packet:
        packet=Path(packet);packet_files(packet)
        for name in ['acceptance.json','source-association.json','minimum-tools.json','sanitizer-environment.json']:
            require((packet/name).read_bytes()==(evidence/name).read_bytes(),'acceptance packet differs from retained record')
        require((packet/'hosted-ci-verification.json').read_bytes()==(ci/'verification.json').read_bytes(),'wrong packet CI record')
    with tempfile.TemporaryDirectory() as temporary:
        archive=candidate/(STEM+'-source.tar.gz')
        source=unpack(archive,Path(temporary)/'source',STEM+'-source');record=source_record(source)
        source_association(record,association,ROOT,commit,sha(archive))
        fingerprint=hashlib.sha256(json.dumps(inventory(source),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    verified=read(ci/'verification.json');run=read(ci/'run.json');expected=dict(verified['identity'],source_commit=commit,workflow_sha=commit,source_inputs_sha256=fingerprint)
    require(verified['identity']==expected and expected['event']=='push' and expected['run_id']==str(run['databaseId']) and expected['run_attempt']==str(run['attempt']),'wrong CI source/run identity')
    require(expected['workflow_ref']=='brewpi-remix/brewpi-emulator-rmx/.github/workflows/regression.yml@refs/heads/main' and run['event']=='push','wrong CI workflow origin')
    require(run['status']=='completed' and run['headSha']==commit and run['conclusion']=='success' and len(run['jobs'])==9 and {j['name'] for j in run['jobs']}==set(LANES)|{'pr-validation'} and all(j['conclusion']=='success' and j['status']=='completed' for j in run['jobs']),'incomplete hosted CI')
    needs={}
    for lane in LANES:
        path=ci/'artifacts'/(lane+'-'+str(run['attempt']))/'receipt.json';raw=path.read_bytes()
        require(sha(path)==verified['artifacts_sha256'][str(path.relative_to(ci))],'CI receipt changed')
        needs[lane]=dict(result='success',outputs=dict(receipt=base64.b64encode(raw).decode()))
    require(validate_ci(needs,expected)==read(ci/'artifacts'/('pr-validation-'+str(run['attempt']))/'receipt.json'),'completion receipt mismatch')
    minimum=read(evidence/'minimum-tools.json');require(minimum['source_commit']==commit and minimum['source_inputs_sha256']==fingerprint,'wrong minimum-tool source')
    acceptance=read(evidence/'acceptance.json')
    require(acceptance['version']=='0.0.1-rc.1' and acceptance['status']=='R4-technical-checks-passed-review-required' and acceptance['owner_review_pending'] is True and all(acceptance[k] is False for k in ['r5_accepted','r6_complete','release_published','physical_pi_qualified','systemd_activation','arduino_characterization_completed']),'unsupported acceptance claim')
    require(acceptance['source_inputs_sha256']==fingerprint,'wrong acceptance source fingerprint')
    require(acceptance['source_commit']==commit and acceptance['source_snapshot_sha256']==record['source_snapshot_sha256'] and acceptance['archives']=={p.name:sha(p) for p in candidate.glob('*.tar.gz')} and acceptance['candidate_freeze_sha256']==sha(candidate/'freeze.json'),'acceptance artifact identity mismatch')
    native_hashes={};attempt=evidence/'attempt1'
    for arch in ['arm64','amd64']:
        manifest_path=candidate/(arch+'-payload-manifest.json');manifest=read(manifest_path)
        build=attempt/'builds'/arch/'first/result';require((build/'payload-manifest.json').read_bytes()==manifest_path.read_bytes(),'tested build differs from saved payload')
        compare_builds(attempt,arch)
        require(sha(build/(STEM+'-linux-'+arch+'.tar.gz'))==sha(candidate/(STEM+'-linux-'+arch+'.tar.gz')),'tested archive differs from saved archive')
        receipt=read(ci/'artifacts'/('linux-'+arch+'-release-'+str(run['attempt']))/'receipt.json');floor=receipt['checks'][1]['build']
        minimum_row=minimum['architectures'][arch]
        require(all(minimum_row.get(k)==floor.get(k) for k in ['cmake','python','compiler','executable_sha256']) and minimum_row.get('native_machine')==floor['machine'] and minimum_row.get('source_git') is False and minimum_row.get('reference_checkouts') is False,'minimum-tool summary differs from receipt')
        require(floor['executable_sha256']==manifest['files']['bin/brewpi-emulator-rmx']==minimum['architectures'][arch]['executable_sha256'] and minimum['architectures'][arch]['receipt_sha256']==sha(ci/'artifacts'/('linux-'+arch+'-release-'+str(run['attempt']))/'receipt.json'),'minimum-tool/package mismatch')
        with patch.dict(os.environ,RMX_EXECUTION_MODE='packaged-input',RMX_CANDIDATE_COMMIT='',RMX_CANDIDATE_SNAPSHOT=manifest['source_snapshot_sha256'],RMX_PAYLOAD_MANIFEST=str(manifest_path.resolve())):
            if arch=='arm64':
                for role,validator in [('integration',validate_integration),('qualification',validate)]:
                    folder=attempt/('packaged-'+role+'-arm64');validator(folder);input_evidence(folder,role)
                    launch=read(folder/'launcher-results.json');require(launch['exit_code']==0 and launch['status']=='passed' and launch['cleanup_verified'],'ARM64 workflow cleanup failed')
                    require(acceptance['checks']['arm64-'+role]['launcher_sha256']==sha(folder/'launcher-results.json'),'wrong accepted ARM64 launcher')
            else:
                for label,role,scoped in [('native-full','integration',False),('native-operating-retry','qualification',True),('native-clean-runtime','runtime',False)]:
                    folder=evidence/(label+'-evidence')/role;archive=evidence/(label+'-evidence')/(role+'.tar.gz')
                    native_hashes[role]=capture(archive,folder)
                    key='amd64-native-clean-runtime' if role=='runtime' else 'amd64-'+role
                    require(native_hashes[role]==acceptance['checks'][key]['evidence_archive_sha256'],'wrong accepted raw evidence archive')
                    native_launch(read(folder/'native-launcher.json'),read(folder/'namespace.json'),manifest,role,scoped)
                    if role!='runtime':require(acceptance['checks'][key]['launcher_sha256']==sha(folder/'native-launcher.json'),'wrong accepted native launcher')
                    stage=evidence/label/'inputs';request=read(stage/'request.json')
                    require(request==read(evidence/label/'launch.json')['request'] and request['manifest_sha256']==sha(manifest_path) and (stage/'candidate.json').read_bytes()==manifest_path.read_bytes() and request['native_wrapper_sha256']==sha(stage/'native_package.py') and request['source_snapshot_sha256']==manifest['source_snapshot_sha256'] and request['source_commit']==commit,'native staging/request mismatch')
                    tool_label='runtime-tools' if role=='runtime' else 'full-tools';tools=read(evidence/(tool_label+'.json'))
                    image=read(evidence/tool_label/'image-inspect.json')
                    require(request['tools']==tools and image['Id']==tools['image_id'] and image['Architecture']=='amd64','wrong native external tools identity')
                    require(source_record(stage/'source')['source_snapshot_sha256']==record['source_snapshot_sha256'],'wrong native source tree')
                    if role=='runtime':
                        runtime_receipts(folder/'evidence',manifest,sha(manifest_path))
                        for name in ['runtime-packages.tsv','runtime-debs.sha256']:require((folder/'evidence'/name).read_bytes()==(candidate/('amd64-'+name)).read_bytes(),'native baseline runtime changed')
                    else:
                        (validate_integration if role=='integration' else validate)(folder/'evidence');input_evidence(folder/'evidence',role)
    summary=read(evidence/'sanitizer-environment.json')
    with tarfile.open(evidence/'asan-diagnostic.tar.gz') as stream:diagnostic=json.load(stream.extractfile('./diagnostic.json'))
    require(summary['raw_diagnostic_archive_sha256']==sha(evidence/'asan-diagnostic.tar.gz') and summary['failed_qualification_archive_sha256']==sha(evidence/'native-full-evidence/qualification-failed.tar.gz'),'sanitizer diagnostic archive mismatch')
    require(len(diagnostic['default_runs'])==len(diagnostic['process_scoped_no_aslr'])==50 and diagnostic['default_failures']==sum(r['exit_code']!=0 for r in diagnostic['default_runs'])>0 and all(r['exit_code']==0 for r in diagnostic['process_scoped_no_aslr']) and diagnostic['scoped_failures']==0 and diagnostic['positive_control']['exit_code']!=0 and 'heap-buffer-overflow' in diagnostic['positive_control']['stderr'],'incomplete sanitizer startup/positive control')
    require('R4 sanitizer-only process ASLR workaround' in (evidence/'native-operating-retry-evidence/qualification/evidence/ctest-sanitize.log').read_text(),'missing executed sanitizer condition')
    tool_inputs=inventory(ROOT)
    return dict(status='passed',scope='Independent final R4 review; no workload rerun, artifact replacement, R5 acceptance, or publication',source_commit=commit,source_snapshot_sha256=record['source_snapshot_sha256'],source_inputs_sha256=fingerprint,native_evidence_sha256=native_hashes,accepted_packet_sha256=sha(packet/'SHA256SUMS') if packet else None,
        verifier_sha256=sha(Path(__file__)),review_tool_source_inputs_sha256=hashlib.sha256(json.dumps(tool_inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('candidate',type=Path);parser.add_argument('evidence',type=Path);parser.add_argument('ci',type=Path)
    parser.add_argument('--commit',required=True);parser.add_argument('--packet',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=review(args.candidate,args.evidence,args.ci,args.commit,args.packet)
    with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
