# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise the original Linux supervisor's actual wait4 and interruption paths."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

monitor=str(Path(sys.argv[1]).resolve())
if sys.platform!='linux' or os.geteuid()==0:raise RuntimeError('native unprivileged Linux check required')
with tempfile.TemporaryDirectory(prefix='rmx-r3-monitor-') as temporary:
    root=Path(temporary)
    for name,script,interrupt in [
        ('transient-peak','data=bytearray(24*1024*1024); data[:]=b"x"*len(data)',False),
        ('interruption','import time; time.sleep(120)',True)]:
        pid=root/(name+'.pid');result=root/(name+'.json')
        proc=subprocess.Popen([monitor,str(pid),str(result),sys.executable,'-c',script])
        deadline=time.monotonic()+5
        while (not pid.exists() or not pid.read_text().strip()) and time.monotonic()<deadline:
            if proc.poll() is not None:raise RuntimeError('supervisor exited before child readiness')
            time.sleep(.01)
        if not pid.exists() or not pid.read_text().strip():raise TimeoutError('missing child PID handshake')
        if interrupt:proc.send_signal(signal.SIGTERM)
        rc=proc.wait(timeout=10);row=json.loads(result.read_text())
        if not row['wait4_collected'] or row['emulator_pid']!=int(pid.read_text()):raise AssertionError('missing exact-child wait4 accounting')
        if interrupt:
            if rc==0 or row['interrupted']!=signal.SIGTERM:raise AssertionError('interruption was accepted')
        elif rc or row['exit_code'] or row['maxrss_kib']<24*1024:raise AssertionError('transient lifetime peak was missed')
        try:os.kill(row['emulator_pid'],0)
        except ProcessLookupError:pass
        else:raise AssertionError('owned child remains')
print(json.dumps(dict(status='passed',checks=['complete transient lifetime peak','interruption fails and child cleanup completes'])))
