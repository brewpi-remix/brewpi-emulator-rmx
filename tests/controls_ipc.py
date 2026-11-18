# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Real executable private-IPC actions, stale/duplicate rejection, and door state."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from lcd_tests import Process, wait_for
exe=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='rmx-controls-ipc-') as tmp:
    base=Path(tmp)
    peer=base/'python3'
    peer.write_text('''#!/usr/bin/python3
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
import json,os,socket,time
from pathlib import Path
r=Path(os.environ['CONTROL_PEER_ROOT']);s=socket.socket(fileno=3);s.settimeout(.1)
s.send(b'{"version":2,"type":"ready"}')
frame=None; pending=False; index=0; identity=0; progress=0;stale_sent=False
commands=['press','cw','press','cw','press','door open','door open','door close']
end=time.monotonic()+15
while time.monotonic()<end:
 try:
  m=json.loads(s.recv(4097))
  if m['type']=='frame': frame=m
  if m['type']=='ack':
   frame['epoch']=m['epoch'];pending=False
   if m['status']!='State changed; retry':index+=1
   with (r/'acks').open('a') as f:f.write(json.dumps(m)+'\\n')
 except socket.timeout: pass
 if time.monotonic()>=progress:
  s.send(b'{"version":2,"type":"progress"}');progress=time.monotonic()+1
 if frame and (r/'go').exists() and not pending and index<len(commands):
  identity+=1
  epoch=frame['epoch']
  if os.environ['CONTROL_PEER_CASE']=='stale' and not stale_sent:
   epoch+=1;stale_sent=True
  packet=dict(version=2,type='action',session=frame['session'],id=identity,epoch=epoch,command=commands[index])
  s.send(json.dumps(packet).encode());pending=True
  if os.environ['CONTROL_PEER_CASE']=='duplicate' and index==0:s.send(json.dumps(packet).encode())
 if index==len(commands):
  (r/'done').write_text('done')
  # Keep draining frames/progress until the owner ends this private instance.
''')
    peer.chmod(0o755)
    for case in ('normal','stale','duplicate'):
        root=base/case;root.mkdir()
        env=dict(os.environ,PATH=str(base),TERM='xterm-256color',
                 LC_ALL='en_US.UTF-8' if sys.platform=='darwin' else 'C.UTF-8',
                 CONTROL_PEER_ROOT=str(root),CONTROL_PEER_CASE=case)
        p=Process(exe,root/'process','gui',env=env)
        try:
            p.command(b'E');p.command(b'j{mode:b,beerSet:20}')
            time.sleep(.1)
            while p.read_serial():p.wire=b''
            (root/'go').touch()
            if case=='duplicate':
                wait_for(lambda:b'duplicate GUI action' in p.console())
            else:
                wait_for(lambda:(root/'done').exists())
                acks=[json.loads(line) for line in (root/'acks').read_text().splitlines()]
                assert len(acks)==(9 if case=='stale' else 8)
                if case=='normal':
                    assert acks[4]['status']=='Target committed',acks
                    assert acks[5]['status']=='Door opened' and acks[6]['status']=='Door unchanged'
                else:
                    assert acks[0]['status']=='State changed; retry',acks
            time.sleep(.1)
            while p.read_serial():p.wire=b''
            if case!='duplicate':assert p.command(b'n').startswith(b'N:')
        finally:
            # Drain any annotation replies before asking for a final identity.
            time.sleep(.1)
            while p.read_serial():p.wire=b''
            p.close()
        data=json.loads(p.checkpoint.read_text())['engine']
        if case=='normal':assert data['settings']['beerSet']==-14285,data['settings']
        if case=='duplicate':assert data['settings']['beerSet']==-14336 and 'menu' in data
print('Private IPC ordered actions, explicit commits, door no-op, stale epochs, duplicate rejection with retained continuation passed')
