# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Stage a local packaged-mode test input, expressly not an accepted release candidate."""
import argparse
import json
from pathlib import Path
import subprocess
from payload import FILES, native_arch, preflight, sha
from version import application_version, version_output


def main():
    preflight()
    parser=argparse.ArgumentParser()
    parser.add_argument('tree',type=Path)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--install-prefix',default='/usr/local')
    args=parser.parse_args()
    binary=args.tree/'bin/brewpi-emulator-rmx'
    root=Path(__file__).resolve().parents[2]
    actual=subprocess.check_output([str(binary.resolve()),'--version'],text=True).strip()
    if actual!=version_output(root):raise ValueError('staged executable version differs from source metadata')
    data=dict(schema=1,install_prefix=args.install_prefix,purpose='controlled mode fixture; not a release candidate',
              candidate_version=application_version(root),source_commit=args.source_commit,architecture=native_arch(),
              application_version_output=actual,
              files={name:sha(args.tree/name) for name in sorted(FILES)})
    with args.manifest.open('x') as output:output.write(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':main()
