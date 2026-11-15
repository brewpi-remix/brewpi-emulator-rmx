# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Opt-in isolated Linux real-helper install test; no live host installation."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from lcd_tests import Process, wait_for

binary = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='rmx-lcd-installed-') as tmp:
    p = Process(binary, Path(tmp)/'instance', 'gui',
                env=dict(os.environ, PATH='/usr/bin:/bin', LC_ALL='C.UTF-8', TERM='xterm'))
    try:
        child_file = Path('/proc')/str(p.proc.pid)/'task'/str(p.proc.pid)/'children'
        child = int(wait_for(lambda: child_file.read_text().strip()))
        wait_for(lambda: b'lcd-viewer.py' in (Path('/proc')/str(child)/'cmdline').read_bytes())
        time.sleep(5.2) # past startup/progress deadline; Tk must actually respond
        assert b'+--------------------+' not in p.console()
        assert p.command(b'l').startswith(b'L:')
        os.kill(child, signal.SIGTERM)
        wait_for(lambda: b'\xc2\xb0C' in p.console())
        assert p.command(b'n').startswith(b'N:')
        assert b'send buffer 16384 bytes' in p.buffer, p.buffer
    finally:
        p.close()
print(json.dumps(dict(status='passed', checks=['installed real Tk helper mapping',
      'real Tk progress past five seconds', 'window child exit to Unicode terminal',
      'raw serial alive throughout', 'Linux SO_SNDBUF=16384'])))
