# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Require complete passing child evidence and verified container removal."""
import json
from pathlib import Path
import sys


def validate(directory):
    def report(name):
        value=json.loads((directory/name).read_text())
        if value.get('status')!='passed':
            raise ValueError('nonpassing report: '+name)
        return value
    result=report('qualification-results.json')
    integrity=report('source-integrity.json')
    if integrity.get('unchanged') is not True or integrity.get('files',0)<=0:
        raise ValueError('source integrity was not verified')
    service=report('service-results.json')
    runtime=report('runtime-results/runtime-results.json')
    if not service.get('unit_commands_executed'):
        raise ValueError('service commands were not exercised')
    if len(runtime.get('checks',[]))!=9 or any(row.get('status')!='passed' for row in runtime['checks']):
        raise ValueError('incomplete runtime evidence')
    if result.get('runtime')!=runtime:
        raise ValueError('runtime summary differs from saved report')
    for kind in ['release','sanitize']:
        fixture=json.loads((directory/('native-'+kind)/'milestone3-fixtures.json').read_text())
        if fixture.get('counts')!=dict(passed=48,unresolved_reference_characterization=9):
            raise ValueError('incomplete native fixture evidence: '+kind)


def finish(directory, exit_code, cleanup_ok):
    error=None
    if exit_code==0:
        try:
            validate(directory)
            if not cleanup_ok:
                raise ValueError('owned container removal could not be verified')
        except Exception as exc:
            error=str(exc)
            exit_code=1
    if exit_code:
        primary=directory/'qualification-results.json'
        if primary.exists():primary.rename(directory/'qualification-before-launcher-failure.json')
        primary.write_text(json.dumps(dict(status='failed',stage='launcher',exit_code=exit_code,error=error))+'\n')
    (directory/'launcher-results.json').write_text(json.dumps(dict(
        status='passed' if exit_code==0 else 'failed',exit_code=exit_code,
        cleanup_verified=cleanup_ok,error=error))+'\n')
    return exit_code


if __name__=='__main__':
    sys.exit(finish(Path(sys.argv[1]),int(sys.argv[2]),sys.argv[3]=='yes'))
