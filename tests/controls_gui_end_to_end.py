# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Opt-in real Tk keyboard/mouse bindings -> private IPC -> actual engine -> clean close."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from lcd_tests import Process, wait_for

exe=str(Path(sys.argv[1]).resolve())
mouse='--mouse' in sys.argv[2:]
with tempfile.TemporaryDirectory(prefix='rmx-controls-real-gui-') as tmp:
    root=Path(tmp)
    peer=root/'python3'
    peer.write_text('#!'+sys.executable+'\n'+'''# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
import importlib.util,json,os,socket,sys,time
from pathlib import Path
r=Path(os.environ['CONTROL_GUI_ROOT'])
# Load the actual helper selected by the actual executable, not a duplicate UI.
script=sys.argv[2]
spec=importlib.util.spec_from_file_location('real_helper',script)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
v=m.Viewer(socket.socket(fileno=3));v.channel.setblocking(False)
commands=['press','cw','press','press','door','door'];stage=0;waiting=False;statuses=[]
def step():
 global stage,waiting
 if (r/'go').exists() and v.ready and v.session and not v.pending and v.frame_epoch >= v.epoch:
  if waiting:
   statuses.append(v.status.cget('text'));waiting=False
   if stage==4:(r/'confirmed-rows.json').write_text(json.dumps(v.rows))
  if stage==len(commands):
   (r/'done.json').write_text(json.dumps(dict(actions=stage,statuses=statuses,door=v.door_open)))
   v.close();return
  command=commands[stage];widget=v.door_button if command=='door' else v.encoder
  key='Right' if command=='cw' else 'Return'
  if os.environ.get('CONTROL_GUI_MOUSE')=='1':
   if command=='press':widget=v.press_button
   if command=='cw':widget=v.buttons[2]
   widget.focus_force();v.root.update()
   x,y=(90,55) if command=='cw' and widget==v.encoder else ((55,55) if widget==v.encoder else (widget.winfo_width()//2,widget.winfo_height()//2))
   assert v.root.winfo_containing(widget.winfo_rootx()+x,widget.winfo_rooty()+y)==widget
   widget.event_generate('<Enter>',x=x,y=y)
   widget.event_generate('<ButtonPress-1>',x=x,y=y)
   widget.event_generate('<ButtonRelease-1>',x=x,y=y)
  else:
   widget.focus_force();v.root.update()
   widget.event_generate('<KeyPress-'+key+'>');widget.event_generate('<KeyRelease-'+key+'>')
  stage+=1;waiting=True
 v.root.after(100,step)
v.root.after(100,step)
v.run()
raise SystemExit(10 if v.closing else 0)
''')
    peer.chmod(0o755)
    env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ.get('PATH',''),
             PYTHONDONTWRITEBYTECODE='1',
             CONTROL_GUI_ROOT=str(root),CONTROL_GUI_MOUSE='1' if mouse else '0',TERM='xterm-256color',
             LC_ALL='en_US.UTF-8' if sys.platform=='darwin' else 'C.UTF-8')
    p=Process(exe,root/'instance','gui',env=env)
    try:
        p.command(b'E');p.command(b'j{mode:b,beerSet:20.023}')
        while not p.line().startswith(b'C:'):
            pass
        (root/'go').touch()
        wait_for(lambda:(root/'done.json').exists(),timeout=12)
        wait_for(lambda:p.proc.poll() is not None or (p.console() and False),timeout=5)
        result=json.loads((root/'done.json').read_text())
        assert result['actions']==6 and not result['door'],result
        assert 'Target committed' in result['statuses'],result
        assert p.proc.returncode==0,p.proc.returncode
        rows=json.loads((root/'confirmed-rows.json').read_text())
        assert 'Beer Const.' in rows[0] and '20.0' in rows[1][12:18],rows
    finally:
        p.close()
    checkpoint=json.loads(p.checkpoint.read_text())['engine']
    assert checkpoint['settings']['beerSet']==-14336,checkpoint['settings']
    assert checkpoint['settings']['mode']==ord('b')
    assert checkpoint['plant']['door_open'] is False
    print(json.dumps(dict(status='passed',input_method='Tk mouse events' if mouse else 'Tk keyboard events',checks=['real Tk bindings and focused door activation',
          'actual private IPC and engine confirmation','source-defined unrotated quantization',
          'modeled door round trip','deliberate GUI closure and checkpoint'],result=result)))
