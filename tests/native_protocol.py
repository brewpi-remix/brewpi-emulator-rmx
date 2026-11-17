# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Replay the publicly establishable reviewed fixture subset on a native endpoint."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from fixtures import DATA, contains, decode_frames, equal, load


def eligible(case):
    return (case['classification'] == 'source_defined' and case['initial_preset'] == 'initialized'
            and all(step['action'] in ['serial_write', 'allow_serial_read_timeout', 'await_controller_restart']
                    and 'postconditions' not in step.get('expected', {}) for step in case['steps']))


def check(wire, expected, artifacts):
    if 'raw_hex' in expected:
        assert wire == bytes.fromhex(expected['raw_hex']), (wire, expected)
        return
    if 'output_before_read_timeout' in expected:
        assert not wire, wire
        return
    replies, diagnostics, order = [], [], []
    for prefix, value in decode_frames(wire):
        if prefix == 'D':
            diagnostics.append(value); order.append('D:' + value['logType'] + str(value['logID']))
        else:
            replies.append((prefix, value)); order.append(prefix)
    assert equal(diagnostics, expected.get('diagnostics', [])), (diagnostics, expected)
    wants = expected.get('replies', [])
    assert len(replies) == len(wants), (replies, expected)
    for (prefix, value), want in zip(replies, wants):
        assert prefix == want['prefix']
        if 'payload_contains' in want:
            assert contains(value, want['payload_contains']), (value, want)
        else:
            if 'payload_ref' in want:
                filename, path = want['payload_ref'].split('#')
                target = artifacts[filename]
                for key in path.split('/')[1:]:
                    target = target[int(key)] if isinstance(target, list) else target[key.replace('~1', '/').replace('~0', '~')]
            else:
                target = want['payload_equals']
            assert equal(value, target), (value, target)
    if 'output_order' in expected:
        assert order == expected['output_order'], (order, expected)


def run(binary, pair, directory):
    import serial
    if serial.VERSION != '3.5':
        raise ValueError('pinned external pySerial 3.5 required')
    windows = os.name == 'nt'
    if windows:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'release'))
        from windows import native
        native()
        from windows_application import stop_console
        record = json.loads(pair.read_text())
        selected, peer = [x['port'] for x in record['endpoints']]
    elif sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('this qualification adapter requires native macOS ARM64 or Windows x64')
    artifacts = {name: load(name) for name in ['defaults-v1.json', 'protocol-v1.json', 'diagnostics-v1.json']}
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert sum(eligible(c) for c in artifacts['protocol-v1.json']['cases']) == 30
    inputs = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in [Path(__file__), Path(__file__).with_name('fixtures.py'),
                           *[DATA / name for name in artifacts]]}
    results = []
    with tempfile.TemporaryDirectory(prefix='native-protocol-', dir=directory) as temp:
        root = Path(temp)
        for case in artifacts['protocol-v1.json']['cases']:
            if not eligible(case):
                results.append(dict(id=case['id'], status=('unresolved_reference_characterization'
                                    if case['classification'] == 'requires_reference_trace' else 'source_driver_only'),
                                    reason='requires a different constructed preset, internal observation, or explicit source-driver action'))
                continue
            path = root / case['id']; path.mkdir()
            port, state = path / 'serial', path / 'state.json'
            args = [str(binary), '--state', str(state), '--speed', '0']
            kwargs = {}
            if windows:
                args += ['--serial', selected, '--serial-pair', str(pair)]
                startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
                kwargs = dict(creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
            else:
                args += ['--serial', str(port)]
            with (path / 'log').open('wb') as log:
                process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **kwargs)
                client = None
                try:
                    end = time.monotonic() + 5
                    while not (Path(str(state) + '.ready').exists() if windows else port.is_symlink()):
                        assert process.poll() is None, 'native process exited before endpoint publication'
                        if time.monotonic() > end:
                            raise TimeoutError('native endpoint publication')
                        time.sleep(.01)
                    client = serial.Serial(peer if windows else str(port), 57600, timeout=.02, write_timeout=2)
                    time.sleep(.2)
                    client.flushInput(); client.flushOutput()
                    client.write(b'E'); client.flush()
                    initial = b''
                    deadline = time.monotonic() + 5
                    while not initial.endswith(b'\r\n'):
                        if time.monotonic() > deadline:
                            raise TimeoutError('public factory initialization')
                        initial += client.read_until(b'\n')
                    assert json.loads(initial[2:]) == dict(logType='I', logID=15, V=[])
                    for step in case['steps']:
                        expected = step.get('expected', {})
                        if step['action'] == 'serial_write':
                            for chunk in step['chunks_hex']:
                                data = bytes.fromhex(chunk)
                                assert client.write(data) == len(data)
                                client.flush()
                        lines = len(expected.get('replies', [])) + len(expected.get('diagnostics', []))
                        exact = bytes.fromhex(expected['raw_hex']) if 'raw_hex' in expected else None
                        if exact is not None:
                            lines = exact.count(b'\r\n')
                        wire = b''
                        deadline = time.monotonic() + 5
                        while wire.count(b'\r\n') < lines:
                            if time.monotonic() > deadline or len(wire) > 1024 * 1024:
                                raise TimeoutError(('native fixture response', case['id'], step, wire))
                            wire += client.read_until(b'\n')
                        # Deliberate paused-time quiet boundary; there is no
                        # production state-construction or observation API.
                        quiet = time.monotonic() + .1
                        while time.monotonic() < quiet:
                            # Timed HHD bulk reads can remain pending on a short
                            # response. Never request an arbitrary remainder.
                            wire += client.read(1 if windows else 4096)
                        check(wire, expected, artifacts)
                    client.close(); client = None
                    if windows:
                        stop_console(process)
                    else:
                        process.terminate(); process.wait(timeout=5)
                        assert process.returncode == 0
                    results.append(dict(id=case['id'], status='passed_public_transport'))
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=5)
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == before
    assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest for name, digest in inputs.items())
    return dict(input_sha256=inputs, status='passed', producer='local-native-public-fixture-replay', system=platform.platform(),
                executable_sha256=before, pyserial=serial.VERSION, cases=results,
                counts={status: sum(row['status'] == status for row in results) for status in
                        ['passed_public_transport', 'source_driver_only', 'unresolved_reference_characterization']})


def main():
    if not __debug__:
        raise SystemExit('test assertions must be enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path); parser.add_argument('--pair', type=Path)
    parser.add_argument('--directory', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (os.name == 'nt' and args.pair is None) or args.output.exists():
        parser.error('Windows requires --pair; output must be new')
    result = run(args.binary.resolve(strict=True), args.pair, args.directory)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
