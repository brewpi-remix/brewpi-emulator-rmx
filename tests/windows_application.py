# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Native provider-backed application lifecycle checks, not physical-device tests."""
import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


def stop_console(process):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.FreeConsole()
    kernel.AttachConsole.argtypes = [w.DWORD]
    kernel.GenerateConsoleCtrlEvent.argtypes = [w.DWORD, w.DWORD]
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.DWORD)
    handler = callback_type(lambda reason: True)
    kernel.SetConsoleCtrlHandler.argtypes = [callback_type, w.BOOL]
    if not kernel.AttachConsole(process.pid):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetConsoleCtrlHandler(handler, True):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GenerateConsoleCtrlEvent(1, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        process.wait(timeout=5)
    finally:
        kernel.FreeConsole()
    if process.returncode:
        raise AssertionError('cooperative shutdown failed: ' + str(process.returncode))


def execute(binary, pair, cycles, ready_helper, directory):
    import serial
    if os.name != 'nt' or platform.machine().upper() != 'AMD64' or serial.VERSION != '3.5':
        raise RuntimeError('native Windows AMD64 and pySerial 3.5 required')
    binary = Path(binary).resolve(strict=True)
    pair = Path(pair).resolve(strict=True)
    record = json.loads(pair.read_text())
    selected, peer = [x['port'] for x in record['endpoints']]
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    rows = []
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with tempfile.TemporaryDirectory(prefix='application-', dir=directory) as temp:
        root = Path(temp)
        for cycle in range(cycles):
            case = root / ('Unicode é ' + str(cycle))
            case.mkdir()
            state, checkpoint = [case / name for name in ['state.json', 'checkpoint.json']]
            speed = [1, 10, 60, 0][cycle % 4]
            with (case / 'stdout').open('wb') as out, (case / 'stderr').open('wb') as err:
                process = subprocess.Popen([str(binary), '--serial', selected, '--serial-pair', str(pair),
                                            '--state', str(state), '--speed', str(speed),
                                            '--checkpoint', str(checkpoint)], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                           creationflags=subprocess.CREATE_NEW_CONSOLE,
                                           startupinfo=startup)
                client = None
                try:
                    result = subprocess.run([sys.executable, str(ready_helper), '--serial', selected,
                                             '--state', str(state), '--pid', str(process.pid),
                                             '--timeout', '5'], stdin=subprocess.DEVNULL, capture_output=True, timeout=7)
                    assert result.returncode == 0, (result.stdout, result.stderr, process.poll())
                    client = serial.Serial(peer, 57600, timeout=.1, write_timeout=2)
                    client.flushInput()
                    client.flushOutput()
                    client.dtr = False
                    client.rts = False
                    client.dtr = True
                    client.rts = True
                    client.break_condition = True
                    client.break_condition = False

                    def send(data):
                        assert client.write(data) == len(data)
                        client.flush()

                    def line():
                        data, end = b'', time.monotonic() + 5
                        while not data.endswith(b'\r\n'):
                            assert time.monotonic() < end and len(data) <= 65536, data
                            data += client.read_until(b'\n')
                        assert b'\r' not in data[:-2] and b'\n' not in data[:-2], data
                        return data

                    send(b'nlE')
                    identity, lcd, initialized = line(), line(), line()
                    assert identity == b'N:{"v":"0.2.13","n":"8f1fa12","s":2,"y":0,"b":"s","l":"3"}\r\n'
                    assert lcd.startswith(b'L:') and b'\xb0' in lcd and b'\xc2\xb0' not in lcd
                    assert json.loads(initialized[2:]) == dict(logType='I', logID=15, V=[])
                    waited = None
                    if cycle < 4:
                        start = time.monotonic()
                        send(b'j{Kp:7')
                        diagnostic = line()
                        waited = time.monotonic() - start
                        assert .6 < waited < 2.5, waited
                        assert json.loads(diagnostic[2:]) == dict(logType='I', logID=12, V=['Kp', '7'])
                        assert line().startswith(b'S:')
                        constants = line()
                        assert json.loads(constants[2:])['Kp'] == 7
                    if cycle == 0:
                        # Deliberately stop reading before draining a reply burst
                        # larger than the application gate and provider buffers.
                        send(b'n' * 2500)
                        time.sleep(.2)
                        for _ in range(2500):
                            assert line() == identity
                        previous = json.loads(constants[2:])
                        send(b'j{Kp:notanumber,Ki:1e2}')
                        assert json.loads(line()[2:]) == dict(logType='I', logID=12, V=['Kp', 'notanumber'])
                        assert json.loads(line()[2:]) == dict(logType='I', logID=12, V=['Ki', '1e2'])
                        assert line().startswith(b'S:')
                        assert json.loads(line()[2:]) == previous
                        send(b'j{K'); time.sleep(.05); send(b'p:7}')
                        assert json.loads(line()[2:]) == dict(logType='I', logID=12, V=['Kp', '7'])
                        assert line().startswith(b'S:')
                        assert json.loads(line()[2:]) == previous
                        send(b'R')
                        assert client.read(1) == b'', 'valid stored restart invented a reply'
                        send(b'c')
                        assert json.loads(line()[2:]) == previous
                    client.close()
                    client = serial.Serial(peer, 57600, timeout=.1, write_timeout=2)
                    assert client.read(1) == b'', 'reopen invented a startup response'
                    send(b'nc')
                    assert line() == identity
                    constants = line()
                    assert json.loads(constants[2:])['Kp'] == (7 if cycle < 4 else 5)
                    client.close()
                    client = None
                    stop_console(process)
                    saved = json.loads(checkpoint.read_text())
                    assert saved['format'] == 'brewpi-emulator-checkpoint-v1'
                    assert json.loads(Path(str(state) + '.ready').read_text())['ready'] is False
                    assert not (case / 'stdout').read_bytes()
                    rows.append(dict(cycle=cycle, speed=speed, partial_wait_seconds=waited))
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == before
    return dict(status='passed', scope='native Windows COM application process/client lifecycles',
                executable_sha256=before, pair_sha256=hashlib.sha256(pair.read_bytes()).hexdigest(),
                system=platform.platform(), architecture=platform.machine(), python=sys.version,
                pyserial=serial.VERSION, cycles=rows)


def main():
    if not __debug__:
        raise SystemExit('test assertions must be enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=100)
    parser.add_argument('--ready-helper', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 4 <= args.cycles <= 100 or args.output.exists():
        parser.error('4..100 cycles and a new output path required')
    report = execute(args.binary, args.pair, args.cycles, args.ready_helper, args.directory)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
