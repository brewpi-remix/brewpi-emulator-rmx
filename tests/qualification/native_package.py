# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Run existing package workflows in private native Linux namespaces.

The caller stages source, payload, manifest, pinned references, and a disposable
external tool filesystem. No live prefix, account, service, or reference is edited.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def command(*args):
    subprocess.run(list(map(str,args)),check=True,timeout=120)


def ctest_command(directory, arguments):
    if directory=='/qualification/build-sanitize':
        return ['/usr/bin/setarch','x86_64','-R','/usr/bin/ctest',*arguments]
    return ['/usr/bin/ctest',*arguments]


def validate_request(base, wrapper, role, expected_version=None):
    request=json.loads((base/'request.json').read_text())
    sys.path.insert(0,str(base/'source/tests/ci'))
    from version import application_version, checked_version
    expected_version=checked_version(expected_version if expected_version is not None else request.get('candidate_version'))
    if request.get('candidate_version')!=expected_version or application_version(base/'source')!=expected_version:
        raise ValueError('requested version differs from staged source metadata')
    raw=(base/'candidate.json').read_bytes();manifest=json.loads(raw)
    source=json.loads((base/'source/SOURCE.json').read_text())
    if source.get('version')!=expected_version:raise ValueError('staged source record version differs from request')
    snapshot=manifest.get('source_snapshot_sha256')
    commit=source.get('base_commit')
    if not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('invalid staged source commit')
    claimed=request.get('source_commit')
    if not isinstance(claimed,str) or len(claimed)!=40 or any(c not in '0123456789abcdef' for c in claimed):
        raise ValueError('invalid requested commit claim')
    if not isinstance(snapshot,str) or len(snapshot)!=64 or any(c not in '0123456789abcdef' for c in snapshot):
        raise ValueError('invalid staged source identity')
    if request.get('manifest_sha256')!=hashlib.sha256(raw).hexdigest() or request.get('native_wrapper_sha256')!=hashlib.sha256(wrapper.read_bytes()).hexdigest():
        raise ValueError('staged manifest or wrapper differs from request')
    if manifest.get('candidate_version')!=expected_version or manifest.get('architecture')!='amd64' or manifest.get('schema')!=2:
        raise ValueError('wrong staged candidate version or architecture')
    if request.get('source_snapshot_sha256')!=snapshot or source.get('source_snapshot_sha256')!=snapshot or manifest.get('base_commit')!=source.get('base_commit'):
        raise ValueError('requested and staged source identities disagree')
    scoped=request.get('sanitizer_process_no_aslr',False)
    if type(scoped) is not bool or (scoped and role!='qualification'):
        raise ValueError('sanitizer setting requires an explicit qualification boolean')
    return request


def inside(base, role):
    if os.geteuid()!=0 or os.getpid()!=1:
        raise RuntimeError('private root-provisioned PID namespace required')
    folder=base/role;root=folder/'rootfs'
    sanitizer_scope=role=='qualification' and json.loads((base/'request.json').read_text()).get('sanitizer_process_no_aslr') is True
    if sanitizer_scope:
        private=root/'opt/package-test';private.mkdir()
        (private/'native_package.py').write_bytes(Path(__file__).read_bytes())
        shim=private/'ctest'
        shim.write_text('#!/usr/bin/python3\n# Copyright 2026 Lee Bussy\n# SPDX-License-Identifier: MIT\nimport os,sys\nsys.path.insert(0,"/opt/package-test")\nfrom native_package import ctest_command\ncommand=ctest_command(os.getcwd(),sys.argv[1:])\nif command[0].endswith("setarch"): print("Sanitizer-only process ASLR workaround; host policy unchanged",flush=True)\nos.execv(command[0],command)\n')
        shim.chmod(0o755)
    command('mount','--make-rprivate','/')
    for source,target in [(base/'source','work'),(base/'payload','payload'),
                          (base/'candidate.json','candidate.json'),(base/'refs','refs')]:
        destination=root/target
        command('mount','--bind',source,destination)
        command('mount','-o','remount,bind,ro',destination)
    for name in ['lab','evidence']:
        command('mount','--bind',folder/name,root/name)
    command('mount','-t','proc','-o','nosuid,nodev,noexec','proc',root/'proc')
    command('mount','-t','tmpfs','-o','mode=755,nosuid','tmpfs',root/'dev')
    (root/'dev/pts').mkdir()
    command('mount','-t','devpts','-o','newinstance,ptmxmode=0666,mode=0620,gid=5','devpts',root/'dev/pts')
    (root/'dev/ptmx').symlink_to('pts/ptmx')
    for name in ['null','zero','random','urandom','tty']:
        destination=root/'dev'/name;destination.touch()
        command('mount','--bind','/dev/'+name,destination)
    (root/'dev/fd').symlink_to('/proc/self/fd')
    (root/'dev/shm').mkdir()
    command('mount','-t','tmpfs','-o','mode=1777,size=256m,nosuid,nodev','tmpfs',root/'dev/shm')
    for name in ['tmp','qualification']:
        command('mount','-t','tmpfs','-o','mode=1777,nosuid,nodev','tmpfs',root/name)
    if role=='runtime':
        command('mount','--bind',base/'payload',root/'usr/local')
        command('mount','-o','remount,bind,ro',root/'usr/local')
        results=root/'qualification/results';results.mkdir()
        command('mount','--bind',folder/'evidence',results)
        os.chown(root/'qualification',2001,2001)
        os.chown(folder/'evidence',2001,2001)
    command('ip','link','set','lo','up')
    write(folder/'namespace.json',dict(pid_namespace=os.readlink('/proc/self/ns/pid'),
          host_machine=platform.machine(),private_network=True,private_mounts=True,
          private_tool_filesystem=True,source_payload_references_readonly=True,
          physical_devices=False,systemd_activation=False,sanitizer_process_no_aslr=sanitizer_scope))
    os.chroot(root);os.chdir('/lab')
    # Fail before builds if a smaller soak-only tool filesystem was supplied.
    if role!='runtime':
        command('/bin/sh','-c','command -v php && command -v chromium && command -v systemd-analyze && command -v cmake && command -v c++')
    # The external tools image already has this test account. Remove it only
    # inside this private copy; the original workflows create their own account.
    if any(row.startswith('brewpi:') for row in Path('/etc/passwd').read_text().splitlines()):
        command('/usr/sbin/userdel','brewpi')
    if any(row.startswith('brewpi:') for row in Path('/etc/group').read_text().splitlines()):
        command('/usr/sbin/groupdel','brewpi')
    manifest=json.loads(Path('/candidate.json').read_text())
    env=dict(PATH='/opt/brewpi-test/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',HOME='/tmp',
        TZ='UTC',LC_ALL='C',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
        RMX_EXECUTION_MODE='packaged-input',RMX_PAYLOAD_ROOT='/payload',RMX_PAYLOAD_MANIFEST='/candidate.json',
        RMX_CANDIDATE_SNAPSHOT=manifest['source_snapshot_sha256'],RMX_TARGET_ARCH=manifest['architecture'],
        RMX_DISPOSABLE_QUALIFICATION='1')
    if sanitizer_scope:env['PATH']='/opt/package-test:'+env['PATH']
    script='/work/tests/'+('integration/run.py' if role=='integration' else 'qualification/prepare.py')
    if role=='runtime':
        env.update(RMX_PAYLOAD_ROOT='/usr/local',RMX_PAYLOAD_RECEIPT='/qualification/results/payload-execution.jsonl')
        os.setgroups([]);os.setgid(2001);os.setuid(2001)
        os.execve('/usr/bin/python3',['python3','/work/release/runtime.py','/usr/local/bin/brewpi-emulator-rmx'],env)
    os.execve('/opt/brewpi-test/bin/python3',['python3','-u',script],env)


def launch(base, role):
    if os.geteuid()!=0 or base.is_symlink() or not base.is_dir() or base.stat().st_uid==0:
        raise RuntimeError('explicit user-owned private staging directory required')
    request=json.loads((base/'request.json').read_text())
    if request.get('purpose')!='native packaged qualification' or request.get('architecture')!='amd64' or platform.machine()!='x86_64':
        raise RuntimeError('explicit native x86-64 request required')
    request=validate_request(base,Path(__file__),role)
    folder=base/role;folder.mkdir()
    root=folder/'rootfs'
    started=time.time();process=None;error=None;remaining=[];namespace=None
    handlers={sig:signal.getsignal(sig) for sig in [signal.SIGTERM,signal.SIGINT]}
    def interrupted(number,frame):raise RuntimeError('operator interruption')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        command('cp','-a','--reflink=auto',(base/'tools').resolve(),root)
        for name in ['work','payload','refs','lab','evidence','qualification']:
            (root/name).mkdir(exist_ok=True)
        (root/'candidate.json').touch(exist_ok=True)
        for name in ['lab','evidence']:(folder/name).mkdir()
        os.sched_setaffinity(0,{max(os.sched_getaffinity(0))});os.nice(10)
        with (folder/'namespace.log').open('xb') as log:
            process=subprocess.Popen(['unshare','--mount','--pid','--fork','--kill-child=SIGTERM',
                '--net','--ipc','--uts',sys.executable,str(Path(__file__).resolve()),'inside',str(base),role],
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:exit_code=process.wait(timeout=7200)
            except subprocess.TimeoutExpired:raise RuntimeError('native package workflow deadline')
        if exit_code:raise RuntimeError('namespace workflow exit '+str(exit_code))
    except BaseException as exc:error=repr(exc)
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.signal(signal.SIGINT,signal.SIG_IGN)
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
        metadata=folder/'namespace.json'
        if metadata.exists():
            namespace=json.loads(metadata.read_text())['pid_namespace']
            for path in Path('/proc').iterdir():
                if path.name.isdigit():
                    try:
                        if os.readlink(path/'ns/pid')==namespace:remaining.append(int(path.name))
                    except OSError:pass
        clean=process is None or (namespace is not None and not remaining)
        if not clean:error=error or 'owned namespace cleanup unverified'
        result=dict(status='passed' if error is None else 'failed',role=role,
            architecture='amd64',candidate_version=request['candidate_version'],native_machine=platform.machine(),started_utc=started,finished_utc=time.time(),
            exit_code=process.returncode if process else None,error=error,cleanup_verified=clean,
            remaining_owned_pids=remaining,source_snapshot_sha256=request['source_snapshot_sha256'])
        result['sanitizer_process_no_aslr']=role=='qualification' and request.get('sanitizer_process_no_aslr') is True
        write(folder/'native-launcher.json',result)
        for sig,handler in handlers.items():signal.signal(sig,handler)
    return 0 if error is None else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','inside'])
    parser.add_argument('base',type=Path);parser.add_argument('role',choices=['integration','qualification','runtime'])
    args=parser.parse_args();base=args.base.absolute()
    if args.action=='inside':inside(base,args.role)
    else:raise SystemExit(launch(base,args.role))
