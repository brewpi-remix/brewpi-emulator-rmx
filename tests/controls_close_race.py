# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Stress explicit close and reserved child-exit shutdown without weakening deadlines."""
import os
from pathlib import Path
import sys
import tempfile
from lcd_tests import Process, peer, wait_for
exe=str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='rmx-close-race-') as tmp:
    root=Path(tmp);bindir=root/'bin';bindir.mkdir();peer(bindir)
    program=bindir/'python3'
    code=program.read_text().replace('seen=False', 'seen=False; first_heartbeat=None')
    code=code.replace("  if msg['type']=='frame':", "  if msg['type']=='heartbeat' and first_heartbeat is None:first_heartbeat=time.monotonic()\n  if msg['type']=='frame':")
    code=code.replace(" if mode in ('user-close','close-exit') and seen:", " if mode=='close-exit' and seen and first_heartbeat is not None:\n  time.sleep(max(0,first_heartbeat+.95-time.monotonic()))\n  s.close();time.sleep(.08);raise SystemExit(10)\n if mode in ('user-close','close-exit') and seen:")
    program.write_text(code)
    for index in range(int(sys.argv[2]) if len(sys.argv)>2 else 12):
        scenario='user-close' if index%2==0 else 'close-exit'
        directory=root/str(index)
        env=dict(os.environ,PATH=str(bindir),TERM='xterm-256color',
                 LC_ALL='en_US.UTF-8' if sys.platform=='darwin' else 'C.UTF-8',
                 LCD_TEST_ROOT=str(directory),LCD_TEST_PEER=scenario,LCD_SENTINEL='40')
        p=Process(exe,directory,'gui',env=env,await_boot=False)
        try:
            try:wait_for(lambda:(p.console(),p.proc.poll())[1] is not None)
            except AssertionError as exc:
                raise AssertionError((index,scenario,p.proc.poll(),p.console()[-3000:])) from exc
            assert p.proc.returncode==0 and p.checkpoint.exists(),(index,scenario,p.proc.returncode)
            assert b'+--------------------+' not in p.console(),(index,scenario,p.buffer)
        finally:p.close()
print('Forced explicit-message/child-exit close trials passed')
