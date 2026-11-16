# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Local, offline artifact orchestration; explicit preparation and sealing phases."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import stat
import xml.etree.ElementTree as ET
from artifacts import ROOT, STEM, VERSION, canonical, snapshot, sha, source_record, payload_record, unpack, write_json, preflight, checked_version


def compare_builds(output, arch):
    output=Path(output);results=[output/'builds'/arch/label/'result' for label in ['first','second']]
    names=[STEM+'-source.tar.gz',STEM+'-linux-'+arch+'.tar.gz','payload-manifest.json','build-manifest.json','packages.tsv','debs.sha256','indices.sha256']
    for name in names:
        if (results[0]/name).read_bytes()!=(results[1]/name).read_bytes():raise ValueError('reproducibility mismatch: '+arch+'/'+name)
    sys.path.insert(0,str(ROOT/'tests/ci'))
    from native import SUITES
    for result in results:
        rows=ET.parse(result/'ctest.xml').findall('./Testing/Test')
        if len(rows)!=6 or {r.findtext('Name') for r in rows}!=SUITES or any(r.get('Status')!='passed' for r in rows):
            raise ValueError('incomplete build-root CTest evidence')
        fixture=json.loads((result/'native-results/fixtures.json').read_text())
        report=json.loads((result/'build-results.json').read_text())
        counts=dict(passed=48,unresolved_reference_characterization=9)
        if fixture.get('counts')!=counts or report.get('status')!='passed' or report.get('counts')!=counts or report.get('native_suites')!=6:
            raise ValueError('incomplete build-root fixture evidence')
    first,second=[result/'external-notices' for result in results]
    expected={name+'-copyright.txt' for name in ['libc6','libc6-dev','libstdc++6','libgcc-s1','gcc-12-base']}
    if {p.name for p in first.iterdir()}!=expected or {p.name for p in second.iterdir()}!=expected:
        raise ValueError('incorrect external notice inventory')
    for name in expected:
        if not (first/name).is_file() or (first/name).is_symlink() or not (second/name).is_file() or (second/name).is_symlink() or (first/name).read_bytes()!=(second/name).read_bytes():
            raise ValueError('external notice mismatch')


def docker(args, log, timeout=1800, cid=None):
    handlers={sig:signal.getsignal(sig) for sig in [signal.SIGINT,signal.SIGTERM]}
    def interrupted(signum,frame):raise SystemExit(128+signum)
    for sig in handlers:signal.signal(sig,interrupted)
    try:
        with Path(log).open('w') as output:
            subprocess.run(['docker',*map(str,args)],stdout=output,stderr=subprocess.STDOUT,check=True,timeout=timeout)
    finally:
        for sig in handlers:signal.signal(sig,signal.SIG_IGN)
        try:
            if cid and Path(cid).exists():
                identity=Path(cid).read_text().strip()
                if not identity:raise RuntimeError('empty owned container identity')
                subprocess.run(['docker','rm','-f',identity],capture_output=True,timeout=30)
                remaining=subprocess.check_output(['docker','ps','-aq','--no-trunc','--filter','id='+identity],text=True,timeout=15).strip()
                if remaining:raise RuntimeError('owned container cleanup failed')
            elif cid:raise RuntimeError('no owned container identity recorded')
        finally:
            for sig,handler in handlers.items():signal.signal(sig,handler)


def image(role, arch):
    tag='brewpi-emulator-package-'+role+':'+arch
    raw=json.loads(subprocess.check_output(['docker','image','inspect',tag],text=True))[0]
    if raw['Architecture']!=arch:raise ValueError('wrong tool image architecture')
    return raw['Id']


def prepare(output):
    preflight()
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    record=snapshot(ROOT,output/'transport')
    transport=output/'transport'/(STEM+'-source.tar.gz')
    tools=output/'transport/extracted'/(STEM+'-source')
    lock={arch:{role:image(role,arch) for role in ['build','runtime']} for arch in ['arm64','amd64']}
    docker_machine=subprocess.check_output(['docker','info','--format','{{.Architecture}}'],text=True).strip()
    native_arch={'aarch64':'arm64','x86_64':'amd64'}.get(docker_machine)
    if native_arch is None:raise ValueError('unsupported Docker VM machine')
    write_json(output/'environment-lock.json',dict(schema=1,images=lock,host_machine=platform.machine(),
        docker_machine=docker_machine,
        execution={arch:('native '+arch+' Linux guest' if arch==native_arch else 'emulated '+arch+' Linux guest on '+docker_machine) for arch in ['arm64','amd64']},
        recipes={name:sha(ROOT/'release'/name) for name in ['build.Dockerfile','runtime.Dockerfile']}))
    canonical_dir=output/'canonical';canonical_dir.mkdir()
    cid=canonical_dir/'container.cid'
    docker(['run','--rm','--init','--cidfile',cid,'--network','none','--platform','linux/arm64',
        '--tmpfs','/build:exec','-v',str(tools)+':/tools:ro','-v',str(transport)+':/transport.tar.gz:ro',
        '-v',str(canonical_dir)+':/output',lock['arm64']['build'],'python3','/tools/release/artifacts.py',
        'repack-source','/transport.tar.gz','/output/'+STEM+'-source.tar.gz','--work','/build/canonical'],
        output/'canonical-source.log',cid=cid)
    source=canonical_dir/(STEM+'-source.tar.gz')
    frozen_source=unpack(source,output/'source',STEM+'-source');source_record(frozen_source)
    results={}
    for arch in ['arm64','amd64']:
        results[arch]={}
        for label,root in [('first','/build/first-root'),('second','/build/differently-located/second-root')]:
            folder=output/'builds'/arch/label;folder.mkdir(parents=True)
            cid=folder/'container.cid'
            docker(['run','--rm','--init','--cidfile',cid,'--platform','linux/'+arch,'--network','none',
                '--user',str(os.getuid())+':'+str(os.getgid()),'--cap-drop','ALL','--security-opt','no-new-privileges',
                '--tmpfs','/build:exec','-v',str(frozen_source)+':/tools:ro','-v',str(source)+':/source.tar.gz:ro',
                '-v',str(folder)+':/output',lock[arch]['build'],'python3','/tools/release/artifacts.py',
                'build','/source.tar.gz','/output/result','--work',root,'--architecture',arch,'--image-id',lock[arch]['build']],
                folder/'container.log',cid=cid)
            results[arch][label]=folder/'result'
        first,second=results[arch]['first'],results[arch]['second']
        compare_builds(output,arch)
        if (first/(STEM+'-source.tar.gz')).read_bytes()!=source.read_bytes():raise ValueError('source archive differs across architecture')
    write_json(output/'reproducibility.json',dict(status='passed',source_archive_sha256=sha(source),
        source_snapshot_sha256=record['source_snapshot_sha256'],independent_roots=2,
        architectures={arch:dict(binary_archive_sha256=sha(results[arch]['first']/(STEM+'-linux-'+arch+'.tar.gz')),
            build_manifest_sha256=sha(results[arch]['first']/'build-manifest.json'),native_execution=(arch==native_arch)) for arch in results}))


def runtime(output,arch):
    preflight()
    output=Path(output).resolve();lock=json.loads((output/'environment-lock.json').read_text())
    result=output/'builds'/arch/'first/result';manifest=result/'payload-manifest.json'
    metadata=json.loads(manifest.read_text());tree=result/'extracted'/(STEM+'-linux-'+arch)
    source=output/'source'/(STEM+'-source')
    folder=output/('clean-runtime-'+arch);folder.mkdir()
    cid=folder/'container.cid'
    if os.getuid()==0:raise RuntimeError('clean runtime requires an unprivileged host account')
    results=folder/'results';results.mkdir(mode=0o700)
    args=['create','--init','--cidfile',cid,'--platform','linux/'+arch,'--network','none','--read-only',
        '--user',str(os.getuid())+':'+str(os.getgid()),'--cap-drop','ALL','--security-opt','no-new-privileges',
        '--tmpfs','/qualification:exec,uid='+str(os.getuid())+',gid='+str(os.getgid())+',mode=0755','--tmpfs','/tmp:exec',
        '-v',str(results)+':/qualification/results',
        '-e','RMX_EXECUTION_MODE=packaged-input','-e','RMX_CANDIDATE_SNAPSHOT='+metadata['source_snapshot_sha256'],
        '-e','RMX_PAYLOAD_ROOT=/usr/local','-e','RMX_PAYLOAD_MANIFEST=/candidate.json',
        '-e','RMX_PAYLOAD_RECEIPT=/qualification/results/payload-execution.jsonl',
        '-v',str(source)+':/work:ro','-v',str(tree)+':/usr/local:ro','-v',str(manifest)+':/candidate.json:ro',
        lock['images'][arch]['runtime'],'python3','/work/release/runtime.py','/usr/local/bin/brewpi-emulator-rmx']
    identity=None;exit_code=1
    try:
        subprocess.run(['docker',*map(str,args)],check=True,capture_output=True)
        identity=cid.read_text().strip()
        with (folder/'runtime.log').open('w') as stream:
            subprocess.run(['docker','start','-a',identity],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
        exit_code=int(subprocess.check_output(['docker','inspect','--format','{{.State.ExitCode}}',identity],text=True))
    finally:
        for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,signal.SIG_IGN)
        if identity is None and cid.exists():identity=cid.read_text().strip()
        if not identity:raise RuntimeError('clean runtime has no owned container identity')
        subprocess.run(['docker','rm','-f',identity],capture_output=True,timeout=30)
        remaining=subprocess.check_output(['docker','ps','-aq','--no-trunc','--filter','id='+identity],text=True,timeout=15).strip()
        if remaining:raise RuntimeError('clean runtime container remains')
        reports_present=(results/'runtime-results.json').is_file() and (results/'clean-environment.json').is_file()
        write_json(folder/'launcher.json',dict(status='passed' if exit_code==0 and reports_present else 'failed',
            exit_code=exit_code,cleanup_verified=True,execution_mode=lock['execution'][arch],image_id=lock['images'][arch]['runtime'],manifest_sha256=sha(manifest),
            runtime_inputs={name:sha(results/name) for name in ['runtime-packages.tsv','runtime-debs.sha256']} if reports_present else {}))
    if exit_code or not reports_present:raise RuntimeError('clean runtime failed')
    report=json.loads((folder/'results/runtime-results.json').read_text())
    if report['status']!='passed' or len(report['checks'])!=9:raise ValueError('incomplete clean-runtime evidence')


def seal(output,destination):
    preflight()
    output=Path(output).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('frozen candidate destination already exists')
    reproducible=json.loads((output/'reproducibility.json').read_text())
    if reproducible['status']!='passed':raise ValueError('reproducibility not verified')
    source=output/'source'/(STEM+'-source');record=source_record(source)
    lock=json.loads((output/'environment-lock.json').read_text())
    files={STEM+'-source.tar.gz':output/'canonical'/(STEM+'-source.tar.gz'),
           'environment-lock.json':output/'environment-lock.json','reproducibility.json':output/'reproducibility.json'}
    if reproducible['source_archive_sha256']!=sha(files[STEM+'-source.tar.gz']):raise ValueError('source archive changed after comparison')
    if reproducible.get('source_snapshot_sha256')!=record['source_snapshot_sha256'] or reproducible.get('independent_roots')!=2:
        raise ValueError('wrong reproducibility source identity')
    with tempfile.TemporaryDirectory() as temporary:
        extracted=unpack(files[STEM+'-source.tar.gz'],Path(temporary)/'source',STEM+'-source',epoch=record['source_date_epoch'])
        if source_record(extracted)!=record:raise ValueError('source archive differs from tested source')
    for arch in ['arm64','amd64']:
        compare_builds(output,arch)
        result=output/'builds'/arch/'first/result'
        if sha(result/(STEM+'-linux-'+arch+'.tar.gz'))!=reproducible['architectures'][arch]['binary_archive_sha256'] or sha(result/'build-manifest.json')!=reproducible['architectures'][arch]['build_manifest_sha256']:
            raise ValueError('build changed after reproducibility comparison')
        for name in [STEM+'-linux-'+arch+'.tar.gz']:files[name]=result/name
        for name in ['payload-manifest.json','build-manifest.json','packages.tsv','debs.sha256','indices.sha256']:
            files[arch+'-'+name]=result/name
        for path in sorted((result/'external-notices').iterdir()):files[arch+'-'+path.name]=path
        build_manifest=json.loads((result/'build-manifest.json').read_text())
        if build_manifest['image_id']!=lock['images'][arch]['build']:raise ValueError('wrong build environment identity')
        manifest=json.loads((result/'payload-manifest.json').read_text())
        inventory=payload_record(manifest,record,arch,sha(files[STEM+'-source.tar.gz']))
        if any(build_manifest.get(k)!=v for k,v in dict(architecture=arch,version=VERSION,source_snapshot_sha256=record['source_snapshot_sha256'],
            source_archive_sha256=sha(files[STEM+'-source.tar.gz']),source_date_epoch=record['source_date_epoch'],files=manifest['files'],file_modes=manifest['file_modes'],
            archive=STEM+'-linux-'+arch+'.tar.gz',archive_sha256=sha(result/(STEM+'-linux-'+arch+'.tar.gz')),
            package_inventory_sha256=sha(result/'packages.tsv'),package_archives_sha256=sha(result/'debs.sha256')).items()):
            raise ValueError('build manifest differs from packaged inputs')
        if (result/(STEM+'-source.tar.gz')).read_bytes()!=files[STEM+'-source.tar.gz'].read_bytes():raise ValueError('build source archive differs')
        clean=output/('clean-runtime-'+arch)
        report=json.loads((clean/'results/runtime-results.json').read_text())
        environment=json.loads((clean/'results/clean-environment.json').read_text())
        sys.path.insert(0,str(ROOT/'tests/qualification'))
        from evidence import RUNTIME_NAMES, named
        if report.get('status')!='passed' or not named(report.get('checks',[]),RUNTIME_NAMES) or environment.get('status')!='passed' or environment.get('compiler_linker_build_tools_absent') is not True:raise ValueError('missing clean-runtime checks')
        starts=[json.loads(line) for line in (clean/'results/payload-execution.jsonl').read_text().splitlines()]
        expected=dict(mode='packaged-input',phase='runtime-process-start',candidate_version=VERSION,architecture=arch,source_commit=None,
            base_commit=record['base_commit'],manifest_sha256=sha(result/'payload-manifest.json'),source_snapshot_sha256=record['source_snapshot_sha256'],files=manifest['files'])
        if not starts or any(any(row.get(k)!=v for k,v in expected.items()) for row in starts):raise ValueError('clean runtime payload identity mismatch')
        with tempfile.TemporaryDirectory() as temporary:
            unpack(result/(STEM+'-linux-'+arch+'.tar.gz'),Path(temporary)/'payload',STEM+'-linux-'+arch,inventory,epoch=record['source_date_epoch'])
        launch=json.loads((clean/'launcher.json').read_text())
        if launch['status']!='passed' or launch.get('exit_code')!=0 or launch['cleanup_verified'] is not True or launch.get('execution_mode')!=lock['execution'][arch] or launch.get('image_id')!=lock['images'][arch]['runtime'] or launch.get('manifest_sha256')!=sha(result/'payload-manifest.json'):raise ValueError('missing or mismatched clean-runtime validation')
        if launch.get('runtime_inputs')!={name:sha(clean/'results'/name) for name in ['runtime-packages.tsv','runtime-debs.sha256']}:raise ValueError('runtime package inputs changed')
        for name in ['runtime-packages.tsv','runtime-debs.sha256']:files[arch+'-'+name]=clean/'results'/name
    # ARM64 external-client/package qualification is available locally. AMD64's
    # native client and target qualification remain explicit later gates.
    keys=['RMX_EXECUTION_MODE','RMX_CANDIDATE_COMMIT','RMX_CANDIDATE_SNAPSHOT','RMX_PAYLOAD_MANIFEST']
    previous={key:os.environ.get(key) for key in keys}
    try:
        os.environ.update(RMX_EXECUTION_MODE='packaged-input',RMX_CANDIDATE_COMMIT='',
            RMX_CANDIDATE_SNAPSHOT=record['source_snapshot_sha256'],
            RMX_PAYLOAD_MANIFEST=str(output/'builds/arm64/first/result/payload-manifest.json'))
        from evidence import validate, validate_integration, input_evidence
        for name,kind,check in [('packaged-integration-arm64','integration',validate_integration),('packaged-qualification-arm64','qualification',validate)]:
            report=json.loads((output/name/'launcher-results.json').read_text())
            if report['status']!='passed' or report.get('exit_code')!=0 or report['cleanup_verified'] is not True:raise ValueError('missing native ARM64 package workflows')
            check(output/name);input_evidence(output/name,kind)
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    destination.parent.mkdir(parents=True,exist_ok=True)
    final_destination=destination
    destination=Path(tempfile.mkdtemp(prefix='package-staging-',dir=destination.parent))
    try:
        for name,path in files.items():shutil.copyfile(path,destination/name)
        write_json(destination/'source-manifest.json',dict(record,archive=STEM+'-source.tar.gz',archive_sha256=sha(files[STEM+'-source.tar.gz']),reviewed_commit_binding_pending=True))
        checks={p.name:sha(p) for p in sorted(destination.iterdir())}
        (destination/'SHA256SUMS').write_text(''.join(digest+'  '+name+'\n' for name,digest in checks.items()))
        write_json(destination/'freeze.json',dict(schema=1,status='frozen-provisional-review-required',version=VERSION,
            source_snapshot_sha256=record['source_snapshot_sha256'],base_commit=record['base_commit'],source_commit=None,
            source_commit_role='pending-reviewed-commit-binding',unsigned=True,sustained_testing_started=False,license_audit_accepted=False,
            pending=['owner review','reviewed commit association','candidate minimum-tool checks','native amd64 packaged client/qualification','sustained-evidence assessment','package/license/distribution acceptance'],
            files={p.name:sha(p) for p in sorted(destination.iterdir())}))
        (destination/'freeze.sha256').write_text(sha(destination/'freeze.json')+'  freeze.json\n')
        verify_freeze(destination)
        for path in destination.iterdir():path.chmod(0o444)
        destination.chmod(0o555)
        if final_destination.exists():raise ValueError('refusing to replace a candidate freeze')
        destination.rename(final_destination)
    except BaseException:
        if destination.exists():
            destination.chmod(0o755);shutil.rmtree(destination)
        raise



def verify_freeze(destination, expected_version=None):
    version=checked_version(expected_version if expected_version is not None else VERSION)
    stem="brewpi-emulator-rmx-"+version
    preflight()
    root=Path(destination)
    if root.is_symlink() or not root.is_dir():raise ValueError('candidate is not a regular directory')
    for path in root.iterdir():
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):raise ValueError('nonregular saved candidate member')
    data=json.loads((root/'freeze.json').read_text())
    pending={}
    for key,alias in [('license_audit_accepted','r5_accepted'),('sustained_testing_started','r3_started')]:
        if any(name in data and type(data[name]) is not bool for name in [key,alias]):raise ValueError('invalid saved acceptance flag')
        if key in data and alias in data and data[key]!=data[alias]:raise ValueError('conflicting saved acceptance flags')
        pending[key]=data.get(key,data.get(alias))
    if data.get('schema')!=1 or data.get('status')!='frozen-provisional-review-required' or data.get('version')!=version or data.get('source_commit') is not None or data.get('source_commit_role')!='pending-reviewed-commit-binding' or data.get('unsigned') is not True or pending['license_audit_accepted'] is not False or pending['sustained_testing_started'] is not False:
        raise ValueError('wrong provisional freeze identity')
    if (root/'freeze.sha256').read_text()!=sha(root/'freeze.json')+'  freeze.json\n':raise ValueError('freeze manifest checksum mismatch')
    actual={p.name for p in root.iterdir()}
    if actual!=set(data['files'])|{'freeze.json','freeze.sha256'}:raise ValueError('missing or extra frozen file')
    for name,digest in data['files'].items():
        if Path(name).name!=name or (root/name).is_symlink() or sha(root/name)!=digest:raise ValueError('frozen byte mismatch')
    for name in [stem+'-source.tar.gz',stem+'-linux-amd64.tar.gz',stem+'-linux-arm64.tar.gz']:
        if name not in data['files']:raise ValueError('missing frozen archive')
    expected=''.join(data['files'][name]+'  '+name+'\n' for name in sorted(data['files']) if name!='SHA256SUMS')
    if (root/'SHA256SUMS').read_text()!=expected:raise ValueError('checksum inventory mismatch')
    # Checksums detect accidental edits; independently reconcile archive contents
    # and sidecar identities as well. They are not signatures/authentication.
    metadata=json.loads((root/'source-manifest.json').read_text())
    source_digest=sha(root/(stem+'-source.tar.gz'))
    if metadata.get('archive_sha256')!=source_digest:raise ValueError('source sidecar archive mismatch')
    with tempfile.TemporaryDirectory() as temporary:
        source=unpack(root/(stem+'-source.tar.gz'),Path(temporary)/'source',stem+'-source',epoch=metadata['source_date_epoch'])
        record=source_record(source,expected_version=version)
        if any(metadata.get(k)!=v for k,v in record.items()) or any(data.get(k)!=record[k] for k in ['source_snapshot_sha256','base_commit','source_commit']):
            raise ValueError('saved source identities disagree')
        lock=json.loads((root/'environment-lock.json').read_text())
        reproducible=json.loads((root/'reproducibility.json').read_text())
        if reproducible.get('status')!='passed' or reproducible.get('independent_roots')!=2 or reproducible.get('source_archive_sha256')!=source_digest or reproducible.get('source_snapshot_sha256')!=record['source_snapshot_sha256']:
            raise ValueError('saved reproducibility identity mismatch')
        for name,digest in lock['recipes'].items():
            if name not in ['build.Dockerfile','runtime.Dockerfile'] or sha(source/'release'/name)!=digest:raise ValueError('saved recipe identity mismatch')
        if set(lock['recipes'])!={'build.Dockerfile','runtime.Dockerfile'}:raise ValueError('missing saved recipe')
        native_arch={'aarch64':'arm64','x86_64':'amd64'}.get(lock.get('docker_machine'))
        if native_arch is None:raise ValueError('unsupported saved Docker VM architecture')
        for arch in ['arm64','amd64']:
            execution='native '+arch+' Linux guest' if arch==native_arch else 'emulated '+arch+' Linux guest on '+lock['docker_machine']
            if lock['execution'].get(arch)!=execution or reproducible['architectures'][arch].get('native_execution') is not (arch==native_arch):
                raise ValueError('inconsistent native/emulated evidence label')
            manifest=json.loads((root/(arch+'-payload-manifest.json')).read_text())
            inventory=payload_record(manifest,record,arch,source_digest,expected_version=version)
            build=json.loads((root/(arch+'-build-manifest.json')).read_text())
            archive=stem+'-linux-'+arch+'.tar.gz'
            expected=dict(architecture=arch,version=version,source_snapshot_sha256=record['source_snapshot_sha256'],source_archive_sha256=source_digest,
                source_date_epoch=record['source_date_epoch'],files=manifest['files'],file_modes=manifest['file_modes'],archive=archive,
                archive_sha256=sha(root/archive),image_id=lock['images'][arch]['build'],
                package_inventory_sha256=sha(root/(arch+'-packages.tsv')),package_archives_sha256=sha(root/(arch+'-debs.sha256')))
            if any(build.get(k)!=v for k,v in expected.items()):raise ValueError('saved build and payload identities disagree')
            comparison=reproducible['architectures'][arch]
            if comparison['binary_archive_sha256']!=sha(root/archive) or comparison['build_manifest_sha256']!=sha(root/(arch+'-build-manifest.json')):
                raise ValueError('saved reproducibility build mismatch')
            tree=unpack(root/archive,Path(temporary)/arch,stem+'-linux-'+arch,inventory,epoch=record['source_date_epoch'])
            if (tree/'share/doc/brewpi-emulator-rmx/LICENSE.md').read_bytes()!=(source/'LICENSE.md').read_bytes():raise ValueError('saved payload license differs from source')
    return data


def main():
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('output')
    p=sub.add_parser('runtime');p.add_argument('output');p.add_argument('architecture',choices=['arm64','amd64'])
    p=sub.add_parser('seal');p.add_argument('output');p.add_argument('destination')
    p=sub.add_parser('verify');p.add_argument('destination');p.add_argument('--expected-version')
    args=parser.parse_args()
    try:
        if args.action=='prepare':prepare(args.output)
        elif args.action=='runtime':runtime(args.output,args.architecture)
        elif args.action=='seal':seal(args.output,args.destination)
        else:verify_freeze(args.destination,expected_version=args.expected_version)
    except BaseException:
        # Never turn a failed attempt into a frozen candidate or reuse its path.
        raise


if __name__=='__main__':main()
