# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original isolated test orchestration; reference applications stay external."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import socket
import hashlib
import importlib.metadata
import subprocess
import threading
import tempfile
import time
import tty
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_inputs import inventory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
from payload import selected, sha, preflight
from native import save_execution, copy_test_log

LAB = Path('/lab')
EVIDENCE = Path('/evidence')


def wait_until(fn, timeout=30, message='condition'):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = fn()
            if value:
                return value
        except (OSError, ValueError, KeyError) as exc:
            last = str(exc)
        time.sleep(.1)
    raise AssertionError(f'timed out: {message}: {last}')


class WireTap:
    """Byte-transparent PTY relay; never synthesizes a controller response."""
    def __init__(self, source, session):
        self.session = session
        self.fd = os.open(source, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(self.fd)
        self.master, self.slave = pty.openpty()
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        self.path = LAB / 'host-serial'
        self.path.symlink_to(os.ttyname(self.slave))
        self.closed = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            with (EVIDENCE / 'wire.jsonl').open('a') as capture:
                while not self.closed.is_set():
                    for fd in select.select([self.fd, self.master], [], [], .1)[0]:
                        data = os.read(fd, 65536)
                        if not data:
                            continue
                        capture.write(json.dumps(dict(session=self.session,monotonic=time.monotonic(),
                            direction='controller' if fd == self.fd else 'host', hex=data.hex()))+'\n')
                        capture.flush()
                        destination = self.master if fd == self.fd else self.fd
                        view = memoryview(data)
                        while view and not self.closed.is_set():
                            if not select.select([], [destination], [], .1)[1]:
                                continue
                            try:
                                view = view[os.write(destination, view):]
                            except BlockingIOError:
                                pass
        except Exception as exc:
            self.error = repr(exc)

    def close(self):
        if getattr(self,"disposed",False):
            return
        self.disposed=True
        self.closed.set()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive(), "relay did not stop"
        for fd in [self.fd, self.master, self.slave]:
            os.close(fd)
        self.path.unlink(missing_ok=True)
        assert self.error is None, self.error


class Lab:
    def __init__(self):
        self.host = self.php = self.emulator = self.tap = None
        self.logs = []
        self.code_hashes = {}
        self.source_root=Path('/work')
        self.source_hashes={}
        self.session = 0
        self.disposed = False
        self.host_exits = []
        self.payload = None
        self.executable = "/lab/build/brewpi-emulator-rmx"
        self.binary_hash = None

    def spawn(self, args, name, cwd=None):
        log = (EVIDENCE / (name+'.log')).open('ab', buffering=0)
        self.logs.append(log)
        return subprocess.Popen(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)

    @staticmethod
    def clone_reference(source, destination):
        # The caller verifies the frozen HEAD first. Trust only the two exact
        # paths of that read-only mounted checkout inside this disposable guest.
        with tempfile.TemporaryDirectory(prefix='rmx-reference-git-') as temporary:
            config=Path(temporary)/'gitconfig'
            for trusted in [source,source+'/.git']:
                subprocess.run(['git','config','--file',str(config),'--add','safe.directory',trusted],check=True)
            # Git's nested upload-pack does not retain clone's -c options.
            # A private protected-config file reaches that child without
            # changing the host or guest's ordinary global Git configuration.
            subprocess.run(['git','clone','--no-hardlinks',source,str(destination)],
                           check=True,env=dict(os.environ,GIT_CONFIG_GLOBAL=str(config)))
        # The pinned host queries active_branch during startup. A private clone
        # of a detached frozen ref needs ordinary branch metadata, with the
        # exact same HEAD and tracked bytes; the read-only source is untouched.
        subprocess.run(['git','-C',str(destination),'checkout','-B','main','HEAD'],check=True)

    def prepare(self):
        preflight()
        self.payload = selected()
        LAB.mkdir(exist_ok=True)
        EVIDENCE.mkdir(exist_ok=True)
        self.source_hashes=inventory(self.source_root)
        (EVIDENCE/'source-inventory.json').write_text(json.dumps(self.source_hashes,indent=2)+'\n')
        with (EVIDENCE/'helper-checks.log').open('w') as output:
            subprocess.run(['python3','/work/tests/integration/checks.py'],check=True,
                           stdout=output,stderr=subprocess.STDOUT)
        pins = {'/refs/script':'d183fb5319b928f78b4c0eb6f05fe3620610ffff',
                '/refs/panel':'f79631830a99575e250403f08a19be8bf944596c'}
        self.code_hashes = {}
        for source, destination in [('/refs/script', 'host'), ('/refs/panel', 'www')]:
            revision = subprocess.check_output(['git','-c',f'safe.directory={source}',
                '-C',source,'rev-parse','HEAD'],text=True).strip()
            assert revision == pins[source], (source,revision)
            self.clone_reference(source,LAB/destination)
        self.mutable_reference_inputs = {'host/settings/tempProfile.csv'}
        for folder in ['host','www']:
            clone=LAB/folder
            files=subprocess.check_output(['git','-C',str(clone),'ls-files','-z']).decode().split('\0')[:-1]
            for name in files:
                path=clone/name
                if str(path.relative_to(LAB)) not in self.mutable_reference_inputs:
                    self.code_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        (EVIDENCE/'reference-baseline.json').write_text(json.dumps(dict(
            hashes=self.code_hashes,allowed_runtime_inputs=sorted(self.mutable_reference_inputs)),indent=2)+'\n')
        subprocess.run(['groupadd', '-f', 'brewpi'], check=True)
        subprocess.run(['useradd', '-r', '-g', 'brewpi', 'brewpi'], check=True)
        (LAB/'tools').mkdir()
        (LAB/'host/logs').mkdir(exist_ok=True)
        (LAB/'www/config_user.php').write_text("<?php\n$scriptPath = '/lab/host';\n")
        (LAB/'host/settings/config.cfg').write_text('''chamber = IntegrationTest
scriptPath = /lab/host/
wwwPath = /lab/www/
toolPath = /lab/tools/
port = /lab/host-serial
altport = None
startupDelay = 0
interval = 10
beerName = IntegrationTest
dataLogging = active
logJson = True
''')
        subprocess.run(['cmake', '-S', '/work', '-B', '/lab/build',
                        '-DCMAKE_BUILD_TYPE=Debug'], check=True)
        subprocess.run(['cmake', '--build', '/lab/build', '-j4'], check=True)
        subprocess.run(['ctest','-T','Test','--output-on-failure'],cwd='/lab/build',check=True)
        save_execution('/lab/build','debug')
        copy_test_log('/lab/build',EVIDENCE/'native-tests.log')
        shutil.copytree('/lab/build/test-results',EVIDENCE/'native-test-results',dirs_exist_ok=True)
        if self.payload:
            self.executable = str(self.payload.binary)
            self.payload.verify('before-integration',EVIDENCE/'payload-execution.jsonl')
        self.binary_hash = sha(self.executable)
        (EVIDENCE/'execution-input.json').write_text(json.dumps(dict(
            mode='packaged-input' if self.payload else 'source-build',executable=self.executable,
            sha256=self.binary_hash,native_driver_scope='separate source-build checks'))+'\n')
        versions = subprocess.check_output(['sh', '-c',
            'python3 --version; php --version; chromium --version; c++ --version; cmake --version; pip freeze'], text=True)
        (EVIDENCE/'tool-versions.txt').write_text(versions)
        packages = [dict(name=d.metadata['Name'],version=d.version,
                        license=d.metadata.get('License'),
                        license_expression=d.metadata.get('License-Expression'))
                    for d in importlib.metadata.distributions()]
        (EVIDENCE/'package-metadata.json').write_text(json.dumps(packages,indent=2)+'\n')
        with (EVIDENCE/'php-modules.txt').open('w') as target:
            subprocess.run(['php','-m'],stdout=target,check=True)

    def start_emulator(self, speed=1, resume=False):
        if self.payload:
            self.payload.verify('restart-'+str(self.session+1),EVIDENCE/'payload-execution.jsonl')
        assert sha(self.executable)==self.binary_hash,'executable substituted before restart'
        with (EVIDENCE/'executable-hashes.jsonl').open('a') as output:
            output.write(json.dumps(dict(phase='restart-'+str(self.session+1),sha256=sha(self.executable)))+'\n')
        args = [self.executable, '--serial', '/lab/emulator-serial',
                '--state', '/lab/controller.json', '--checkpoint', '/lab/checkpoint.json',
                '--speed', str(speed)]
        if resume:
            args += ['--resume', '/lab/checkpoint.json']
        self.emulator = self.spawn(args, 'emulator')
        wait_until(lambda: (LAB/'emulator-serial').is_symlink(), message='emulator PTY')
        self.session += 1
        self.tap = WireTap('/lab/emulator-serial',self.session)

    def start_host(self):
        self.host = self.spawn(['python3', '-u', '/lab/host/brewpi.py', '-c',
                                '/lab/host/settings/config.cfg', '-l'], 'host', '/lab/host')
        wait_until(lambda: (LAB/'host/BEERSOCKET').exists(), message='host socket')

    def start_panel(self):
        self.php = self.spawn(['php', '-S', '127.0.0.1:8080', '-t', '/lab/www'], 'php', '/lab/www')

    @staticmethod
    def stop_process(proc):
        if proc is None or proc.poll() is not None:
            return
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)

    def stop_host(self):
        if self.host and self.host.poll() is None:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                    conn.settimeout(2)
                    conn.connect(str(LAB/'host/BEERSOCKET'))
                    conn.sendall(b'quit')
                self.host.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.stop_process(self.host)
        if self.host:
            self.host_exits.append(self.host.returncode)
            if (LAB/'host/logs').exists():
                shutil.copytree(LAB/'host/logs',EVIDENCE/'host-logs'/('session-'+str(self.session)),dirs_exist_ok=True)
        self.host = None
        time.sleep(.2)

    def audit_references(self):
        changed=[name for name,digest in self.code_hashes.items()
                 if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]
        report=dict(unchanged=bool(self.code_hashes) and not changed,checked_files=len(self.code_hashes),changed=changed,
                    allowed_runtime_inputs=sorted(getattr(self,'mutable_reference_inputs',[])))
        (EVIDENCE/'reference-code-integrity.json').write_text(json.dumps(report,indent=2)+'\n')
        if not self.code_hashes:
            raise AssertionError("no reference baseline was recorded")
        if changed:
            raise AssertionError('reference files changed: '+repr(changed))

    def audit_source(self):
        unchanged=bool(self.source_hashes) and inventory(self.source_root)==self.source_hashes
        (EVIDENCE/'source-integrity.json').write_text(json.dumps(dict(
            status='passed' if unchanged else 'failed',files=len(self.source_hashes),unchanged=unchanged),indent=2)+'\n')
        assert unchanged,'original source inputs changed or no baseline was recorded'

    def close(self):
        if self.disposed:
            return
        self.disposed=True
        failures=[]
        def attempt(label, operation):
            try:
                operation()
            except Exception as exc:
                failures.append(label+': '+repr(exc))
        attempt('host shutdown',self.stop_host)
        attempt('PHP shutdown',lambda:self.stop_process(self.php))
        attempt('emulator shutdown',lambda:self.stop_process(self.emulator))
        if self.emulator and self.emulator.returncode!=0:
            failures.append('unexpected emulator exit: '+str(self.emulator.returncode))
        if any(code!=0 for code in self.host_exits):
            failures.append('unexpected host exits: '+repr(self.host_exits))
        if self.tap:
            attempt('relay shutdown',self.tap.close)
        def collect():
            for name in ['controller.json','checkpoint.json']:
                if (LAB/name).exists():
                    shutil.copyfile(LAB/name,EVIDENCE/name)
            for source,destination in [('host/data/IntegrationTest','host-data/IntegrationTest'),
                                       ('www/data/IntegrationTest','web-data/IntegrationTest')]:
                if (LAB/source).exists():
                    shutil.copytree(LAB/source,EVIDENCE/destination,dirs_exist_ok=True)
        attempt('evidence collection',collect)
        attempt('reference integrity',self.audit_references)
        attempt('original source integrity',self.audit_source)
        if self.payload:
            attempt('payload integrity',lambda:self.payload.verify('after-integration',EVIDENCE/'payload-execution.jsonl'))
        if self.binary_hash:
            def binary_unchanged():
                assert sha(self.executable)==self.binary_hash,'executable changed during execution'
                with (EVIDENCE/'executable-hashes.jsonl').open('a') as output:
                    output.write(json.dumps(dict(phase='after-integration',sha256=sha(self.executable)))+'\n')
            attempt('executable integrity',binary_unchanged)
        for log in self.logs:
            attempt('log close',log.close)
        (EVIDENCE/'cleanup-results.json').write_text(json.dumps(dict(
            status='failed' if failures else 'passed',errors=failures,host_exits=self.host_exits),indent=2)+'\n')
        if failures:
            raise AssertionError('; '.join(failures))
