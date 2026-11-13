# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Real PTY/process/store checks using only the Python standard library."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import termios
import time

EXE = str(Path(sys.argv[1]).resolve())


class Session:
    def __init__(self, root, fresh=True):
        self.path = root / 'serial'
        self.store = root / 'controller.json'
        self.p = subprocess.Popen([EXE, '--serial', str(self.path), '--state', str(self.store)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.fd = None
        self.buffer = b''
        deadline = time.monotonic() + 5
        while not self.path.is_symlink():
            if self.p.poll() is not None:
                raise AssertionError(self.p.communicate())
            if time.monotonic() > deadline:
                raise AssertionError('PTY readiness deadline exceeded')
            time.sleep(.01)
        self.connect()
        if fresh:
            self.expect('D', {'logType': 'W', 'logID': 3, 'V': []})

    def connect(self):
        self.fd = os.open(self.path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        flags = termios.tcgetattr(self.fd)
        assert not flags[3] & (termios.ICANON | termios.ECHO)
        assert not flags[1] & termios.OPOST

    def write(self, data):
        pos = 0
        deadline = time.monotonic() + 5
        while pos < len(data):
            if time.monotonic() > deadline:
                raise AssertionError('PTY write stalled')
            _, ready, _ = select.select([], [self.fd], [], .1)
            if ready:
                try:
                    pos += os.write(self.fd, data[pos:])
                except BlockingIOError:
                    pass

    def line(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\r\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            assert remaining > 0, ('PTY response deadline exceeded', self.buffer)
            readable, _, _ = select.select([self.fd], [], [], remaining)
            assert readable, ('PTY response deadline exceeded', self.buffer)
            data = os.read(self.fd, 65536)
            assert data, 'PTY closed'
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\r\n', 1)
        return line

    def expect(self, prefix, payload=None):
        line = self.line()
        assert line.startswith(prefix.encode() + b':'), line
        result = json.loads(line[2:].decode('cp437'))
        if payload is not None:
            assert result == payload, (result, payload)
        return result

    def silent(self, timeout=.08):
        assert not self.buffer, self.buffer
        assert not select.select([self.fd], [], [], timeout)[0], 'unexpected output'

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.p.terminate()
        stdout, stderr = self.p.communicate(timeout=5)
        assert self.p.returncode == 0, (stdout, stderr)
        assert not self.path.exists() and not self.path.is_symlink(), 'owned link was not removed'


def failure(serial, store):
    p = subprocess.run([EXE, '--serial', str(serial), '--state', str(store)], capture_output=True, timeout=5)
    assert p.returncode != 0 and p.stderr and not p.stdout
    return p.stderr


def run():
    checks = []
    with tempfile.TemporaryDirectory(prefix='rmx-pty-') as directory:
        root = Path(directory)
        s = Session(root)
        try:
            s.write(b'ns')
            identity = s.expect('N')
            assert identity == dict(v='0.2.13', n='8f1fa12', s=2, y=0, b='s', l='3')
            initial = s.expect('S')
            assert initial == dict(mode='o', beerSet=None, fridgeSet=None, heatEst=.199, coolEst=5)
            checks.append('real raw PTY, identity, and erased boot')
            # Two independent exclusive resources: a store and a serial path.
            assert b'store' in failure(root / 'other-serial', s.store)
            assert b'serial' in failure(s.path, root / 'other-state')
            assert s.path.is_symlink()
            checks.append('exclusive store/serial ownership')
            s.write(b'E')
            s.expect('D', dict(logType='I', logID=15, V=[]))
            s.write(b'j{Kp:7')
            s.silent(.2)
            before = time.monotonic()
            s.expect('D', dict(logType='I', logID=12, V=['Kp', '7']))
            elapsed = time.monotonic() - before
            assert .55 < elapsed < 2.2, elapsed
            s.expect('S')
            assert s.expect('C')['Kp'] == 7
            s.silent()
            checks.append('wall-clock partial-token timeout, independent of simulated time')
            # Every input chunk boundary is exercised through the kernel PTY.
            for cut in range(1, len(b'j{Ki:0.5}n')):
                message = b'j{Ki:0.5}n'
                s.write(message[:cut])
                s.write(message[cut:])
                s.expect('D', dict(logType='I', logID=12, V=['Ki', '0.5']))
                s.expect('S')
                assert s.expect('C')['Ki'] == .5
                s.expect('N', identity)
            checks.append('all split positions and coalesced commands through PTY')
            s.write(b'U{i:0,f:9,h:2,p:18,a:28A10100000001E6}U{i:3,f:2,h:1,p:5,x:1}')
            probe = s.expect('U')
            heater = s.expect('U')
            assert probe['f'] == 9 and heater['f'] == 2
            s.silent()
            s.write(b'j{mode:t}d{i:3,w:1,r:1}d{i:3,r:1}')
            s.expect('D')
            s.expect('T')
            s.expect('S')
            s.expect('C')
            assert 'v' not in s.expect('d')[0]
            assert s.expect('d')[0]['v'] == 1
            # Close/reopen does not restart the MCU-like state or lose the PTY.
            os.close(s.fd)
            s.fd = None
            s.connect()
            s.write(b'd{i:3,r:1}s')
            assert s.expect('d')[0]['v'] == 1
            assert s.expect('S')['mode'] == 't'
            checks.append('assignment, manual output, and client reopen without reset')
            # An intentionally slow reader causes output backpressure, not data loss.
            s.write(b'n' * 2500)
            for _ in range(2500):
                s.expect('N', identity)
            s.silent()
            checks.append('slow reader and 2,500 ordered replies without dropped bytes')
            s.write(b'C')
            assert s.expect('C')['Kp'] == 5
            s.expect('D', dict(logType='I', logID=13, V=[]))
            s.write(b'R')
            s.silent()
            s.write(b'cd{r:1}')
            assert s.expect('C')['Kp'] == 7
            devices = s.expect('d')
            assert devices[0]['a'] == probe['a'] and devices[-1]['v'] == 0
            checks.append('volatile C, R reload, and volatile actuator reset')
        finally:
            s.close()
        s = Session(root, fresh=False)
        try:
            s.write(b'cd{}')
            constants = s.expect('C')
            assert constants['Kp'] == 7 and constants['Ki'] == .5
            devices = s.expect('d')
            assert devices == [probe, heater]
            checks.append('saved settings and registry survive an actual process restart')
        finally:
            s.close()
        # A foreign regular file is never overwritten by stable-link setup.
        foreign = root / 'foreign'
        foreign.write_text('keep me')
        failure(foreign, root / 'unused-state')
        assert foreign.read_text() == 'keep me'
        # Corruption is an environment error, not an invented Arduino D record.
        corrupt = root / 'corrupt.json'
        corrupt.write_text('{broken')
        assert b'JSON' in failure(root / 'new-serial', corrupt)
        assert corrupt.read_text() == '{broken'
        assert not (root / 'new-serial').exists()
        checks.append('foreign path preservation and corrupt-store failure outside serial')
        # A failing host-store replacement terminates outside serial; it cannot
        # claim the I15 success message or silently keep accepting writes.
        broken_root = root / 'write-failure'
        broken_root.mkdir()
        broken = Session(broken_root)
        broken.store.mkdir()
        broken.write(b'E')
        stdout, stderr = broken.p.communicate(timeout=5)
        assert broken.p.returncode != 0 and b'store' in stderr and not stdout
        assert not broken.path.is_symlink()
        assert not broken.buffer
        if select.select([broken.fd], [], [], .05)[0]:
            try:
                assert os.read(broken.fd, 4096) == b''
            except OSError as exc:
                assert exc.errno == 5  # Linux PTY hangup is EIO; Darwin returns EOF.
        os.close(broken.fd)
        checks.append('host write failure terminates without a fabricated serial acknowledgment')
        # Replacing the owned symlink with a foreign file does not authorize
        # cleanup to remove that file on shutdown.
        replacement_root = root / 'replacement'
        replacement_root.mkdir()
        replaced = Session(replacement_root)
        replaced.path.unlink()
        replaced.path.write_text('foreign replacement')
        os.close(replaced.fd)
        replaced.p.terminate()
        replaced.p.communicate(timeout=5)
        assert replaced.p.returncode == 0
        assert replaced.path.read_text() == 'foreign replacement'
        checks.append('shutdown removes only its own unchanged symlink')
        # Missing native fields are corruption, not silently defaulted records.
        original_image = json.loads(s.store.read_text())
        incomplete = root / 'incomplete.json'
        bad_image = json.loads(json.dumps(original_image))
        del bad_image['devices'][0]['f']
        incomplete.write_text(json.dumps(bad_image))
        assert b'stored device' in failure(root / 'incomplete-serial', incomplete)
        # Opening a FIFO must not block before checking the regular-file requirement.
        fifo = root / 'fifo-state'
        os.mkfifo(fifo)
        assert b'regular file' in failure(root / 'fifo-serial', fifo)
        oversized = root / 'oversized.json'
        oversized.write_bytes(b' ' * (1024 * 1024 + 1))
        assert b'bounded regular' in failure(root / 'oversized-serial', oversized)
        checks.append('incomplete native records, FIFO state paths, and oversized stores fail without blocking or invented defaults')
        # Wrong firmware store version enters safe mode rather than initializing slots.
        image = json.loads(s.store.read_text())
        image['controller_version'] = 3
        s.store.write_text(json.dumps(image))
        s = Session(root)
        try:
            s.write(b'd{e:1}')
            s.expect('d', [])
            s.write(b'E')
            s.expect('D', dict(logType='I', logID=15, V=[]))
            s.write(b'd{e:1}')
            assert len(s.expect('d')) == 16
            checks.append('wrong-version safe mode followed by E initialization')
        finally:
            s.close()
    result = dict(status='passed', platform=sys.platform, checks=checks)
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    (out / 'milestone2-transport.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    run()
