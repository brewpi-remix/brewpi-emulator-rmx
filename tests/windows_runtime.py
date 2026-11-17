# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Finite native Windows package pacing, COM traffic, and checkpoint continuation."""
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
from windows_application import stop_console


def memory_kib(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    class Memory(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('faults', w.DWORD),
                    *[(name, ctypes.c_size_t) for name in ['peak', 'working', 'paged_peak', 'paged',
                                                         'nonpaged_peak', 'nonpaged', 'pagefile',
                                                         'pagefile_peak', 'private']]]
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.K32GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Memory(); info.size = ctypes.sizeof(info)
        if not kernel.K32GetProcessMemoryInfo(handle, ctypes.byref(info), info.size):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.working // 1024
    finally:
        kernel.CloseHandle(handle)


def run(package, pair, seconds, defaults_path, snapshot):
    import serial
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'release'))
    from windows import native, verify
    native()
    if serial.VERSION != '3.5':
        raise ValueError('external pySerial 3.5 required')
    manifest = verify(package, '0.0.1', snapshot)
    binary = package / 'payload/bin/brewpi-emulator-rmx.exe'
    helper = package / 'payload/libexec/brewpi-emulator-rmx/wait-ready.py'
    defaults = json.loads(defaults_path.read_text())
    pair_record = json.loads(pair.read_text())
    selected, peer = [x['port'] for x in pair_record['endpoints']]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    results = []
    with tempfile.TemporaryDirectory(prefix='windows-runtime-', dir=package.parent) as temp:
        root = Path(temp)
        for speed in [1, 60]:
            case = root / str(speed); case.mkdir()
            state, checkpoint = case / 'state.json', case / 'checkpoint.json'
            base = [str(binary), '--serial', selected, '--serial-pair', str(pair), '--state', str(state)]
            with (case / 'log').open('wb') as log:
                start = time.monotonic()
                process = subprocess.Popen(base + ['--speed', str(speed), '--checkpoint', str(checkpoint)],
                                           stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                           creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
                client = None
                try:
                    subprocess.run([sys.executable, str(helper), '--serial', selected, '--state', str(state),
                                    '--pid', str(process.pid), '--timeout', '5'], stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=7, check=True)
                    client = serial.Serial(peer, 57600, timeout=.1, write_timeout=2)
                    client.flushInput(); client.flushOutput()
                    def send(data):
                        assert client.write(data) == len(data)
                        client.flush()
                    def receive(prefix):
                        end = time.monotonic() + 5
                        line = b''
                        while time.monotonic() < end:
                            line += client.read_until(b'\n')
                            if not line.endswith(b'\n'):
                                assert len(line) <= 65536, 'oversized native serial frame'
                                continue
                            assert line.endswith(b'\r\n') and line[1:2] == b':', line
                            value = json.loads(line[2:].decode('cp437'))
                            if line[:1] == prefix:
                                return value
                            line = b''
                        raise TimeoutError('missing native COM response')
                    send(b'E'); assert receive(b'D') == dict(logType='I', logID=15, V=[])
                    for slot in defaults['all_assigned_slots']:
                        patch = {k: v for k, v in slot.items() if k in ['i', 'c', 'b', 'f', 'h', 'd', 'p', 'x', 'a', 'j']}
                        send(b'U' + json.dumps(patch).encode())
                        actual = receive(b'U')
                        assert actual['i'] == patch['i'] and actual['f'] == patch['f']
                    send(b'j{mode:b,beerSet:22}'); receive(b'S'); receive(b'C')
                    latencies, resources = [], []
                    phase = time.monotonic()
                    while time.monotonic() - phase < seconds:
                        query = time.monotonic(); send(b'n')
                        assert receive(b'N') == defaults['identity']
                        latencies.append(time.monotonic() - query)
                        assert latencies[-1] < 1, latencies[-1]
                        send(b't'); receive(b'T')
                        resources.append(memory_kib(process.pid))
                        assert resources[-1] < 128 * 1024
                        time.sleep(min(.2, max(0, seconds - (time.monotonic() - phase))))
                    stopped = time.monotonic()
                    client.close(); client = None
                    stop_console(process)
                    saved = json.loads(checkpoint.read_text())
                    simulated = (saved['engine']['plant']['age_ms'] + saved['engine']['pending_ms']) / 1000
                    achieved = simulated / (stopped - start)
                    assert .85 * speed < achieved < 1.15 * speed, achieved
                    assert max(resources) - min(resources) < 32 * 1024
                    resumed_checkpoint = case / 'resumed.json'
                    resumed = subprocess.Popen(base + ['--resume', str(checkpoint), '--speed', '0',
                                                       '--checkpoint', str(resumed_checkpoint)],
                                               stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                               creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
                    try:
                        subprocess.run([sys.executable, str(helper), '--serial', selected, '--state', str(state),
                                        '--pid', str(resumed.pid), '--timeout', '5'], stdin=subprocess.DEVNULL,
                                       capture_output=True, timeout=7, check=True)
                        stop_console(resumed)
                    finally:
                        if resumed.poll() is None:
                            resumed.kill(); resumed.wait(timeout=5)
                    assert json.loads(resumed_checkpoint.read_text())['engine'] == saved['engine']
                    results.append(dict(speed=speed, wall_seconds=stopped-phase, achieved_factor=achieved,
                                        max_query_seconds=max(latencies), queries=len(latencies),
                                        max_working_set_kib=max(resources), working_set_range_kib=max(resources)-min(resources),
                                        exact_paused_continuation=True))
                finally:
                    if client is not None:
                        client.close()
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=5)
    verify(package, '0.0.1', snapshot)
    return dict(status='passed', producer='local-native-windows-package-runtime',
                scope='300-second focused checks' if seconds == 300 else 'short smoke; duration gate incomplete',
                system=platform.platform(), executable_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                archive_sha256=manifest['archive_sha256'], source_snapshot_sha256=snapshot,
                limits=dict(query_seconds=1, pacing_relative_error=.15, max_working_set_mib=128, working_set_range_mib=32),
                results=results)


def main():
    if not __debug__:
        raise SystemExit('test assertions must be enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path); parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=300); parser.add_argument('--source-snapshot', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--defaults', type=Path, default=Path(__file__).resolve().parents[1] / 'engineering/protocol/test-vectors/defaults-v1.json')
    args = parser.parse_args()
    if not 3 <= args.seconds <= 300 or args.output.exists():
        parser.error('3..300 seconds and a new output path required')
    result = run(args.package.resolve(), args.pair.resolve(), args.seconds, args.defaults, args.source_snapshot)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
