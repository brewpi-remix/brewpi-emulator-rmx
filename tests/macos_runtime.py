# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Bounded native macOS package pacing, terminal controls, and continuation checks."""
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

from lcd_tests import Process, wait_for

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'release'))
from macos import verify


def run(package, seconds, expected_snapshot):
    import serial
    if serial.VERSION != '3.5':
        raise ValueError('pinned external pySerial 3.5 is required')
    manifest = verify(package, expected_snapshot=expected_snapshot)
    drivers = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
               ['tests/macos_runtime.py', 'tests/lcd_tests.py', 'release/macos.py',
                'release/artifacts.py', 'release/runbook.py', 'tests/ci/version.py']}
    binary = str((package / 'payload/bin/brewpi-emulator-rmx').resolve())
    helper = package / 'payload/libexec/brewpi-emulator-rmx/wait-ready.py'
    defaults = json.loads((ROOT / 'engineering/protocol/test-vectors/defaults-v1.json').read_text())
    results = []
    with tempfile.TemporaryDirectory(prefix='rmx-macos-package-runtime-') as directory:
        root = Path(directory)
        for speed in [1, 60]:
            case = root / str(speed)
            env = dict(os.environ, TERM='xterm-256color', LC_ALL='en_US.UTF-8', PYTHONDONTWRITEBYTECODE='1')
            start = time.monotonic()
            p = Process(binary, case, 'terminal', env=env, extra=['--speed', str(speed)])
            os.close(p.serial); p.serial = None
            client = None
            try:
                subprocess.run([sys.executable, str(helper), '--serial', str(case / 'serial'),
                                '--pid', str(p.proc.pid), '--timeout', '2'], capture_output=True, check=True, timeout=4)
                client = serial.Serial(str(case / 'serial'), 57600, timeout=.1, write_timeout=2, exclusive=True)

                def receive(prefix):
                    deadline = time.monotonic() + 5
                    line = b''
                    while time.monotonic() < deadline:
                        p.console(); p.buffer = p.buffer[-65536:]
                        line += client.read_until(b'\n')
                        if not line.endswith(b'\n'):
                            assert len(line) <= 65536, 'oversized native serial frame'
                            continue
                        assert line.endswith(b'\r\n') and line[1:2] == b':', line
                        value = json.loads(line[2:].decode('cp437'))
                        if line[:1] == prefix:
                            return value
                        line = b''
                    raise TimeoutError('missing native serial reply: ' + repr(prefix))

                def send(data):
                    assert client.write(data) == len(data)
                    client.flush()

                send(b'E'); initialized = receive(b'D')
                assert initialized == dict(logType='I', logID=15, V=[])
                for slot in defaults['all_assigned_slots']:
                    patch = {k: v for k, v in slot.items() if k in ['i', 'c', 'b', 'f', 'h', 'd', 'p', 'x', 'a', 'j']}
                    send(b'U' + json.dumps(patch).encode())
                    assigned = receive(b'U')
                    assert assigned['i'] == patch['i'] and assigned['f'] == patch['f']
                send(b'j{mode:b,beerSet:22}')
                receive(b'S'); receive(b'C')
                wait_for(lambda: b'> ' in p.console())
                controls = [(b'press\r', b'Action accepted'), (b'cw\r', b'Action accepted'),
                            (b'press\r', b'Edit target'), (b'press\r', b'Target committed'),
                            (b'door open\r', b'Door opened'), (b'door close\r', b'Door closed')]
                for command, expected in controls:
                    p.console(); p.buffer = b''
                    os.write(p.master, command)
                    wait_for(lambda: expected in p.console(), timeout=3)
                latencies, resources = [], []
                phase = time.monotonic()
                end = phase + seconds
                while time.monotonic() < end:
                    query = time.monotonic()
                    send(b'n')
                    assert receive(b'N') == defaults['identity']
                    latency = time.monotonic() - query
                    assert latency < 1, latency
                    latencies.append(latency)
                    send(b't'); receive(b'T')
                    rss = int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(p.proc.pid)], text=True).strip())
                    assert rss < 128 * 1024, rss
                    resources.append(rss)
                    p.console(); p.buffer = p.buffer[-65536:]
                    time.sleep(min(.2, max(0, end - time.monotonic())))
                stopped = time.monotonic()
                client.close(); client = None
                p.close()
                checkpoint = json.loads(p.checkpoint.read_text())
                simulated = (checkpoint['engine']['plant']['age_ms'] + checkpoint['engine']['pending_ms']) / 1000
                achieved = simulated / (stopped - start)
                assert .85 * speed < achieved < 1.15 * speed, achieved
                assert max(resources) - min(resources) < 32 * 1024
                resumed = Process(binary, root / (str(speed) + '-resume'), 'off', env=env,
                                  extra=['--resume', str(p.checkpoint), '--state', str(case / 'state.json')])
                try:
                    assert resumed.command(b'n').startswith(b'N:')
                finally:
                    resumed.close()
                assert json.loads(resumed.checkpoint.read_text())['engine'] == checkpoint['engine']
                results.append(dict(speed=speed, wall_seconds=stopped - phase, achieved_factor=achieved,
                                    max_query_seconds=max(latencies), query_count=len(latencies),
                                    max_rss_kib=max(resources), rss_growth_kib=max(resources) - min(resources),
                                    terminal_controls=[x[0].decode().strip() for x in controls], exact_paused_continuation=True))
            finally:
                if client is not None:
                    client.close()
                if p.proc.poll() is None:
                    p.close(check=False)
    verify(package, expected_snapshot=expected_snapshot)
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
               for name, digest in drivers.items()), 'qualification helper changed during execution'
    return dict(producer='local-native-macos-package-runtime', status='passed',
                scope='300-second focused checks' if seconds == 300 else 'short smoke checks; duration gate incomplete',
                archive_sha256=manifest['archive_sha256'], source_snapshot_sha256=manifest['source_snapshot_sha256'],
                manifest_sha256=hashlib.sha256((package / 'macos-manifest.json').read_bytes()).hexdigest(),
                qualification_helper_sha256=drivers,
                host=platform.platform(), python=sys.version, pyserial=serial.VERSION,
                predeclared_limits=dict(query_seconds=1, pacing_relative_error=.15, max_rss_mib=128, rss_range_mib=32),
                results=results, separate_acceptance=['host/panel workflows', 'desktop GUI', 'downloaded archive handling', 'notarization', 'owner acceptance'])


def main():
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
        raise SystemExit('Python test assertions must be enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-snapshot', required=True)
    args = parser.parse_args()
    if not 3 <= args.seconds <= 300:
        parser.error('--seconds must be between 3 and 300')
    if args.output.exists():
        parser.error('output already exists')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def expired(signum, frame):
        raise TimeoutError('bounded macOS qualification deadline exceeded')
    old = signal.signal(signal.SIGALRM, expired)
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    old_term = signal.signal(signal.SIGTERM, interrupted)
    signal.setitimer(signal.ITIMER_REAL, 2 * args.seconds + 90)
    try:
        result = run(args.package.resolve(), args.seconds, args.source_snapshot)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        signal.signal(signal.SIGTERM, old_term)
    with args.output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
