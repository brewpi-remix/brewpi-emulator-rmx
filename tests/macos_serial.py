# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise a native macOS PTY with the separately installed pySerial client."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time


def worker(binary, cycles, directory, ready_helper):
    import serial

    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise RuntimeError('this check requires native macOS ARM64')
    if serial.VERSION != '3.5':
        raise RuntimeError('this check requires the pinned external pySerial 3.5 client')
    binary = Path(binary).resolve(strict=True)
    ready_helper = Path(ready_helper).resolve(strict=True)
    ready_hash = hashlib.sha256(ready_helper.read_bytes()).hexdigest()
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    from source_inputs import inventory
    inputs = inventory(Path(__file__).resolve().parents[1])
    results = []
    with tempfile.TemporaryDirectory(prefix='endpoint-', dir=directory) as directory:
        root = Path(directory)
        for cycle in range(cycles):
            case = root / str(cycle)
            case.mkdir()
            port, store, checkpoint = [case / name for name in ['serial', 'state.json', 'checkpoint.json']]
            speed = [1, 10, 60][cycle % 3]
            process = subprocess.Popen([str(binary), '--serial', str(port), '--state', str(store),
                                        '--speed', str(speed), '--checkpoint', str(checkpoint)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            client = None
            try:
                deadline = time.monotonic() + 5
                while not port.is_symlink():
                    if process.poll() is not None:
                        raise AssertionError(process.communicate())
                    if time.monotonic() >= deadline:
                        raise TimeoutError('serial publication')
                    time.sleep(.01)
                ready = subprocess.run([sys.executable, str(ready_helper), '--serial', str(port),
                                '--pid', str(process.pid), '--timeout', '2'],
                               capture_output=True, timeout=4)
                assert ready.returncode == 0, (ready.stdout, ready.stderr)

                def connect():
                    return serial.Serial(str(port), 57600, timeout=.1, write_timeout=2, exclusive=True)

                def line():
                    data = b''
                    end = time.monotonic() + 5
                    while not data.endswith(b'\r\n'):
                        if time.monotonic() >= end or len(data) > 65536:
                            raise AssertionError(('missing bounded CRLF response', data))
                        data += client.read_until(b'\n')
                    assert b'\r' not in data[:-2] and b'\n' not in data[:-2], data
                    return data

                def send(data):
                    assert client.write(data) == len(data)
                    # The outer process timeout also bounds macOS tcdrain(),
                    # which pySerial's write timeout does not cover.
                    client.flush()

                client = connect()
                # pySerial's open path purges queued input. Test the host's
                # actual client semantics rather than requiring pre-open boot
                # bytes to survive an intentional client purge.
                client.flushInput()
                client.flushOutput()
                send(b'nlE')
                identity, lcd, initialized = line(), line(), line()
                assert identity == b'N:{"v":"0.2.13","n":"8f1fa12","s":2,"y":0,"b":"s","l":"3"}\r\n'
                assert lcd.startswith(b'L:') and b'\xb0' in lcd and b'\xc2\xb0' not in lcd
                assert json.loads(initialized[2:]) == dict(logType='I', logID=15, V=[])
                waited = None
                if cycle < 3:
                    start = time.monotonic()
                    send(b'j{Kp:7')
                    diagnostic = line()
                    waited = time.monotonic() - start
                    assert .6 < waited < 2.5, waited
                    assert json.loads(diagnostic[2:]) == dict(logType='I', logID=12, V=['Kp', '7'])
                    assert line().startswith(b'S:')
                    constants = line()
                    assert constants.startswith(b'C:') and json.loads(constants[2:])['Kp'] == 7
                client.close()
                client = connect()
                assert client.read(1) == b'', 'reopen invented a startup response'
                send(b'nc')
                assert line() == identity
                constants = line()
                assert constants.startswith(b'C:')
                assert json.loads(constants[2:])['Kp'] == (7 if cycle < 3 else 5)
                client.close()
                client = None
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
                assert process.returncode == 0 and not stdout, (stdout, stderr)
                assert not port.exists() and not port.is_symlink()
                saved = json.loads(checkpoint.read_text())
                assert saved['format'] == 'brewpi-emulator-checkpoint-v1'
                results.append(dict(cycle=cycle, speed=speed, partial_wait_seconds=waited,
                                    simulated_ms=saved['engine']['controller_ms'] + saved['engine']['pending_ms']))
            finally:
                if client is not None:
                    client.close()
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == before
    assert hashlib.sha256(ready_helper.read_bytes()).hexdigest() == ready_hash
    assert inventory(Path(__file__).resolve().parents[1]) == inputs, 'source changed during checks'
    return dict(status='passed', evidence_scope='native source-bound pySerial endpoint regression; not final package qualification',
                executable_sha256=before, ready_helper_sha256=ready_hash, source_inputs=inputs,
                system=platform.platform(), architecture=platform.machine(),
                python=sys.version, pyserial=serial.VERSION, cycles=results)


def main():
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
        raise SystemExit('Python test assertions must be enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary')
    parser.add_argument('--cycles', type=int, default=100)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ready-helper', type=Path, default=Path(__file__).resolve().parents[1] / 'scripts/wait-ready.py')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--root', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('native macOS ARM64 is required')
    if not 3 <= args.cycles <= 100:
        parser.error('--cycles must be between 3 and 100')
    if args.output.exists():
        parser.error('output already exists; retain prior results')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.worker:
        if args.root is None:
            parser.error('worker requires its parent-owned temporary directory')
        report = worker(args.binary, args.cycles, args.root, args.ready_helper)
        with args.output.open('x') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')
    else:
        # A fresh process bounds even a platform client flush that never returns.
        with tempfile.TemporaryDirectory(prefix='rmx-macos-serial-') as root:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), args.binary,
                                        '--cycles', str(args.cycles), '--output', str(args.output),
                                        '--ready-helper', str(args.ready_helper),
                                        '--worker', '--root', root], start_new_session=True)
            try:
                code = process.wait(timeout=30 + args.cycles * 5)
                if code:
                    raise subprocess.CalledProcessError(code, process.args)
            except BaseException:
                # The private process group includes a client stuck in tcdrain
                # and its emulator. The parent also owns temporary-path cleanup.
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
                raise


if __name__ == '__main__':
    main()
