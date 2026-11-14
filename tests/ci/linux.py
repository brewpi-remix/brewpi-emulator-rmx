# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Bounded disposable Linux guest; no socket mount or release artifact upload."""
import base64
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time
from gate import emit_receipt
from payload import preflight

ROOT=Path(__file__).resolve().parents[2]


def remove_container(cid):
    handlers={sig:signal.signal(sig,signal.SIG_IGN) for sig in [signal.SIGINT,signal.SIGTERM]}
    try:
        container=Path(cid).read_text().strip()
        if not container:raise RuntimeError('empty owned container identity')
        subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=30)
        if subprocess.check_output(['docker','ps','-aq','--no-trunc','--filter','id='+container],text=True,timeout=15).strip():
            raise RuntimeError('CI container removal not verified')
    finally:
        for sig,handler in handlers.items():signal.signal(sig,handler)


def main():
    preflight()
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    lane=sys.argv[1]
    image=os.environ.get('RMX_CI_IMAGE','brewpi-emulator-ci:r2')
    host=platform.machine()
    arch=lane.split('-')[1]
    if host!={'amd64':'x86_64','arm64':'aarch64'}[arch]:raise ValueError('native runner required; emulation is not accepted')
    subprocess.run(['docker','build','-t',image,'-f',str(ROOT/'tests/ci/Dockerfile'),str(ROOT/'tests/ci')],check=True)
    image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip()
    parent=ROOT/'runs/ci'
    parent.mkdir(parents=True,exist_ok=True)
    if (parent/lane).exists():raise ValueError('CI evidence directory must be new')
    with tempfile.TemporaryDirectory() as temporary:
        cid=Path(temporary)/'container.cid'
        args=['docker','run','--rm','--init','--user',str(os.getuid())+':'+str(os.getgid()),'-e','HOME=/tmp/rmx-ci-home','--cidfile',str(cid),'--network','none',
              '-v',str(ROOT)+':/work:ro','-v',str(parent)+':/work/runs/ci',
              '-v',os.environ['GITHUB_EVENT_PATH']+':/event.json:ro',
              '-e','GITHUB_EVENT_PATH=/event.json','-e','RMX_DEFER_RECEIPT=1',
              '-e','RMX_HOST_MACHINE='+host]
        for name in ['GITHUB_SHA','GITHUB_EVENT_NAME','GITHUB_WORKFLOW_REF','GITHUB_WORKFLOW_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT']:
            args+=['-e',name+'='+os.environ[name]]
        args += [image_id,'sh','-c','mkdir -p "$HOME" && git config --global --add safe.directory /work && exec python3 /work/tests/ci/gate.py "$1" "/work/runs/ci/$1"','sh',lane]
        try:
            subprocess.run(args,check=True,timeout=3300)
        finally:
            if cid.exists():
                remove_container(cid)
            else:raise RuntimeError('missing owned container identity')

    if lane.endswith('-release'):
        floor_image=image+'-floor'
        subprocess.run(['docker','build','--build-arg','BASE='+image,'-t',floor_image,
                        '-f',str(ROOT/'tests/ci/floor.Dockerfile'),str(ROOT/'tests/ci')],check=True,timeout=2400)
        floor_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',floor_image],text=True).strip()
        with tempfile.TemporaryDirectory() as temporary:
            cid=Path(temporary)/'floor.cid'
            try:
                subprocess.run(['docker','run','--rm','--init','--user',str(os.getuid())+':'+str(os.getgid()),'--cidfile',str(cid),'--network','none',
                    '-v',str(ROOT)+':/work:ro','-v',str(parent)+':/output',floor_id,
                    'python3','/work/tests/ci/offline.py','/output/'+lane+'/minimum-tools'],check=True,timeout=600)
            finally:
                if not cid.exists():raise RuntimeError('missing floor container identity')
                remove_container(cid)
        receipt=parent/lane/'receipt.json'
        row=json.loads(receipt.read_text())
        floor=json.loads((parent/lane/'minimum-tools/offline-results.json').read_text())
        floor['image_id']=floor_id
        row['checks'].append(floor)
        receipt.write_text(json.dumps(row,indent=2)+'\n')

    # The guest's receipt/output is accepted only when the wrapper also exits successfully.
    (parent/lane/'guest-image.json').write_text(json.dumps(dict(image_id=image_id,host_machine=host))+'\n')
    row=json.loads((parent/lane/'receipt.json').read_text())
    row['finished']=time.time()
    row['cleanup_verified']=True
    row['image_id']=image_id
    (parent/lane/'receipt.json').write_text(json.dumps(row,indent=2)+'\n')
    emit_receipt(row,os.environ['GITHUB_OUTPUT'])


def entry():
    output=ROOT/'runs/ci'/sys.argv[1]
    existed=output.exists()
    try:main()
    except BaseException as exc:
        if not existed:
            output.mkdir(parents=True,exist_ok=True)
            primary=output/'receipt.json'
            if primary.exists():primary.rename(output/'receipt-before-wrapper-failure.json')
            primary.write_text(json.dumps(dict(status='failed',lane=sys.argv[1],stage='wrapper',error=type(exc).__name__))+'\n')
        raise


if __name__=='__main__':entry()
