# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Bound hidden Session 0 COM service and missing-Python LCD fallback checks."""
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
import time

IDENTITY = b'N:{"v":"0.2.13","n":"da7e14a9","s":2,"y":0,"b":"s","l":"3"}\r\n'


def line(client, process):
    data, deadline = b'', time.monotonic() + 5
    while not data.endswith(b'\r\n'):
        if process.poll() is not None or time.monotonic() >= deadline or len(data) > 65536:
            raise TimeoutError(('bounded serial line', process.poll(), data))
        # The supported HHD driver can leave a timed bulk read pending after
        # receiving fewer bytes than requested. A one-byte request never asks
        # it to wait for the remainder of an arbitrary application buffer.
        data += client.read(1)
    if b'\r' in data[:-2] or b'\n' in data[:-2]:
        raise AssertionError(('invalid line framing', data))
    return data


def worker(args):
    import serial
    from windows_application import stop_console
    if serial.VERSION != '3.5':
        raise RuntimeError('external pySerial 3.5 required')
    root = args.directory
    record = json.loads(args.pair.read_text())
    selected, peer = [x['port'] for x in record['endpoints']]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    rows = []
    for cycle in range(args.cycles):
        mode = ['off', 'terminal', 'gui'][cycle % 3]
        case = root / str(cycle)
        case.mkdir()
        state, checkpoint = case / 'state.json', case / 'checkpoint.json'
        environment = dict(os.environ, PATH=str(case / 'missing-python'), PYTHONDONTWRITEBYTECODE='1')
        with (case / 'stdout').open('wb') as out, (case / 'stderr').open('wb') as err:
            process = subprocess.Popen([str(args.binary), '--serial', selected, '--serial-pair', str(args.pair),
                                        '--state', str(state), '--checkpoint', str(checkpoint),
                                        '--lcd', mode, '--speed', '0'], cwd=case, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup)
            client = None
            try:
                ready = Path(str(state) + '.ready')
                deadline = time.monotonic() + 5
                while not ready.exists():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise TimeoutError('readiness publication')
                    time.sleep(.01)
                # Perform a live readiness challenge; the file alone is not a
                # response from the currently advancing controller process.
                subprocess.run([sys.executable, str(args.ready_helper), '--serial', selected,
                                '--state', str(state), '--pid', str(process.pid), '--timeout', '3'],
                               check=True, capture_output=True, timeout=5)
                client = serial.Serial(peer, 57600, timeout=.1, write_timeout=2)
                client.reset_input_buffer()
                if client.write(b'nlE') != 3:
                    raise AssertionError('short command write')
                client.flush()
                if line(client, process) != IDENTITY:
                    raise AssertionError('identity reply differs')
                lcd = line(client, process)
                if not lcd.startswith(b'L:') or b'\xb0' not in lcd or b'\xc2\xb0' in lcd:
                    raise AssertionError(('LCD wire bytes differ', lcd))
                rows_lcd = json.loads(lcd[2:].decode('latin-1'))
                if not isinstance(rows_lcd, list) or len(rows_lcd) != 4 or any(
                        not isinstance(row, str) or len(row) != 20 for row in rows_lcd):
                    raise AssertionError(('invalid LCD rows', rows_lcd))
                initialized = line(client, process)
                if not initialized.startswith(b'D:') or json.loads(initialized[2:]) != dict(logType='I', logID=15, V=[]):
                    raise AssertionError('initialization reply differs')
                queries, end = 0, time.monotonic() + 3
                while time.monotonic() < end:
                    if client.write(b'n') != 1:
                        raise AssertionError('short identity query write')
                    client.flush()
                    if line(client, process) != IDENTITY:
                        raise AssertionError('repeated identity reply differs')
                    queries += 1
                    time.sleep(.05)
                # A quiet boundary also uses one-byte reads, so unexpected
                # trailing bytes cannot make a timed large read hang here.
                if client.read(1):
                    raise AssertionError('unexpected trailing response')
                client.close()
                client = None
                stop_console(process)
                if not checkpoint.is_file() or json.loads(checkpoint.read_text())['format'] != 'brewpi-emulator-checkpoint-v1':
                    raise AssertionError('orderly checkpoint missing')
                if json.loads(ready.read_text()).get('ready') is not False:
                    raise AssertionError('readiness left active')
                if (case / 'stdout').read_bytes():
                    raise AssertionError('protocol leaked to stdout')
                # Reacquisition proves both virtual handles were released.
                for port in [selected, peer]:
                    with serial.Serial(port, 57600, timeout=.1, write_timeout=2):
                        pass
                rows.append(dict(cycle=cycle, lcd=mode, queries=queries, exit=process.returncode,
                                 checkpoint=True, ready_after_exit=False, endpoints_reopened=True))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if client is not None:
                    client.close()
    return dict(status='passed', producer='native Windows Session 0 hidden console',
                executable_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                pair_sha256=hashlib.sha256(args.pair.read_bytes()).hexdigest(),
                helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                ready_helper_sha256=hashlib.sha256(args.ready_helper.read_bytes()).hexdigest(),
                lifecycle_helper_sha256=hashlib.sha256(Path(__file__).with_name('windows_application.py').read_bytes()).hexdigest(),
                pyserial=serial.VERSION, system=platform.platform(), cycles=rows)


def job_object(kernel):
    class Limits(ctypes.Structure):
        _fields_ = [('user', ctypes.c_int64), ('job_user', ctypes.c_int64), ('flags', w.DWORD),
                    ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t), ('active', w.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Limits), ('io', ctypes.c_uint64 * 6),
                    ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                    ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel.CloseHandle(handle)
        raise error
    return handle


def input_hashes(args):
    paths = [args.binary, args.pair, Path(__file__).resolve(),
             Path(__file__).with_name('windows_application.py').resolve(),
             args.ready_helper, args.ready_helper.with_name('windows_ready.py')]
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def supervise(kernel, command, directory, timeout):
    """Assign before releasing the stdin gate; bound and clean the entire job."""
    job = job_object(kernel)
    process = None
    try:
        with (directory / 'worker-stdout').open('wb') as out, (directory / 'worker-stderr').open('wb') as err:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err)
            if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            process.communicate(input=b'g', timeout=timeout)
            if process.returncode:
                raise RuntimeError('Session 0 worker failed; inspect private worker logs')
    finally:
        # The handle is not inherited. A timeout, exception, or supervisor exit
        # closes this job and terminates only its owned process descendants.
        kernel.CloseHandle(job)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('--pair', type=Path, required=True)
    parser.add_argument('--ready-helper', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cycles', type=int, default=6)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not __debug__ or os.name != 'nt' or platform.machine().upper() != 'AMD64':
        parser.error('native Windows AMD64 with assertions enabled required')
    if not 3 <= args.cycles <= 12 or args.output.exists():
        parser.error('3..12 cycles and a new report path required')
    for name in ['binary', 'pair', 'ready_helper']:
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.directory = args.directory.resolve()
    args.output = args.output.resolve()
    if args.output == args.directory or args.directory in args.output.parents:
        parser.error('--output must be outside the new case directory')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.ProcessIdToSessionId.argtypes = [w.DWORD, ctypes.POINTER(w.DWORD)]
    session = w.DWORD()
    if not kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)) or session.value != 0:
        parser.error('run through an actual Windows Session 0 launcher, such as SSH')
    if args.worker:
        if sys.stdin.buffer.read(1) != b'g':
            raise RuntimeError('supervisor did not assign the cleanup job')
        result = worker(args)
        (args.directory / 'worker-result.json').write_text(json.dumps(result, indent=2) + '\n')
        return
    args.directory.mkdir(exist_ok=False)
    inputs = input_hashes(args)
    command = [sys.executable, str(Path(__file__).resolve()), str(args.binary),
               '--pair', str(args.pair), '--ready-helper', str(args.ready_helper),
               '--directory', str(args.directory), '--output', str(args.output),
               '--cycles', str(args.cycles), '--worker']
    supervise(kernel, command, args.directory, args.cycles * 20 + 10)
    worker_result = args.directory / 'worker-result.json'
    if not worker_result.is_file():
        raise RuntimeError('Session 0 worker did not produce a report')
    if input_hashes(args) != inputs:
        # The public report is created only after validating every input.
        raise AssertionError('qualification inputs changed during execution')
    result = json.loads(worker_result.read_text())
    result['input_sha256'] = inputs
    with args.output.open('x') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(args.output.read_text())


if __name__ == '__main__':
    main()
