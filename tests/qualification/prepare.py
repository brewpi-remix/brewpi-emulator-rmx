# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Build, inspect, and exercise only the agreed disposable Linux ARM64 target."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import traceback
from service import exercise
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_inputs import inventory as source_inventory

ROOT=Path('/qualification')
OUT=Path('/evidence')
PREFIX=Path('/opt/brewpi-emulator-rmx')


def command(args,name=None,**kwargs):
    result=subprocess.run(args,capture_output=True,text=True,**kwargs)
    if name:
        (OUT/name).write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}')
    return result.stdout


def main():
    checks=[]
    try:
        release=Path('/etc/os-release').read_text()
        assert 'VERSION_ID="12"' in release and 'ID=debian' in release
        assert platform.machine()=='aarch64'
        before=source_inventory(Path('/work'))
        (OUT/'source-inventory.json').write_text(json.dumps(before,indent=2)+'\n')
        ROOT.mkdir(exist_ok=True)
        command(['groupadd','--gid','2001','brewpi'])
        command(['useradd','--uid','2001','--gid','2001','--no-create-home','--shell','/usr/sbin/nologin','brewpi'])
        for name in ['runtime','results']:
            path=ROOT/name
            if name=='results':path.mkdir()
            if path.exists():os.chown(path,2001,2001)
        # The unprivileged runtime owns its parent and creates the private test tree.
        os.chown(ROOT,2001,2001)
        os.chmod(ROOT,0o755)
        command(['runuser','-u','brewpi','--',sys.executable,'/work/tests/qualification/checks.py'],'readiness-checks.log')
        versions=command(['sh','-c','uname -a; cat /etc/os-release; c++ --version; cmake --version; python3 --version; systemd-analyze --version; dpkg-query -W libc6 libstdc++6 libgcc-s1 binutils make systemd'])
        (OUT/'target-environment.txt').write_text(versions)
        for kind,extra in [('release',[]),('sanitize',['-DRMX_SANITIZERS=ON'])]:
            build=ROOT/('build-'+kind)
            command(['cmake','-S','/work','-B',str(build),
                '-DCMAKE_BUILD_TYPE='+('Release' if kind=='release' else 'Debug'),
                '-DCMAKE_INSTALL_PREFIX='+str(PREFIX)]+extra,'configure-'+kind+'.log')
            command(['cmake','--build',str(build),'-j4'],'build-'+kind+'.log')
            command(['chown','-R','2001:2001',str(build)])
            try:
                command(['runuser','-u','brewpi','--','ctest','--test-dir',str(build),'--output-on-failure'],
                        'ctest-'+kind+'.log',timeout=300)
            finally:
                if (build/'test-results').exists():
                    shutil.copytree(build/'test-results',OUT/('native-'+kind),dirs_exist_ok=True)
            checks.append(dict(name='unprivileged '+kind+' native suites',status='passed',suites=6))
        stage=ROOT/'stage'
        env=dict(os.environ,DESTDIR=str(stage))
        command(['cmake','--install',str(ROOT/'build-release')],'install.log',env=env)
        tree=stage/PREFIX.relative_to('/')
        expected={'bin/brewpi-emulator-rmx','libexec/brewpi-emulator-rmx/wait-ready.py',
                  'share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service',
                  'share/doc/brewpi-emulator-rmx/LICENSE.md',
                  'share/doc/brewpi-emulator-rmx/THIRD_PARTY_NOTICES.md',
                  'share/doc/brewpi-emulator-rmx/operation.txt'}
        actual={str(p.relative_to(tree)) for p in tree.rglob('*') if p.is_file()}
        assert actual==expected,(actual,expected)
        inventory=[]
        for relative in sorted(actual):
            p=tree/relative
            assert not p.is_symlink()
            inventory.append(dict(path=relative,bytes=p.stat().st_size,mode=oct(p.stat().st_mode&0o777),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        assert (tree/'share/doc/brewpi-emulator-rmx/LICENSE.md').read_bytes()==Path('/work/LICENSE.md').read_bytes()
        (OUT/'install-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
        # Install only into this disposable container to validate generated absolute paths.
        shutil.copytree(tree,PREFIX,dirs_exist_ok=True)
        binary=PREFIX/'bin/brewpi-emulator-rmx'
        command(['readelf','-h',str(binary)],'elf-header.txt')
        dependencies=command(['ldd',str(binary)],'dynamic-libraries.txt')
        assert 'not found' not in dependencies
        assert 'AArch64' in (OUT/'elf-header.txt').read_text()
        for line in dependencies.splitlines():
            if '=>' in line:
                name=line.strip().split()[0]
                assert name in ['libstdc++.so.6','libm.so.6','libgcc_s.so.1','libc.so.6'],name
        dynamic=command(['readelf','-d',str(binary)],'elf-dynamic.txt')
        needed=set(re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic))
        assert needed and needed<={'libstdc++.so.6','libm.so.6','libgcc_s.so.1','libc.so.6'},needed
        assert '(RPATH)' not in dynamic and '(RUNPATH)' not in dynamic
        for package in ['libc6','libstdc++6','libgcc-s1']:
            shutil.copyfile('/usr/share/doc/'+package+'/copyright',OUT/(package+'-copyright.txt'))
        # BUILD_SHARED_LIBS must not create an uninstalled project-library dependency.
        shared=ROOT/'build-shared-option'
        command(['cmake','-S','/work','-B',str(shared),'-DCMAKE_BUILD_TYPE=Release',
                 '-DBUILD_TESTING=OFF','-DBUILD_SHARED_LIBS=ON','-DCMAKE_INSTALL_PREFIX='+str(PREFIX)],'configure-shared-option.log')
        command(['cmake','--build',str(shared),'-j4'],'build-shared-option.log')
        shared_stage=ROOT/'stage-shared-option'
        command(['cmake','--install',str(shared)],'install-shared-option.log',env=dict(os.environ,DESTDIR=str(shared_stage)))
        shared_binary=shared_stage/PREFIX.relative_to('/')/'bin/brewpi-emulator-rmx'
        shared_deps=command(['ldd',str(shared_binary)],'shared-option-libraries.txt')
        assert 'not found' not in shared_deps and 'librmx_protocol' not in shared_deps
        assert command([str(shared_binary),'--version']).strip()=='brewpi-emulator-rmx 0.1.0 (development)'
        version=command([str(binary),'--version'],'application-version.txt')
        assert version.strip()=='brewpi-emulator-rmx 0.1.0 (development)'
        unit=PREFIX/'share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service'
        command(['systemd-analyze','verify','--man=no',str(unit)],'service-verify.log')
        service=exercise(unit,OUT)
        assert service['status']=='passed'
        checks.append(dict(name='staged install and service syntax',status='passed',installed_files=len(inventory),
                           real_systemd_activation=False,unit=str(unit.relative_to(PREFIX))))
        command(['runuser','-u','brewpi','--',sys.executable,'/work/tests/qualification/runtime.py',str(binary)],
                'runtime.log',timeout=180)
        shutil.copytree(ROOT/'results',OUT/'runtime-results',dirs_exist_ok=True)
        runtime=json.loads((ROOT/'results/runtime-results.json').read_text())
        assert runtime['status']=='passed'
        # Other unprivileged accounts must not traverse this instance's private paths.
        private=ROOT/'runtime/ownership'
        test=command(['runuser','-u','nobody','--',sys.executable,'-c',
            'import os,sys\ntry:os.open(sys.argv[1],os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)\nexcept PermissionError:print("denied")\nelse:raise SystemExit("unexpected access")',str(private/'serial.lock')])
        assert test.strip()=='denied'
        checks.append(dict(name='foreign-account isolation',status='passed'))
        after=source_inventory(Path('/work'))
        integrity=dict(status='passed' if after==before else 'failed',files=len(before),unchanged=after==before)
        (OUT/'source-integrity.json').write_text(json.dumps(integrity,indent=2)+'\n')
        assert after==before,'source inputs changed during qualification'
        (OUT/'qualification-results.json').write_text(json.dumps(dict(status='passed',
            agreed_target='isolated Debian 12 ARM64 Linux container',checks=checks,runtime=runtime,
            physical_pi_qualified=False,systemd_pid1_activation_qualified=False,
            unresolved_reference_characterization=9),indent=2)+'\n')
    except BaseException:
        (OUT/'qualification-results.json').write_text(json.dumps(dict(status='failed',checks=checks,error=traceback.format_exc()),indent=2)+'\n')
        if (ROOT/'results').exists():shutil.copytree(ROOT/'results',OUT/'runtime-results',dirs_exist_ok=True)
        raise


if __name__=='__main__':
    main()
