# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise provisioned tool floors without Git, sibling references, or downloads."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_inputs import inventory
from native import run
from payload import preflight


def main():
    preflight()
    original=Path(__file__).resolve().parents[2]
    output=Path(sys.argv[1]).resolve();output.mkdir(parents=True,exist_ok=False)
    source=output/'source';source.mkdir()
    for name in inventory(original):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original/name,target)
    assert not (source/'.git').exists()
    cmake='/opt/floor-cmake/bin/cmake';python='/opt/floor-python/bin/python3.9'
    assert subprocess.check_output([cmake,'--version'],text=True).splitlines()[0]=='cmake version 3.16.9'
    assert subprocess.check_output([python,'--version'],text=True).strip()=='Python 3.9.25'
    report=run(source,output/'build','release',cmake,python)
    (output/'offline-results.json').write_text(json.dumps(dict(status='passed',network='disabled by caller',
        source_git=False,reference_checkouts=False,build=report),indent=2)+'\n')


if __name__=='__main__':main()
