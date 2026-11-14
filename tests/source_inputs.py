# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Hash original build/test/install inputs separately from external evidence."""
import hashlib
from pathlib import Path


def inventory(root):
    root=Path(root)
    paths=[root/name for name in ['CMakeLists.txt','LICENSE.md','THIRD_PARTY_NOTICES.md','AGENTS.md','CONTRACT.md','CONTRIBUTING.md','README.md']]
    for folder in ['.github','src','tests','scripts','systemd','config','docs','engineering','cmake']:
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
