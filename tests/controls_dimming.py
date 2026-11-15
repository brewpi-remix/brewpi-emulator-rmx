# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise actual wall-clock dimming, wake-and-act, and keep-on terminals."""
import os
from pathlib import Path
import sys
import tempfile
import time
from lcd_tests import Process, wait_for
exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='rmx-dim-') as tmp:
    env = dict(os.environ, TERM='xterm-256color', LC_ALL='en_US.UTF-8' if sys.platform=='darwin' else 'C.UTF-8')
    normal = Process(exe,Path(tmp)/'normal','terminal',env=env)
    keep = Process(exe,Path(tmp)/'keep','terminal',env=env,extra=('--lcd-keep-on',))
    try:
        wait_for(lambda:b'> ' in normal.console() and b'> ' in keep.console())
        deadline=time.monotonic()+62
        while time.monotonic()<deadline:
            normal.console();keep.console();time.sleep(.1)
        assert b'\x1b[2m' in normal.console(), normal.buffer
        assert b'\x1b[2m' not in keep.console(), keep.buffer
        start=len(normal.buffer)
        os.write(normal.master,b'press\r')
        wait_for(lambda:b'Action accepted' in normal.console()[start:])
        assert b'\x1b[2m' not in normal.buffer[start:]
        os.write(normal.master,b'cw\r')
        time.sleep(.2)
        start=len(normal.console())
        os.write(normal.master,b'press\r')
        wait_for(lambda:b'Edit target' in normal.console()[start:])
    finally:
        normal.close();keep.close()
print('Real 60-second wall-clock dimming, first-press wake-and-act, and keep-on passed')
