# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Native Windows build/core receipts; provider and desktop qualification are separate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from source_inputs import inventory
sys.path.insert(0, str(ROOT / 'release'))
from windows import native
SUITES = {'controls', 'model', 'dynamics', 'protocol-fixtures', 'protocol-edges'}


def run(output):
    if os.name != 'nt' or platform.machine().upper() != 'AMD64' or not __debug__:
        raise ValueError('native Windows AMD64 with assertions required')
    native_identity = native(allow_server=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = inventory(ROOT)
    build = output / 'build'
    commands = [['cmake', '-S', str(ROOT), '-B', str(build), '-A', 'x64',
                 '-DPython3_EXECUTABLE=' + sys.executable],
                ['cmake', '--build', str(build), '--config', 'Release', '-j', '4'],
                ['ctest', '-C', 'Release', '-T', 'Test', '--output-on-failure']]
    for index, command in enumerate(commands):
        with (output / ('step-' + str(index) + '.log')).open('w') as log:
            subprocess.run(command, cwd=build if index == 2 else ROOT, stdout=log,
                           stderr=subprocess.STDOUT, timeout=600, check=True)
    reports = list((build / 'Testing').glob('*/Test.xml'))
    if len(reports) != 1:
        raise ValueError('missing or ambiguous native CTest report')
    rows = ET.parse(reports[0]).findall('./Testing/Test')
    if len(rows) != 5 or {r.findtext('Name') for r in rows} != SUITES or any(r.get('Status') != 'passed' for r in rows):
        raise ValueError('all five named Windows core suites must pass')
    fixtures = json.loads((build / 'test-results/fixtures.json').read_text())
    if fixtures['counts'] != dict(passed=48, unresolved_reference_characterization=9):
        raise ValueError('fixture classification differs')
    if inventory(ROOT) != inputs:
        raise ValueError('source inputs changed during execution')
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    hosted = os.environ.get('GITHUB_ACTIONS') == 'true'
    if hosted and head != os.environ.get('GITHUB_SHA'):
        raise ValueError('hosted event and checkout differ')
    result = dict(status='passed', producer='github-actions' if hosted else 'local-native-execution',
                  source_commit=head if hosted else None, base_commit=head,
                  source_inputs_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
                  workflow_ref=os.environ.get('GITHUB_WORKFLOW_REF'), workflow_sha=os.environ.get('GITHUB_WORKFLOW_SHA'),
                  run_id=os.environ.get('GITHUB_RUN_ID'), run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
                  suites=sorted(SUITES), counts=fixtures['counts'],
                  system=platform.platform(), architecture=platform.machine(), native_identity=native_identity,
                  executable_sha256=hashlib.sha256((build / 'Release/brewpi-emulator-rmx.exe').read_bytes()).hexdigest(),
                  provider_desktop_package_acceptance='separate native qualification; not established by this lane')
    with (output / 'receipt.json').open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
