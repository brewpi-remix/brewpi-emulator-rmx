# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Validate an extracted, original payload; never build or repair its contents."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

FILES = {'bin/brewpi-emulator-rmx', 'libexec/brewpi-emulator-rmx/wait-ready.py',
         'share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service',
         'share/doc/brewpi-emulator-rmx/LICENSE.md',
         'share/doc/brewpi-emulator-rmx/THIRD_PARTY_NOTICES.md',
         'share/doc/brewpi-emulator-rmx/operation.txt'}
MACHINES = {'amd64': 62, 'arm64': 183}


def preflight():
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
        raise RuntimeError('Python assertions must be enabled')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_arch():
    return {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64', 'AMD64': 'amd64'}[platform.machine()]


class Payload:
    def __init__(self, tree, manifest, architecture=None):
        preflight()
        self.tree = Path(tree).resolve()
        manifest_bytes=Path(manifest).read_bytes()
        self.manifest = json.loads(manifest_bytes)
        self.manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest()
        self.architecture = architecture or native_arch()
        m = self.manifest
        if type(m.get('schema')) is not int or m.get('schema') != 1 or m.get('candidate_version') != '0.0.1-rc.1':
            raise ValueError('unexpected candidate policy or manifest schema')
        if m.get('architecture') != self.architecture or self.architecture not in MACHINES:
            raise ValueError('payload architecture differs from execution target')
        if len(m.get('source_commit', '')) != 40 or any(c not in '0123456789abcdef' for c in m['source_commit']):
            raise ValueError('missing exact source commit')
        if not isinstance(m.get('application_version_output'), str) or not m['application_version_output']:
            raise ValueError('missing frozen version expectation')
        if os.environ.get('RMX_CANDIDATE_COMMIT') and m['source_commit']!=os.environ['RMX_CANDIDATE_COMMIT']:
            raise ValueError('payload source differs from frozen candidate commit')
        if set(m.get('files', {})) != FILES:
            raise ValueError('incomplete payload inventory')
        self.prefix=m.get('install_prefix')
        if self.prefix not in ['/usr/local','/opt/brewpi-emulator-rmx']:
            raise ValueError('unsupported payload install prefix')
        self.binary = self.tree / 'bin/brewpi-emulator-rmx'
        self.verify('initial')
        if (self.tree/'share/doc/brewpi-emulator-rmx/LICENSE.md').read_bytes()!=(Path(__file__).resolve().parents[2]/'LICENSE.md').read_bytes():
            raise ValueError('payload project license differs from reviewed MIT license')
        header = self.binary.read_bytes()[:64]
        if len(header) != 64 or header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != MACHINES[self.architecture]:
            raise ValueError('wrong executable ELF architecture')
        version = subprocess.check_output([str(self.binary), '--version'], text=True, timeout=5).strip()
        if version != m['application_version_output']:
            raise ValueError('application version differs from frozen manifest')

    def verify(self, phase, receipt=None):
        actual = {str(p.relative_to(self.tree)) for p in self.tree.rglob('*') if p.is_file() or p.is_symlink()}
        if actual != FILES:
            raise ValueError('payload contains missing or unexpected files')
        for name, expected in self.manifest['files'].items():
            path = self.tree / name
            if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file() or sha(path) != expected:
                raise ValueError('payload bytes changed: ' + name)
        record = dict(phase=phase, mode='packaged-input', manifest_sha256=self.manifest_sha256, source_commit=self.manifest['source_commit'],
                      candidate_version=self.manifest['candidate_version'], architecture=self.architecture,
                      files=self.manifest['files'])
        if receipt:
            with Path(receipt).open('a') as output:
                output.write(json.dumps(record, sort_keys=True) + '\n')
        return record


def selected():
    mode = os.environ.get('RMX_EXECUTION_MODE', 'source-build')
    preflight()
    if mode == 'source-build':
        if os.environ.get('RMX_PAYLOAD_ROOT') or os.environ.get('RMX_PAYLOAD_MANIFEST'):
            raise ValueError('payload inputs require packaged-input mode')
        return None
    if mode != 'packaged-input':
        raise ValueError('unknown execution mode')
    if not os.environ.get('RMX_CANDIDATE_COMMIT'):
        raise ValueError('packaged-input requires an exact expected candidate commit')
    return Payload(os.environ['RMX_PAYLOAD_ROOT'], os.environ['RMX_PAYLOAD_MANIFEST'])
