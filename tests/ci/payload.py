# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Validate an extracted, original payload; never build or repair its contents."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import stat

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


def source_identity(manifest):
    schema=manifest.get('schema')
    if type(schema) is not int or schema not in [1,2]:raise ValueError('unsupported payload schema')
    if schema==1:
        commit=manifest.get('source_commit','')
        if not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('missing exact source commit')
        if not os.environ.get('RMX_CANDIDATE_COMMIT') or commit!=os.environ['RMX_CANDIDATE_COMMIT'] or os.environ.get('RMX_CANDIDATE_SNAPSHOT'):
            raise ValueError('commit payload requires an exact commit expectation, not a snapshot')
        return dict(source_commit=commit)
    snapshot=manifest.get('source_snapshot_sha256','');base=manifest.get('base_commit','')
    if manifest.get('source_commit') is not None or not isinstance(snapshot,str) or len(snapshot)!=64 or any(c not in '0123456789abcdef' for c in snapshot) or not isinstance(base,str) or len(base)!=40 or any(c not in '0123456789abcdef' for c in base):
        raise ValueError('invalid provisional snapshot identity')
    if not os.environ.get('RMX_CANDIDATE_SNAPSHOT') or snapshot!=os.environ['RMX_CANDIDATE_SNAPSHOT'] or os.environ.get('RMX_CANDIDATE_COMMIT'):
        raise ValueError('provisional payload requires exact snapshot expectation, not a candidate commit')
    return dict(source_commit=None,base_commit=base,source_snapshot_sha256=snapshot)


class Payload:
    def __init__(self, tree, manifest, architecture=None):
        preflight()
        self.tree = Path(tree).resolve()
        manifest_bytes=Path(manifest).read_bytes()
        self.manifest = json.loads(manifest_bytes)
        self.manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest()
        self.architecture = architecture or native_arch()
        m = self.manifest
        if m.get('candidate_version') != '0.0.1-rc.1':
            raise ValueError('unexpected candidate policy or manifest schema')
        if m.get('architecture') != self.architecture or self.architecture not in MACHINES:
            raise ValueError('payload architecture differs from execution target')
        self.source_identity=source_identity(m)
        if not isinstance(m.get('application_version_output'), str) or not m['application_version_output']:
            raise ValueError('missing frozen version expectation')
        if set(m.get('files', {})) != FILES:
            raise ValueError('incomplete payload inventory')
        if m['schema']==2 and m.get('file_modes')!={name:(0o755 if name.startswith(('bin/','libexec/')) else 0o644) for name in FILES}:
            raise ValueError('incorrect payload file modes')
        if m['schema']==2:
            import sys
            sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'release'))
            from artifacts import source_record
            record=source_record(Path(__file__).resolve().parents[2])
            if record['source_snapshot_sha256']!=m['source_snapshot_sha256'] or record['base_commit']!=m['base_commit'] or m.get('source_commit_role')!='pending-reviewed-commit-binding':
                raise ValueError('driver/helper source differs from provisional payload identity')
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
        actual=set()
        for path in self.tree.rglob('*'):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):raise ValueError('nonregular payload input')
            if path.is_file():actual.add(str(path.relative_to(self.tree)))
        if actual != FILES:
            raise ValueError('payload contains missing or unexpected files')
        for name, expected in self.manifest['files'].items():
            path = self.tree / name
            if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file() or sha(path) != expected:
                raise ValueError('payload bytes changed: ' + name)
            if self.manifest['schema']==2 and stat.S_IMODE(path.stat().st_mode)!=self.manifest['file_modes'][name]:
                raise ValueError('payload mode changed: '+name)
        record = dict(phase=phase, mode='packaged-input', manifest_sha256=self.manifest_sha256, **self.source_identity,
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
    if not os.environ.get('RMX_CANDIDATE_COMMIT') and not os.environ.get('RMX_CANDIDATE_SNAPSHOT'):
        raise ValueError('packaged-input requires an exact expected candidate commit or provisional snapshot')
    return Payload(os.environ['RMX_PAYLOAD_ROOT'], os.environ['RMX_PAYLOAD_MANIFEST'])
