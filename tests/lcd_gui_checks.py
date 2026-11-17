# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Opt-in real Tk visual/layout checks; run in an isolated graphical session."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lcd_viewer', root/'scripts/lcd-viewer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
a.setblocking(False); b.setblocking(False)
viewer = module.Viewer(b)
errors = []

def send(unit, sequence):
    rows = ['Mode   Beer Const.  ', f'Beer   20.0  20.0 °{unit}',
            f'Fridge 19.5  19.0 °{unit}', 'Cooling for    03m12']
    a.send(json.dumps(dict(version=2, type='frame', sequence=sequence, rows=rows, dim=False, door=sequence == 2, equipment=([1,0,1,0] if sequence == 1 else [0,1,0,1] if sequence == 2 else [-1]*4), status='Ready', session='test', epoch=0)).encode())
    a.send(b'{"version":2,"type":"heartbeat"}')

def check(name, unit):
    try:
        assert viewer.ready
        assert viewer.rows[1][18:] == '°'+unit
        assert len(viewer.cells) == 80
        expected = [1,0,1,0] if viewer.sequence == 1 else [0,1,0,1] if viewer.sequence == 2 else [-1]*4
        assert viewer.equipment == expected
        assert bool(viewer.equipment_canvas.find_withtag('no')) == (expected[2] == 0)
        assert viewer.door_open == (viewer.sequence == 2)
        for item in viewer.equipment_canvas.find_all():
            x0,y0,x1,y1=viewer.equipment_canvas.bbox(item)
            assert 0<=x0<x1<=viewer.equipment_canvas.winfo_width() and 0<=y0<y1<=viewer.equipment_canvas.winfo_height()
        w, h = viewer.canvas.winfo_width(), viewer.canvas.winfo_height()
        for item in viewer.cells:
            x0, y0, x1, y1 = viewer.canvas.bbox(item)
            assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h, (name, w, h, (x0,y0,x1,y1))
        # Capture only this original test window in the disposable X server.
        with (output/(name+'.xwd')).open('wb') as stream:
            subprocess.run(['xwd', '-silent', '-id', str(viewer.root.winfo_id())],
                           stdout=stream, check=True, timeout=5)
    except BaseException as exc:
        errors.append(repr(exc))
        viewer.root.destroy()

viewer.root.after(100, lambda: send('C', 1))
viewer.root.after(300, lambda: check('normal-c', 'C'))
viewer.root.after(400, lambda: viewer.root.geometry('560x360'))
viewer.root.after(600, lambda: check('minimum-c', 'C'))
viewer.root.after(700, lambda: viewer.root.geometry('960x500'))
viewer.root.after(800, lambda: send('F', 2))
viewer.root.after(1000, lambda: check('large-f', 'F'))
viewer.root.after(1100, lambda: send('C', 3))
viewer.root.after(1300, lambda: check('unmodeled-c', 'C'))
viewer.root.after(1400, viewer.root.destroy)
viewer.run()
a.close(); b.close()
assert not errors, errors
report=dict(status='running', python=sys.version, tk=viewer.root.tk.call('info','patchlevel'),
            checks=['mapped/painted readiness', 'C/F degree cells', '80 independent cell bounds',
                    'normal/minimum/large real X11 rendering'])
(output/'result.json').write_text(json.dumps(report,indent=2)+'\n')

# Exercise the standalone helper's actual parent-loss lease. AF_UNIX datagram
# sockets provide no EOF, and a failed progress send must not strand Tk.
a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
process = subprocess.Popen([sys.executable, '-I', str(root/'scripts/lcd-viewer.py'),
                            '--fd', str(b.fileno())], pass_fds=(b.fileno(),),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
b.close(); a.settimeout(5)
try:
    assert json.loads(a.recv(4097)) == dict(version=2, type='ready')
    a.close()
    stdout, stderr = process.communicate(timeout=12)
    assert process.returncode == 0 and not stderr, (stdout, stderr)
finally:
    if process.poll() is None:
        process.kill(); process.communicate()
report['checks'].append('standalone helper exits on real parent-channel loss without callback errors')
report['status'] = 'passed'
(output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
