# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise the generated unit's commands, without claiming PID-1 activation."""
import configparser
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess


def exercise(unit, out):
    config=configparser.ConfigParser(interpolation=None)
    config.optionxform=str
    config.read(unit)
    assert config['Service']['User']=='brewpi' and config['Service']['Group']=='brewpi'
    mask=int(config['Service']['UMask'],8)
    start=shlex.split(config['Service']['ExecStart'].replace('%i','chamber1'))
    prefix=unit.parents[3]
    assert start[0]==str(prefix/'bin/brewpi-emulator-rmx'),'unit executable differs from installed payload'
    serial=Path(start[start.index('--serial')+1])
    state=Path(start[start.index('--state')+1])
    for path in [serial.parent,state.parent]:
        path.mkdir(parents=True,exist_ok=True)
        os.chown(path,2001,2001);os.chmod(path,0o700)
    transcript=out/'service-command.log'
    with transcript.open('w') as log:
        process=subprocess.Popen(start,user=2001,group=2001,extra_groups=[],
                                 stdout=log,stderr=subprocess.STDOUT,start_new_session=True,umask=mask)
        try:
            post=shlex.split(config['Service']['ExecStartPost'].replace('%i','chamber1').replace('${MAINPID}',str(process.pid)))
            assert post[0]==str(prefix/'libexec/brewpi-emulator-rmx/wait-ready.py'),'unit helper differs from installed payload'
            ready=subprocess.run(post,user=2001,group=2001,extra_groups=[],capture_output=True,text=True,timeout=15,umask=mask)
            log.write(ready.stdout+ready.stderr);log.flush()
            assert ready.returncode==0,ready.stderr
            probe=r'''import json,os,select,sys,time
fd=os.open(sys.argv[1],os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
buffer=b''
def line():
 global buffer
 deadline=time.monotonic()+3
 while b'\r\n' not in buffer:
  assert select.select([fd],[],[],max(0,deadline-time.monotonic()))[0]
  buffer+=os.read(fd,4096)
 row,buffer=buffer.split(b'\r\n',1)
 return row
assert line()==b'D:{"logType":"W","logID":3,"V":[]}'
os.write(fd,b'n')
identity=json.loads(line()[2:]);assert identity['v']=='0.2.13' and identity['s']==2 and identity['b']=='s'
os.write(fd,b'E');assert json.loads(line()[2:])==dict(logType='I',logID=15,V=[])
os.close(fd)
'''
            checked=subprocess.run(['python3','-c',probe,str(serial)],user=2001,group=2001,extra_groups=[],capture_output=True,text=True,timeout=10)
            assert checked.returncode==0,checked.stdout+checked.stderr
            foreign=subprocess.run(['runuser','-u','nobody','--','python3','-c',
                'import os,sys\ntry:os.open(sys.argv[1],os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)\nexcept PermissionError:print("denied")\nelse:raise SystemExit("unexpected access")',str(serial)],capture_output=True,text=True,timeout=3)
            assert foreign.returncode==0 and foreign.stdout.strip()=='denied'
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
        assert process.returncode==0
    assert not serial.is_symlink()
    image=json.loads(state.read_text())
    assert image['controller_version']==4 and state.stat().st_uid==2001 and state.stat().st_mode&0o777==0o600
    report=dict(status='passed',unit_commands_executed=True,uid=2001,foreign_access='denied',
                startup_w3_preserved=True,saved_state_mode='0600',clean_endpoint_removal=True,
                systemd_pid1_activation=False,systemd_namespace_policies_exercised=False)
    (out/'service-results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
