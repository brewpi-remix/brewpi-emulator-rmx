# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Offline failure checks for the opt-in physical bench runner; no serial I/O."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import arduino_characterization as subject


class Port:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeBench:
    def __init__(self, connection, directory):
        self.trace = (directory / 'wire.jsonl').open('x')
        self.checks = []

    def collect(self, seconds):
        return b''

    def read(self, command, prefix):
        return {
            'N': {'s': 5},
            'S': {'mode': 'o', 'beerSet': None, 'fridgeSet': None},
            'C': {'tempFormat': 'C'},
            'd': [dict(i=i, f=f, h=2, p=14, d=0, j=0, a=rom)
                  for i, f, rom in [(0, 9, '2800000000000001'),
                                    (1, 5, '2800000000000002'),
                                    (2, 6, '2800000000000003')]],
        }[prefix]


class Restoration(unittest.TestCase):
    def exercise(self, failure, restore_failure=None):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'evidence'
            args = ['bench', '--port', 'synthetic-never-opened', '--output', str(output),
                    '--authorize-hardware']
            serial = SimpleNamespace(__version__='synthetic', Serial=lambda *a, **kw: Port())
            with patch.dict(sys.modules, {'serial': serial}), patch.object(sys, 'argv', args), \
                    patch.object(subject.signal, 'signal'), patch.object(subject, 'Bench', FakeBench), \
                    patch.object(subject, 'run', side_effect=failure) as experiment, \
                    patch.object(subject, 'restore', side_effect=restore_failure) as restore, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = subject.main()
            self.assertEqual(result, 1)
            experiment.assert_called_once()
            restore.assert_called_once()
            return json.loads((output / 'report.json').read_text())

    def test_experiment_exception_still_restores(self):
        report = self.exercise(RuntimeError('synthetic dropped reply'))
        self.assertEqual(report['status'], 'interrupted')
        self.assertTrue(report['restored'])
        self.assertIn('dropped reply', report['error'])

    def test_operator_interrupt_still_restores(self):
        report = self.exercise(KeyboardInterrupt())
        self.assertTrue(report['restored'])
        self.assertIn('KeyboardInterrupt', report['error'])

    def test_restoration_failure_is_not_reported_as_success(self):
        report = self.exercise(RuntimeError('synthetic experiment failure'),
                               RuntimeError('synthetic restore failure'))
        self.assertFalse(report['restored'])
        self.assertIn('restore failure', report['restore_error'])


if __name__ == '__main__':
    unittest.main()
