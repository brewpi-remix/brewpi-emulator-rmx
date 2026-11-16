# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Provision only an already-private mount/PID namespace, then drop privileges."""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

base=Path(sys.argv[1]).resolve();run=Path(sys.argv[2]).resolve();architecture=sys.argv[3];acceptance=sys.argv[4]=='acceptance'
if os.geteuid()!=0 or os.getpid()!=1:raise RuntimeError('private root-provisioned PID namespace required')
root=base/'rootfs'
def command(*args):subprocess.run(list(map(str,args)),check=True,timeout=20)
command('mount','--make-rprivate','/')
command('mount','--bind',root,root);command('mount','-o','remount,bind,ro',root)
for source,target,readonly in [(base/'source','source',True),(base/'refs','refs',True),(base/'payload','usr/local',True),
                               (base/'candidate.json','candidate.json',True),(run/'harness','harness',True),(run/'lab','lab',False),(run/'evidence','evidence',False)]:
    destination=root/target;command('mount','--bind',source,destination)
    if readonly:command('mount','-o','remount,bind,ro',destination)
command('mount','-t','proc','-o','nosuid,nodev,noexec','proc',root/'proc')
command('mount','-t','tmpfs','-o','mode=755,nosuid','tmpfs',root/'dev')
(root/'dev/pts').mkdir()
command('mount','-t','devpts','-o','newinstance,ptmxmode=0666,mode=0620,gid=5','devpts',root/'dev/pts')
(root/'dev/ptmx').symlink_to('pts/ptmx')
for name in ['null','zero','random','urandom']:
    destination=root/'dev'/name;destination.touch();command('mount','--bind','/dev/'+name,destination)
(root/'dev/fd').symlink_to('/proc/self/fd')
command('mount','-t','tmpfs','-o','mode=1777,nosuid,nodev','tmpfs',root/'tmp')
namespace=dict(pid_namespace=os.readlink('/proc/self/ns/pid'),uid=2001,rootfs_readonly=True,network_namespace=True,devices=['private devpts','null','zero','random','urandom'])
(run/'namespace.json').write_text(json.dumps(namespace)+'\n')
os.chroot(root);os.chdir('/lab')
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
env=dict(PATH='/opt/brewpi-test/bin:/usr/local/bin:/usr/bin:/bin',HOME='/lab/home',USER='brewpi',LOGNAME='brewpi',TZ='UTC',LC_ALL='C',
 PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',RMX_CANDIDATE_SNAPSHOT='019a7742a8bce8b37a80e61c6f3274046a99eab884f810feea1655cf402cec48')
args=['/usr/bin/setpriv','--reuid=2001','--regid=2001','--groups=2001,33','--bounding-set=-all','--no-new-privs','/opt/brewpi-test/bin/python3','-u','/harness/run.py','--architecture',architecture]
if acceptance:args+=['--acceptance']
if len(sys.argv)>5 and sys.argv[5]=='accelerated-only':args+=['--accelerated-only']
os.execve(args[0],args,env)
