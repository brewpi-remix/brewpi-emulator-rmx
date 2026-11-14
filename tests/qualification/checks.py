# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative/byte-preservation tests for the operational readiness gate."""
if not __debug__:
    raise SystemExit("Python assertions must be enabled")

import importlib.util
import os
from pathlib import Path
import pty
import tempfile
import termios
import tty
import unittest

spec=importlib.util.spec_from_file_location('readiness',Path(__file__).resolve().parents[2]/'scripts/wait-ready.py')
readiness=importlib.util.module_from_spec(spec);spec.loader.exec_module(readiness)


class ReadinessChecks(unittest.TestCase):
    def test_raw_endpoint_preserves_queued_bytes(self):
        master,slave=pty.openpty()
        try:
            tty.setraw(slave)
            with tempfile.TemporaryDirectory() as temporary:
                link=Path(temporary)/'serial';link.symlink_to(os.ttyname(slave))
                expected=b'D:{"logType":"W","logID":3,"V":[]}\r\n'
                os.write(master,expected)
                readiness.wait_ready(link,os.getpid(),.2)
                self.assertEqual(os.read(slave,4096),expected)
        finally:
            os.close(master);os.close(slave)

    def test_regular_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'regular';target.write_bytes(b'original')
            link=Path(temporary)/'serial';link.symlink_to(target)
            with self.assertRaises(TimeoutError):readiness.wait_ready(link,os.getpid(),.03)
            self.assertEqual(target.read_bytes(),b'original')

    def test_cooked_terminal_is_rejected_without_mutation(self):
        master,slave=pty.openpty()
        try:
            original=termios.tcgetattr(slave)
            with tempfile.TemporaryDirectory() as temporary:
                link=Path(temporary)/'serial';link.symlink_to(os.ttyname(slave))
                with self.assertRaises(TimeoutError):readiness.wait_ready(link,os.getpid(),.03)
                self.assertEqual(termios.tcgetattr(slave),original)
        finally:
            os.close(master);os.close(slave)

    def test_other_raw_flags_are_checked_without_mutation(self):
        master,slave=pty.openpty()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                link=Path(temporary)/'serial';link.symlink_to(os.ttyname(slave))
                for index,flag in [(0,termios.ICRNL),(0,termios.IXON),(3,termios.ISIG),(3,termios.IEXTEN)]:
                    with self.subTest(flag=flag):
                        tty.setraw(slave)
                        changed=termios.tcgetattr(slave);changed[index]|=flag
                        termios.tcsetattr(slave,termios.TCSANOW,changed)
                        before=termios.tcgetattr(slave)
                        with self.assertRaises(TimeoutError):readiness.wait_ready(link,os.getpid(),.03)
                        self.assertEqual(termios.tcgetattr(slave),before)
        finally:
            os.close(master);os.close(slave)

    def test_dead_process_is_rejected(self):
        with self.assertRaises(ProcessLookupError):readiness.wait_ready('/absent',99999999,.1)

    def test_invalid_limits_are_rejected(self):
        for pid,timeout in [(0,1),(-1,1),(os.getpid(),0),(os.getpid(),float('nan')),(os.getpid(),301)]:
            with self.assertRaises(ValueError):readiness.wait_ready('/absent',pid,timeout)


if __name__=='__main__':
    unittest.main()
