# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Copy original test inputs to an explicitly selected SSH test host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import time

ROOT=Path(__file__).resolve().parents[2]
LOCAL=ROOT/'runs/r3/stage'


def ssh(host,args,**kwargs):
    return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,shlex.join(list(map(str,args)))],check=True,**kwargs)


def remote_python(host,code,*args):
    return ssh(host,['python3','-c',code,*args],capture_output=True,text=True).stdout


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def stage(host,arch):
    metadata=json.loads(remote_python(host,"import json,os,platform;from pathlib import Path;print(json.dumps(dict(home=str(Path.home()),uid=os.getuid(),machine=platform.machine(),kernel=platform.release(),cpus=os.cpu_count())))"))
    if metadata['machine']!={'amd64':'x86_64','arm64':'aarch64'}[arch]:raise RuntimeError('target machine architecture differs')
    image=json.loads((LOCAL/('rootfs-'+arch+'.json')).read_text())
    base=metadata['home']+'/.local/share/brewpi-emulator-rmx/r3/base-'+image['image_id'][7:19]
    ssh(host,['mkdir','-p',base]);ssh(host,['chmod','700',base])
    for name in ['rootfs-'+arch+'.tar.gz','inputs-'+arch+'.tar.gz']:
        subprocess.run(['scp','-q',str(LOCAL/name),host+':'+base+'/'+name],check=True)
    script='''import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]);arch=sys.argv[2];expected=sys.argv[3]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()
if sha(root/('rootfs-'+arch+'.tar.gz'))!=expected:raise RuntimeError('rootfs transfer checksum mismatch')
if not (root/'ready.json').exists():
 if (root/'rootfs').exists():raise RuntimeError('partial base exists; retain it and use a new preparation identity')
 (root/'rootfs').mkdir();os.umask(0o022)
 subprocess.run(['tar','--no-same-owner','-xpf',str(root/('rootfs-'+arch+'.tar.gz')),'-C',str(root/'rootfs')],check=True)
 subprocess.run(['tar','--no-same-owner','-xpf',str(root/('inputs-'+arch+'.tar.gz')),'-C',str(root)],check=True)
 for name in ['source','harness','refs','lab','evidence','proc','dev','tmp','usr/local']:(root/'rootfs'/name).mkdir(parents=True,exist_ok=True)
 (root/'rootfs/candidate.json').touch()
 (root/'ready.json').write_text(json.dumps(dict(status='prepared',architecture=arch,rootfs_export_sha256=expected)))
print(root)
'''
    remote_python(host,script,base,arch,image['export_sha256'])
    record=dict(host=host,architecture=arch,base=base,image=image,target=metadata)
    (LOCAL/('target-'+arch+'.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


def launch(host,arch,acceptance,accelerated_only=False):
    target=json.loads((LOCAL/('target-'+arch+'.json')).read_text())
    if target['host']!=host:raise RuntimeError('wrong selected host')
    name=('acceptance' if acceptance else 'pilot')+'-'+arch+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    root=LOCAL/name;root.mkdir();harness=root/'harness';harness.mkdir()
    originals={}
    for source in sorted((ROOT/'tests/sustained').iterdir()):
        if source.is_file():
            shutil.copyfile(source,harness/source.name);originals[source.name]=digest(source)
    (harness/'INPUTS.json').write_text(json.dumps(dict(schema=1,spdx_license_identifier='MIT',files=originals),sort_keys=True)+'\n')
    archive=root/'harness.tar.gz'
    with tarfile.open(archive,'w:gz') as out:out.add(harness,arcname='harness')
    remote=target['target']['home']+'/.local/share/brewpi-emulator-rmx/r3/'+name
    ssh(host,['mkdir',remote]);ssh(host,['chmod','700',remote])
    subprocess.run(['scp','-q',str(archive),host+':'+remote+'/harness.tar.gz'],check=True)
    remote_python(host,"import subprocess,sys;subprocess.run(['tar','--no-same-owner','-xpf',sys.argv[1]+'/harness.tar.gz','-C',sys.argv[1]],check=True)",remote)
    args=['sudo','-n','python3',remote+'/harness/supervise.py',target['base'],remote,arch,'--owner',str(target['target']['uid'])]
    if acceptance:args+=['--acceptance']
    if accelerated_only:args+=['--accelerated-only']
    command='nohup '+shlex.join(args)+' >'+shlex.quote(remote+'/outer.log')+' 2>&1 </dev/null & echo $!'
    pid=ssh(host,['sh','-c',command],capture_output=True,text=True).stdout.strip()
    receipt=dict(host=host,architecture=arch,remote_run=remote,base=target['base'],acceptance=acceptance,scope='accelerated-only' if accelerated_only else 'full',launcher_shell_pid=pid,harness_files=originals,harness_archive_sha256=digest(archive),target=target['target'],image=target['image'])
    (root/'launch.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['stage','launch']);parser.add_argument('host');parser.add_argument('architecture',choices=['arm64','amd64']);parser.add_argument('--accelerated-only',action='store_true');parser.add_argument('--acceptance',action='store_true');args=parser.parse_args()
    if not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9._-]*',args.host):raise ValueError('explicit SSH alias required')
    (stage if args.action=='stage' else lambda h,a:launch(h,a,args.acceptance,args.accelerated_only))(args.host,args.architecture)
