# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Use the original nine runtime checks in a toolchain-free disposable guest."""
import json
from pathlib import Path
import runpy
import shutil
import sys

for tool in ['c++','gcc','g++','cmake','make','ld','git','readelf']:
    if shutil.which(tool):raise RuntimeError('clean runtime unexpectedly contains '+tool)
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests/qualification'))
runpy.run_path(str(root/'tests/qualification/runtime.py'),run_name='__main__')
for name in ['packages.tsv','debs.sha256']:
    shutil.copyfile('/opt/rmx-inputs/'+name,Path('/qualification/results')/('runtime-'+name))
report=Path('/qualification/results/clean-environment.json')
report.write_text(json.dumps(dict(status='passed',compiler_linker_build_tools_absent=True,
    system_libraries='external Debian runtime packages',systemd_activation=False))+'\n')
