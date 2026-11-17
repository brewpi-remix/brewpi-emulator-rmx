# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Reader failure checks and native fault injection for the Session 0 supervisor."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import windows_session0 as session0


class ReaderChecks(unittest.TestCase):
    def test_short_reads_are_assembled_without_bulk_requests(self):
        client = Mock()
        client.read.side_effect = [b'', b'N', b':', b'{', b'}', b'\r', b'\n']
        self.assertEqual(session0.line(client, Mock(poll=lambda: None)), b'N:{}\r\n')
        self.assertTrue(all(call.args == (1,) for call in client.read.call_args_list))

    def test_deadline_and_process_exit_fail(self):
        client = Mock()
        with patch.object(session0.time, 'monotonic', side_effect=[0, 6]):
            with self.assertRaises(TimeoutError):
                session0.line(client, Mock(poll=lambda: None))
        client.read.assert_not_called()
        with self.assertRaises(TimeoutError):
            session0.line(client, Mock(poll=lambda: 2))

    def test_embedded_line_break_is_not_accepted(self):
        client = Mock()
        client.read.side_effect = [bytes([x]) for x in b'N:{}\nX\r\n']
        with self.assertRaises(AssertionError):
            session0.line(client, Mock(poll=lambda: None))


@unittest.skipUnless(os.name == 'nt', 'Windows job objects required')
class SupervisorChecks(unittest.TestCase):
    def test_report_cannot_overwrite_case_outputs(self):
        with tempfile.TemporaryDirectory(prefix='session0-path-') as temp:
            root = Path(temp) / 'new-cases'
            result = subprocess.run([sys.executable, session0.__file__, sys.executable,
                                     '--pair', __file__, '--ready-helper', __file__,
                                     '--directory', str(root), '--output', str(root / '0' / 'checkpoint.json')],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--output must be outside', result.stderr)
            self.assertFalse(root.exists())

    def test_timeout_terminates_worker_and_descendant(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        with tempfile.TemporaryDirectory(prefix='session0-job-') as temp:
            root = Path(temp)
            record = root / 'pids.json'
            handles, errors = [], []
            def observe():
                try:
                    end = time.monotonic() + 5
                    while not record.exists():
                        if time.monotonic() >= end:
                            raise TimeoutError('fault worker did not start')
                        time.sleep(.01)
                    for pid in json.loads(record.read_text()):
                        handle = kernel.OpenProcess(0x100000, False, pid)
                        if not handle:
                            raise ctypes.WinError(ctypes.get_last_error())
                        handles.append(handle)
                except BaseException as error:
                    errors.append(error)
            observer = threading.Thread(target=observe)
            observer.start()
            command = [sys.executable, '-c',
                       "import json,os,subprocess,sys,time; from pathlib import Path; "
                       "gate=sys.stdin.buffer.read(1); gate!=b'g' and sys.exit(1); "
                       "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'],stdin=subprocess.DEVNULL); "
                       "Path(sys.argv[1]+'.tmp').write_text(json.dumps([os.getpid(),p.pid])); os.replace(sys.argv[1]+'.tmp',sys.argv[1]); time.sleep(120)", str(record)]
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    session0.supervise(kernel, command, root, 2)
                observer.join(timeout=6)
                self.assertFalse(observer.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(len(handles), 2)
                for handle in handles:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
            finally:
                observer.join(timeout=6)
                for handle in handles:
                    kernel.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
