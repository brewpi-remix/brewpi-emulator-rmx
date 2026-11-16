# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Run all six native suites with a CMake-3.16-compatible CTest invocation."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import shutil
import xml.etree.ElementTree as ET
from payload import preflight, sha

SUITES = {'model', 'dynamics', 'process',
          'protocol-fixtures', 'protocol-edges', 'pty'}


def validate_build(build):
    build=Path(build)
    tests = list((build / 'Testing').glob('*/Test.xml'))
    if len(tests) != 1:
        raise ValueError('missing CTest execution report')
    rows = ET.parse(tests[0]).findall('./Testing/Test')
    if {r.findtext('Name') for r in rows} != SUITES or len(rows) != 6 or any(r.get('Status') != 'passed' for r in rows):
        raise ValueError('not all six named native suites passed')
    fixtures = json.loads((build / 'test-results/fixtures.json').read_text())
    if fixtures['counts'] != dict(passed=48, unresolved_reference_characterization=9):
        raise ValueError('fixture coverage differs')
    return fixtures


def copy_test_log(build, destination):
    temporary=Path(build)/'Testing/Temporary'
    logs=[p for p in [temporary/'LastTest.log',*temporary.glob('LastTest_*.log')] if p.is_file()]
    if len(logs)!=1:raise ValueError('missing or ambiguous CTest log')
    shutil.copyfile(logs[0],destination)


def save_execution(build, kind):
    fixtures=validate_build(build)
    report=dict(status='passed',kind=kind,suites=sorted(SUITES),counts=fixtures['counts'])
    (Path(build)/'test-results/execution.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(root, build, kind, cmake='cmake', python=sys.executable):
    preflight()
    root, build = Path(root).resolve(), Path(build).resolve()
    build.mkdir(parents=True, exist_ok=False)
    commands = [[cmake, '-S', str(root), '-B', str(build), '-DCMAKE_BUILD_TYPE=' + ('Release' if kind == 'release' else 'Debug'),
                 '-DCMAKE_INSTALL_PREFIX=/usr/local', '-DPython3_EXECUTABLE=' + python, '-DRMX_SANITIZERS=' + ('ON' if kind == 'sanitize' else 'OFF')],
                [cmake, '--build', str(build), '-j2'],
                [str(Path(cmake).with_name('ctest')) if '/' in cmake else 'ctest', '-T', 'Test', '--output-on-failure']]
    for i, command in enumerate(commands):
        with (build / ('step-%d.log' % i)).open('w') as output:
            try:
                subprocess.run(command, cwd=build, stdout=output, stderr=subprocess.STDOUT, check=True)
            except subprocess.CalledProcessError:
                output.flush()
                # Native tests/builds contain original project diagnostics only.
                print((build/('step-%d.log' % i)).read_text()[-24000:],file=sys.stderr)
                raise
    fixtures = validate_build(build)
    report = dict(status='passed', kind=kind, suites=sorted(SUITES), counts=fixtures['counts'],
                  machine=platform.machine(), system=platform.system(), python=subprocess.check_output([python,'-c','import sys; print(sys.version)'],text=True).strip(),
                  compiler=subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
                  cmake=subprocess.check_output([cmake, '--version'], text=True).splitlines()[0],
                  executable_sha256=sha(build / 'brewpi-emulator-rmx'))
    (build / 'execution.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('build')
    parser.add_argument('kind', choices=['release', 'debug', 'sanitize'])
    parser.add_argument('--cmake', default='cmake')
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[2], args.build, args.kind, args.cmake, args.python)
