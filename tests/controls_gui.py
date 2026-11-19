# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Real Tk action/focus/ack/dimming checks; optional hold permits visual inspection."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
import traceback

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lcd_viewer',root/'scripts/lcd-viewer.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
a.setblocking(False);b.setblocking(False)
v=module.Viewer(b)
commands=[];errors=[];sequence=0;epoch=0;door=False;completed=0;stale_blocked=0;mouse_checks=0

def frame(dim=False, unit='C', stale=False):
    global sequence
    sequence+=1
    a.send(json.dumps(dict(version=2,type='frame',sequence=sequence,
        rows=['Mode   Beer Const.  ',f'Beer   20.0  20.0 °{unit}',f'Fridge 19.5  19.0 °{unit}','Idling for     00m00'],
        dim=dim,door=door,equipment=[0,1,1,0],status='Ready',session='visual-test',epoch=epoch-1 if stale else epoch)).encode())

def pump():
    global epoch,door
    try:
        for _ in range(8):
            try:m=json.loads(a.recv(4097))
            except BlockingIOError:break
            if m['type']=='error':raise AssertionError('viewer reported error')
            if m['type']=='action':
                assert m['epoch']==epoch,m
                commands.append(m['command']);epoch+=1
                if m['command'].startswith('door '):door=m['command']=='door open'
                a.send(json.dumps(dict(version=2,type='ack',session='visual-test',id=m['id'],epoch=epoch,status='Action accepted')).encode())
                if len(commands)==1:
                    frame(stale=True)
                    v.root.after(55,lambda:check(block_stale))
                    v.root.after(120,frame)
                else:
                    frame()
        a.send(b'{"version":2,"type":"heartbeat"}')
        v.root.after(50,pump)
    except BaseException as exc:
        errors.append(repr(exc));v.root.destroy()

def check(fn):
    try:fn()
    except BaseException as exc:errors.append(traceback.format_exc());v.root.destroy()

def key(widget,name,release=True):
    widget.focus_force();v.root.update()
    widget.event_generate('<KeyPress-'+name+'>')
    if release:widget.event_generate('<KeyRelease-'+name+'>')

def block_stale():
    global stale_blocked
    assert v.frame_epoch < v.epoch and v.pending is None
    v.action('press')
    assert v.pending is None and 'Busy' in v.status.cget('text')
    stale_blocked+=1

def held():
    key(v.press_button,'Return',False)
    for offset in (60,120,180):v.root.after(offset,lambda:key(v.press_button,'Return',False))
    v.root.after(240,lambda:v.press_button.event_generate('<KeyRelease-Return>'))

def assertions():
    global completed
    assert commands==['press','cw','door open'],commands
    assert v.door_button.cget('text')=='Close door'
    assert v.equipment==[0,1,1,0]
    assert v.door_tip.text.startswith('Door open')
    assert str(v.images['door open']) in str(v.door_button.cget('image')), v.door_button.cget('image')
    for item in v.equipment_canvas.find_all():
        x0,y0,x1,y1=v.equipment_canvas.bbox(item)
        assert 0<=x0<x1<=v.equipment_canvas.winfo_width() and 0<=y0<y1<=v.equipment_canvas.winfo_height()
    foreground = v.canvas.itemcget(v.cells[0],'fill')
    assert foreground=='#384624'
    def luminance(color):
        rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in rgb]
        return sum(x*w for x,w in zip(linear,(.2126,.7152,.0722)))
    dark,light=sorted((luminance(foreground),luminance(v.canvas.cget('background'))))
    assert (light+.05)/(dark+.05)>=4.5, 'dimmed LCD text contrast is insufficient'
    for item in v.cells:
        x0,y0,x1,y1=v.canvas.bbox(item)
        assert 0<=x0<x1<=v.canvas.winfo_width() and 0<=y0<y1<=v.canvas.winfo_height()
    for button in v.buttons + [v.door_button]:
        assert button.winfo_rootx() >= v.root.winfo_rootx()
        assert button.winfo_rootx() + button.winfo_width() <= v.root.winfo_rootx() + v.root.winfo_width(), (button.cget('text'), button.winfo_geometry(), v.root.winfo_geometry())
        assert button.winfo_rooty() + button.winfo_height() <= v.root.winfo_rooty() + v.root.winfo_height(), (button.cget('text'), button.winfo_geometry(), v.root.winfo_geometry())
    assert len(v.rows)==4 and all(len(row)==20 for row in v.rows)
    assert v.rows[1][18:]=='°F'
    completed+=1
    print('Real Tk focus, held-key suppression, door keyboard isolation, acknowledgment, dimming, degree cells and geometry passed',flush=True)


def mouse_pass(size_index=0, index=0):
    """Exercise actual Tk hit lookup and mouse bindings, not widget.invoke()."""
    global mouse_checks
    sizes=['560x360','720x420','960x500']
    if size_index==len(sizes):
        v.root.after(90000 if '--hold' in sys.argv else 20,v.root.destroy)
        return
    cases=[(v.press_button,None,None,'press'),(v.encoder,15,55,'ccw'),
           (v.encoder,95,55,'cw'),(v.buttons[0],None,None,'ccw'),
           (v.buttons[2],None,None,'cw'),(v.door_button,None,None,'door close'),
           (v.door_button,None,None,'door open')]
    if index==0:
        v.root.geometry(sizes[size_index]);v.root.update()
    if index==len(cases):
        v.root.after(120,lambda:check(lambda:mouse_pass(size_index+1)))
        return
    if v.pending or v.frame_epoch<v.epoch:
        v.root.after(50,lambda:check(lambda:mouse_pass(size_index,index)))
        return
    widget,x,y,command=cases[index]
    if x is None:x,y=widget.winfo_width()//2,widget.winfo_height()//2
    target=v.root.winfo_containing(widget.winfo_rootx()+x,widget.winfo_rooty()+y)
    assert target==widget,(sizes[size_index],command,str(target),str(widget))
    before=len(commands)
    widget.event_generate('<Enter>',x=x,y=y)
    widget.event_generate('<ButtonPress-1>',x=x,y=y)
    def release():
        widget.event_generate('<ButtonRelease-1>',x=x,y=y)
        def verify():
            global mouse_checks
            assert commands[before:]==[command],(sizes[size_index],command,commands[before:])
            assert v.pending is None and v.frame_epoch>=v.epoch
            mouse_checks+=1
            mouse_pass(size_index,index+1)
        v.root.after(160,lambda:check(verify))
    # Hold each center press long enough to detect repeated confirmation.
    v.root.after(450 if index==0 else 30,lambda:check(release))

v.root.after(100,frame)
v.root.after(150,pump)
v.root.after(300,lambda:check(held))
v.root.after(700,lambda:check(lambda:key(v.encoder,'Right')))
v.root.after(1000,lambda:check(lambda:key(v.door_button,'Return')))
v.root.after(1300,lambda:frame(True,'F'))
v.root.after(1500,lambda:check(assertions))
v.root.after(1600,lambda:v.root.geometry('560x360'))
v.root.after(1800,lambda:check(assertions))
v.root.after(1900,lambda:check(mouse_pass))
v.root.after(120000 if '--hold' in sys.argv else 20000,v.root.destroy)
v.run();a.close();b.close()
assert not errors and completed==2 and stale_blocked==1 and mouse_checks==21,(errors,completed,stale_blocked,mouse_checks)

# Actual standalone helper lease, not a mocked root.destroy callback.
import subprocess
left,right=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
process=subprocess.Popen([sys.executable,'-I',str(root/'scripts/lcd-viewer.py'),'--fd',str(right.fileno())],
    pass_fds=(right.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
right.close();left.settimeout(5)
try:
    assert json.loads(left.recv(4097))==dict(version=2,type='ready')
    left.close()
    out,err=process.communicate(timeout=12)
    assert process.returncode==0 and not err,(out,err)
finally:
    left.close()
    if process.poll() is None:process.kill();process.communicate()
report=dict(status='passed',python=sys.version,tk=v.root.tk.call('info','patchlevel'),
    completed_geometry_passes=completed,mouse_hit_checks=mouse_checks,stale_frame_guard=stale_blocked,actions=commands,standalone_parent_loss=True,
    visual_inspection='separate acceptance gate; this report covers real Tk interaction and geometry')
output=root/'test-results';output.mkdir(exist_ok=True)
(output/'controls-gui.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
