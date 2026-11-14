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


def validate_integration(directory):
    def passed(name):
        value=json.loads((directory/name).read_text())
        if value.get('status')!='passed':raise ValueError('nonpassing report: '+name)
        return value
    result=passed('integration-results.json')
    workflows=result.get('workflows',[])
    if len(workflows)!=17 or any(row.get('status')!='passed' for row in workflows) or result.get('browser_errors')!=[]:
        raise ValueError('incomplete integration workflow evidence')
    source=passed('source-integrity.json')
    if source.get('unchanged') is not True or source.get('files',0)<=0:
        raise ValueError('original source integrity was not verified')
    cleanup=passed('cleanup-results.json')
    if cleanup.get('errors')!=[] or not cleanup.get('host_exits') or any(code!=0 for code in cleanup['host_exits']):
        raise ValueError('application cleanup or host exit failed')
    integrity=json.loads((directory/'reference-code-integrity.json').read_text())
    if integrity.get('unchanged') is not True or integrity.get('checked_files',0)<=0:
        raise ValueError('reference integrity was not verified')
    fixture=json.loads((directory/'native-test-results/milestone3-fixtures.json').read_text())
    if fixture.get('counts')!=dict(passed=48,unresolved_reference_characterization=9):
        raise ValueError('incomplete integration native fixture evidence')


def finish(directory, exit_code, cleanup_ok, kind="qualification"):
    error=None
    if exit_code==0:
        try:
            (validate_integration if kind=="integration" else validate)(directory)
            if not cleanup_ok:
                raise ValueError('owned container removal could not be verified')
        except Exception as exc:
            error=str(exc)
            exit_code=1
    if exit_code:
        primary=directory/(kind+'-results.json')
        if primary.exists():primary.rename(directory/(kind+'-before-launcher-failure.json'))
        primary.write_text(json.dumps(dict(status='failed',stage='launcher',exit_code=exit_code,error=error))+'\n')
    (directory/'launcher-results.json').write_text(json.dumps(dict(
        status='passed' if exit_code==0 else 'failed',exit_code=exit_code,
        cleanup_verified=cleanup_ok,error=error))+'\n')
    return exit_code


if __name__=='__main__':
    sys.exit(finish(Path(sys.argv[1]),int(sys.argv[2]),sys.argv[3]=='yes',sys.argv[4] if len(sys.argv)>4 else 'qualification'))
