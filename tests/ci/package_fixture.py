# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Stage a local R2 mode-test input, expressly not an accepted release candidate."""
import argparse
import json
from pathlib import Path
import subprocess
from payload import FILES, native_arch, preflight, sha


def main():
    preflight()
    parser=argparse.ArgumentParser()
    parser.add_argument('tree',type=Path)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--install-prefix',default='/usr/local')
    args=parser.parse_args()
    binary=args.tree/'bin/brewpi-emulator-rmx'
    data=dict(schema=1,install_prefix=args.install_prefix,purpose='R2 controlled mode fixture; not a release candidate',
              candidate_version='0.0.1-rc.1',source_commit=args.source_commit,architecture=native_arch(),
              application_version_output=subprocess.check_output([str(binary.resolve()),'--version'],text=True).strip(),
              files={name:sha(args.tree/name) for name in sorted(FILES)})
    with args.manifest.open('x') as output:output.write(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':main()
