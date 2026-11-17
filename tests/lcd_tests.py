# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original LCD boundary, console, failure, and deterministic process regressions."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time

ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(.02)
    raise AssertionError('LCD test deadline expired')


class Process:
    def __init__(self, exe, root, mode, env=None, terminal=True, extra=(), inherited=()):
        root.mkdir()
        self.root, self.buffer = root, b''
        self.master = self.slave = self.serial = None
        options = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                       pass_fds=inherited)
        if terminal:
            self.master, self.slave = pty.openpty()
            fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 80, 0, 0))
            def setup():
                os.setsid()
                fcntl.ioctl(self.slave, termios.TIOCSCTTY, 0)
            options.update(stdin=self.slave, preexec_fn=setup)
        else:
            options.update(stdin=subprocess.DEVNULL, start_new_session=True)
        self.checkpoint = root / 'checkpoint.json'
        self.proc = subprocess.Popen([exe, '--serial', str(root / 'serial'), '--state',
                                      str(root / 'state.json'), '--speed', '0',
                                      '--checkpoint', str(self.checkpoint), '--lcd', mode,
                                      *extra], **options)
        try:
            wait_for(lambda: (root / 'serial').is_symlink() or self.proc.poll() is not None)
            assert self.proc.poll() is None, self.proc.communicate()
            self.serial = os.open(root / 'serial', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            self.wire = b''
            if '--resume' not in extra:
                self.line()
        except BaseException:
            self.close(check=False)
            raise

    def line(self):
        wait_for(lambda: b'\r\n' in self.wire or self.read_serial())
        line, self.wire = self.wire.split(b'\r\n', 1)
        return line

    def read_serial(self):
        if select.select([self.serial], [], [], 0)[0]:
            self.wire += os.read(self.serial, 65536)
        return b'\r\n' in self.wire

    def command(self, command):
        os.write(self.serial, command)
        return self.line()

    def console(self):
        if self.master is not None:
            while select.select([self.master], [], [], 0)[0]:
                try:
                    data = os.read(self.master, 65536)
                    if not data:
                        break
                    self.buffer += data
                except OSError:
                    break
        return self.buffer

    def close(self, check=True):
        self.console()
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            # macOS may hold a controlling-PTY session leader in kernel exit
            # until its terminal output is consumed. Act as a real terminal
            # emulator while reaping instead of leaving that private PTY unread.
            end = time.monotonic() + 5
            while self.proc.poll() is None and time.monotonic() < end:
                self.console()
                time.sleep(.01)
            out, err = self.proc.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            out, err = self.proc.communicate(timeout=3)
            raise AssertionError(('emulator cleanup stalled', out, err))
        finally:
            self.console()
            for fd in (self.master, self.slave, self.serial):
                if fd is not None:
                    os.close(fd)
            self.master = self.slave = self.serial = None
        if check:
            assert self.proc.returncode == 0, (out, err)
            assert not (self.root / 'serial').is_symlink()
        return err


def decoder_checks():
    spec = importlib.util.spec_from_file_location('lcd_viewer', ROOT / 'scripts/lcd-viewer.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    good = dict(version=2, type='frame', sequence=1,
                dim=False, door=False, status='Ready', session='test', epoch=0,
                rows=['Mode   Beer Const.  ', 'Beer   20.0  20.0 °C',
                      'Fridge 19.5  19.0 °C', 'Cooling for    03m12'])
    assert module.decode(json.dumps(good).encode()) == good
    bad = [b'', b'x' * 4097, b'\xff', b'{}', b'{"version":2,"version":2,"type":"heartbeat"}']
    for patch in [dict(version=True), dict(version=3), dict(sequence=0),
                  dict(sequence=True), dict(sequence=2**53), dict(rows=[' ' * 19] * 4),
                  dict(rows=['\x1b' + ' ' * 19] * 4), dict(rows=['界' * 20] * 4), dict(extra=1)]:
        bad.append(json.dumps(dict(good, **patch)).encode())
    for values in ([0, 1, 0, -1], [1, 0, 1, 0]):
        assert module.decode(json.dumps(dict(good, equipment=values)).encode())['equipment'] == values
    for values in (None, {}, [], [0]*3, [0]*5, [True, 0, 0, 0], [2, 0, 0, 0], [-2, 0, 0, 0], ['0', 0, 0, 0]):
        bad.append(json.dumps(dict(good, equipment=values)).encode())
    for packet in bad:
        try:
            module.decode(packet)
        except (ValueError, TypeError, UnicodeError):
            pass
        else:
            raise AssertionError(('accepted malformed GUI frame', packet))


def peer(directory):
    # An independently authored fake interpreter exercises the executable's
    # private IPC without requiring Tk or adding a production test interface.
    script = directory / 'python3'
    script.write_text('''#!/usr/bin/python3
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
import json, os, socket, time, signal, fcntl
from pathlib import Path
s=socket.socket(fileno=3)
s.settimeout(.1)
root=Path(os.environ['LCD_TEST_ROOT'])
(root/'pid').write_text(str(os.getpid()))
mode=os.environ['LCD_TEST_PEER']
try:
 fcntl.fcntl(int(os.environ['LCD_SENTINEL']),fcntl.F_GETFD)
 (root/'leaked').write_text('inherited descriptor')
except OSError: pass
if mode=='ignore':
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
if mode=='error':
 s.send(b'{"version":2,"type":"error"}')
 raise SystemExit()
if mode=='oversize':
 s.send(b'x'*4097)
 time.sleep(10)
if mode=='bad':
 s.send(b'{"version":true,"type":"ready"}')
 time.sleep(10)
if mode=='flood':
 for _ in range(32):s.send(b'{"version":2,"type":"ready"}')
 time.sleep(10)
if mode in ('startup','ignore'):
 time.sleep(30)
 raise SystemExit()
s.send(b'{"version":2,"type":"ready"}')
if mode=='hang':
 time.sleep(30)
 raise SystemExit()
if mode=='blocked':
 end=time.monotonic()+20
 while time.monotonic()<end:
  s.send(b'{"version":2,"type":"progress"}')
  time.sleep(1)
 raise SystemExit()
seen=False
next_progress=time.monotonic()
end=time.monotonic()+20
while time.monotonic()<end:
 try:
  msg=json.loads(s.recv(4097))
  if msg['type']=='frame':
   (root/'frame.json').write_text(json.dumps(msg))
   seen=True
 except socket.timeout:pass
 if time.monotonic()>=next_progress:
  s.send(b'{"version":2,"type":"progress"}')
  next_progress=time.monotonic()+1
 if mode=='close' and seen:break
 if mode in ('user-close','close-exit') and seen:
  time.sleep(.3)
  if mode=='user-close':s.send(b'{"version":2,"type":"close"}')
  raise SystemExit(10 if mode=='close-exit' else 0)
''')
    script.chmod(0o755)


def run(exe, core):
    subprocess.run([core], check=True, timeout=15)
    decoder_checks()
    checks = ['all-byte adapter, immutable shadow, deterministic engine/wire parity, strict GUI decoder']
    with tempfile.TemporaryDirectory(prefix='rmx-lcd-') as tmp:
        root = Path(tmp)
        env = dict(os.environ, LC_ALL='C.UTF-8' if sys.platform != 'darwin' else 'en_US.UTF-8',
                   TERM='xterm-256color')
        bad = subprocess.run([exe, '--serial', str(root/'bad-serial'), '--state', str(root/'bad-state'),
                              '--lcd', 'bogus'], capture_output=True, timeout=5)
        assert bad.returncode != 0 and not (root/'bad-serial.lock').exists()
        # Copy-free baseline comparisons through actual serial endpoints.
        snapshots, replies = [], []
        for mode in ('off', 'terminal', 'auto'):
            print('LCD process mode:',mode,flush=True)
            chosen = dict(env, PATH='/nonexistent') if mode == 'auto' else env
            p = Process(exe, root/mode, mode, env=chosen)
            try:
                response = [p.command(b'n'), p.command(b'l')]
                assert b'\xb0' in response[1] and b'\xc2\xb0' not in response[1]
                if mode != 'off':
                    wait_for(lambda: b'\xc2\xb0C' in p.console())
                    assert b'\xb0C' not in p.buffer.replace(b'\xc2\xb0C', b'')
                else:
                    time.sleep(.15)
                    assert p.console() == b''
                replies.append(response)
            finally:
                p.close()
            snapshots.append(json.loads(p.checkpoint.read_text())['engine'])
        assert replies[0] == replies[1] == replies[2]
        assert snapshots[0] == snapshots[1] == snapshots[2]
        checks.append('actual paused process off/terminal/auto wire and checkpoint equality; proper degree cell')
        p = Process(exe, root/'resize', 'terminal', env=env)
        try:
            wait_for(lambda: b'\xc2\xb0C' in p.console())
            p.console()
            start = len(p.buffer)
            fcntl.ioctl(p.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 6, 22, 0, 0))
            wait_for(lambda: b'23 columns' in p.console()[start:])
            assert b'\x1b' not in p.buffer[start:]
            fcntl.ioctl(p.slave, termios.TIOCSWINSZ, struct.pack('HHHH', 15, 23, 0, 0))
            start = len(p.buffer)
            wait_for(lambda: b'\xc2\xb0C' in p.console()[start:])
            assert p.command(b'n').startswith(b'N:')
        finally:
            p.close()
        for term, locale, expect in [('dumb', env['LC_ALL'], True), ('xterm', 'C', False)]:
            p = Process(exe, root/('term-'+locale.replace('.', '-')), 'terminal',
                        env=dict(env, TERM=term, LC_ALL=locale))
            try:
                time.sleep(.3)
                content = p.console()
                assert b'\x1b' not in content
                assert (b'\xc2\xb0C' in content) == expect
            finally:
                p.close()
        for profile, heater in [('revc', 5), ('i2c', 6)]:
            p = Process(exe, root/('equipment-'+profile), 'terminal', env=env,
                        extra=('--profile', profile))
            try:
                wait_for(lambda: b'Heater OFF  Cooler OFF' in p.console())
                def query(data, prefix):
                    os.write(p.serial, data)
                    while True:
                        row = p.line()
                        if row.startswith(prefix+b':'):
                            return row
                query(b'E', b'D')
                query(('U{i:3,f:2,h:1,p:%d,x:1}' % heater).encode(), b'U')
                query(b'j{mode:t}', b'S'); query(b'c', b'C')
                before = len(p.console())
                query(b'd{i:3,w:1}', b'd')
                wait_for(lambda: b'Heater ON ' in p.console()[before:])
                before = len(p.console())
                query(b'U{i:3,f:0}', b'U')
                query(b'j{mode:o}', b'S'); query(b'c', b'C')
                query(b'n', b'N')
                # The next repaint must retain the active orphan latch.
                os.write(p.master, b'door open\r')
                wait_for(lambda: b'Door   OPEN' in p.console()[before:])
                assert b'Heater ON ' in p.console()[before:]
                before = len(p.console())
                query(('U{i:3,f:2,h:1,p:%d,x:1}' % heater).encode(), b'U')
                wait_for(lambda: b'Heater OFF' in p.console()[before:])
            finally:
                p.close()
        checks.append('both-profile paused terminal equipment repaint, orphan latch, restoration, and physical door')
        p = Process(exe, root/'headless', 'terminal', env=env, terminal=False)
        try:
            assert p.command(b'n').startswith(b'N:')
        finally:
            p.close()
        checks.append('resize suspension/recovery, dumb terminal snapshots, non-UTF-8 and absent-terminal fallback')
        bindir = root/'bin'; bindir.mkdir(); peer(bindir)
        original = os.open(root/'sentinel', os.O_CREAT | os.O_RDWR, 0o600)
        sentinel = fcntl.fcntl(original, fcntl.F_DUPFD, 40)
        os.close(original)
        try:
            for scenario in ('active', 'close', 'error', 'bad', 'oversize', 'flood', 'startup', 'hang', 'ignore', 'blocked'):
                print('LCD GUI scenario:',scenario,flush=True)
                directory = root/('gui-'+scenario)
                chosen = dict(env, PATH=str(bindir), LCD_TEST_ROOT=str(directory),
                              LCD_TEST_PEER=scenario, LCD_SENTINEL=str(sentinel))
                p = Process(exe, directory, 'gui', env=chosen, inherited=(sentinel,))
                try:
                    wait_for(lambda: (directory/'pid').exists())
                    assert not (directory/'leaked').exists()
                    if scenario == 'active':
                        wait_for(lambda: (directory/'frame.json').exists())
                        item = json.loads((directory/'frame.json').read_text())
                        assert len(item['rows']) == 4 and item['rows'][1][18] == '°'
                        assert item['equipment'] == [0, 0, 0, 0]
                        def query(data, prefix):
                            os.write(p.serial, data)
                            while True:
                                line = p.line()
                                if line.startswith(prefix+b':'):return line
                        query(b'E', b'D')
                        query(b'U{i:3,f:2,h:1,p:5,x:1}', b'U')
                        query(b'j{mode:t}', b'S'); query(b'c', b'C')
                        time.sleep(.15)
                        unchanged_rows=json.loads((directory/'frame.json').read_text())['rows']
                        query(b'd{i:3,w:1}', b'd')
                        def active_frame():
                            try:return json.loads((directory/'frame.json').read_text())
                            except ValueError:return {}
                        wait_for(lambda: active_frame().get('equipment') == [1, 0, 0, 0])
                        assert active_frame()['rows'] == unchanged_rows
                        query(b'd{i:3,w:0}', b'd')

                        time.sleep(.2)
                        assert b'+--------------------+' not in p.console()
                    elif scenario == 'blocked':
                        end = time.monotonic()+9
                        unit = False
                        while time.monotonic()<end and b'\xc2\xb0' not in p.console():
                            p.command(b'j{tempFormat:'+ (b'F' if unit else b'C') + b'}')
                            p.line(); p.line()
                            unit = not unit
                            time.sleep(.04)
                        assert b'\xc2\xb0' in p.console(), 'live GUI never reading frames did not fall back'
                    else:
                        wait_for(lambda: b'\xc2\xb0C' in p.console(), timeout=9)
                    assert p.command(b'n').startswith(b'N:')
                finally:
                    p.close()
                pid = int((directory/'pid').read_text())
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise AssertionError(('GUI child survived cleanup', scenario, pid))
        finally:
            os.close(sentinel)
        checks.append('GUI ready/frame path, window close, malformed/oversize/error/startup/hang fallback, ignored SIGTERM, FD isolation, owned-child reaping')
        for scenario in ('user-close', 'close-exit'):
            directory = root/('gui-'+scenario)
            chosen = dict(env, PATH=str(bindir), LCD_TEST_ROOT=str(directory),
                          LCD_TEST_PEER=scenario, LCD_SENTINEL='40')
            p = Process(exe, directory, 'gui', env=chosen)
            try:
                wait_for(lambda: (p.console(), p.proc.poll())[1] is not None)
                assert not (directory/'serial').is_symlink()
                assert p.checkpoint.exists()
            finally:
                p.close()
            assert b'+--------------------+' not in p.buffer
        checks.append('deliberate GUI close datagram and close-exit race both stop emulator cleanly without terminal fallback')
        # A paused resume must not add controller evaluations while a GUI stalls.
        base = root/'off'
        snapshot = json.loads((base/'checkpoint.json').read_text())
        # Process owns its newly created folder, so keep inputs in the existing base.
        p = Process(exe, root/'resume-running', 'gui', env=dict(env, PATH='/nonexistent'),
                    extra=('--resume', str(base/'checkpoint.json')))
        try:
            wait_for(lambda: b'\xc2\xb0C' in p.console())
            assert p.command(b'l').startswith(b'L:')
        finally:
            p.close()
        assert json.loads(p.checkpoint.read_text())['engine'] == snapshot['engine']
        # Display failure must preserve the application's checkpoint failure.
        p = Process(exe, root/'checkpoint-failure', 'auto', env=dict(env, PATH='/nonexistent'))
        try:
            os.write(p.serial, b'j{Kp:7')
            time.sleep(.05)
        finally:
            error = p.close(check=False)
        assert p.proc.returncode != 0 and not p.checkpoint.exists() and b'checkpoint' in error
        checks.append('paused GUI fallback/resume preserves checkpoint; incomplete-command shutdown retains application failure')
    report = dict(status='passed', platform=sys.platform, checks=checks)
    output = Path('test-results'); output.mkdir(exist_ok=True)
    (output/'lcd.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
