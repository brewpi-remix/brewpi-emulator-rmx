# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Real private-terminal menu blocking, logical inputs, and lifecycle checks."""
import fcntl
import json
import os
from pathlib import Path
import signal
import struct
import sys
import tempfile
import termios
import time
from lcd_tests import Process, wait_for, peer

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='rmx-controls-') as tmp:
    env = dict(os.environ, TERM='xterm-256color', LC_ALL='en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8')
    p = Process(exe, Path(tmp)/'terminal', 'terminal', env=env)
    original = None
    try:
        wait_for(lambda: b'> ' in p.console())
        active = termios.tcgetattr(p.slave)
        assert not (active[3] & (termios.ICANON | termios.ECHO))
        p.command(b'E')  # I15
        p.command(b'j{mode:b,beerSet:20.023}')  # first diagnostic, replies drained below
        def drain():
            while p.read_serial():
                p.wire = b''
        time.sleep(.1); drain()
        def command(text, response):
            start = len(p.console())
            os.write(p.master, text)
            wait_for(lambda: response in p.console()[start:])
            return p.console()[start:]
        drain(); os.write(p.serial,b's'); baseline=json.loads(p.line()[2:])
        command(b'press\r\n', b'Action accepted')
        command(b'cw\r', b'Action accepted')
        command(b'press\r', b'Edit target')
        # A query inside the menu waits; unrotated confirmation quantizes the target.
        drain(); os.write(p.serial,b's'); time.sleep(.1)
        assert not p.read_serial(), 'query dispatched inside paused menu'
        command(b'press\r', b'Target committed')
        after=p.line()
        while not after.startswith(b'S:'):after=p.line()
        after=json.loads(after[2:])
        assert baseline['beerSet']==20.02 and after['beerSet']==20, (baseline,after)
        command(b'door open\r', b'Door opened')
        command(b'door open\r', b'Door unchanged')
        command(b'door close\r', b'Door closed')
        segment = command(b'?' + b'x'*100 + b'press\r', b'Line rejected')
        assert b'Action accepted' not in segment and b'Edit target' not in segment
        command(b'help\r', b'cw ccw press door open/close')
        # Appended acknowledgments never allocate a new prompt region.
        # Repainting includes equipment/help and returns to the same command line.
        command(b'press\r', b'Action accepted')
        segment = command(b'cw\r', b'Action accepted')
        assert segment.startswith(b'\r\x1b[13A') and b'\x1b[2K' in segment
        # Terminal suspension preserves the active firmware continuation.
        os.kill(p.proc.pid,signal.SIGTSTP)
        def stopped():
            pid, status = os.waitpid(p.proc.pid,os.WNOHANG | os.WUNTRACED)
            return pid and os.WIFSTOPPED(status)
        wait_for(stopped)
        restored = termios.tcgetattr(p.slave)
        assert restored[3] & termios.ICANON and restored[3] & termios.ECHO
        os.kill(p.proc.pid,signal.SIGCONT)
        time.sleep(.2)
        wait_for(lambda: not termios.tcgetattr(p.slave)[3] & termios.ICANON)
        # Small terminal suspends input; queued commands there must not execute on resize.
        fcntl.ioctl(p.slave,termios.TIOCSWINSZ,struct.pack('HHHH',6,22,0,0))
        time.sleep(.2); os.write(p.master,b'door open\r')
        time.sleep(.1)
        start = len(p.console())
        fcntl.ioctl(p.slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
        time.sleep(.3)
        assert b'Door opened' not in p.console()[start:]
        command(b'door close\r',b'Door unchanged')
    finally:
        # Retain a dup so terminal restoration can be checked after Process closes its descriptors.
        slave = os.dup(p.slave)
        master = os.dup(p.master)
        p.close()
        try:
            flags=termios.tcgetattr(slave)[3]
            assert flags & termios.ICANON and flags & termios.ECHO
        except termios.error:
            # macOS revokes the session leader's PTY on exit. Suspension above
            # checks restoration before revocation; Linux also checks after exit.
            if sys.platform != 'darwin':
                raise
        finally:
            os.close(slave); os.close(master)
    p = Process(exe, Path(tmp)/'background', 'terminal', env=env, extra=('--speed','10'))
    try:
        wait_for(lambda: b'> ' in p.console())
        os.write(p.master,b'press\r')
        time.sleep(.5)
        # Plant time advances, but the query remains queued until the menu returns.
        os.write(p.serial,b'n');time.sleep(.1)
        assert not p.read_serial()
        assert p.line().startswith(b'N:')
    finally:
        p.close()
    checkpoint=json.loads(p.checkpoint.read_text())['engine']
    assert checkpoint['plant']['age_ms'] >= 10000, checkpoint['plant']
    # Headless operation retains ordinary orphan-group SIGTSTP behavior.
    p=Process(exe,Path(tmp)/'headless-signal','off',env=env,terminal=False)
    try:
        os.kill(p.proc.pid,signal.SIGTSTP);time.sleep(.1)
        pid,status=os.waitpid(p.proc.pid,os.WNOHANG | os.WUNTRACED)
        assert not (pid and os.WIFSTOPPED(status)), 'headless default signal behavior changed'
        assert p.command(b'n').startswith(b'N:')
    finally:
        if p.proc.poll() is None:os.kill(p.proc.pid,signal.SIGCONT)
        p.close()
    # GUI failure must not execute terminal input typed before control ownership.
    bindir=Path(tmp)/'bin';bindir.mkdir();peer(bindir)
    fallback_root=Path(tmp)/'fallback'
    chosen=dict(env,PATH=str(bindir),LCD_TEST_ROOT=str(fallback_root),LCD_TEST_PEER='hang',LCD_SENTINEL='40')
    p=Process(exe,fallback_root,'gui',env=chosen)
    try:
        time.sleep(.3);os.write(p.master,b'door open\r')
        wait_for(lambda:b'> ' in p.console(),timeout=9)
        assert b'Door opened' not in p.buffer
        start=len(p.console());os.write(p.master,b'door close\r')
        wait_for(lambda:b'Door unchanged' in p.console()[start:])
    finally:p.close()
    # A storage error during local confirmation must remain fatal, not viewer fallback.
    p=Process(exe,Path(tmp)/'storage-failure','terminal',env=env)
    try:
        wait_for(lambda:b'> ' in p.console())
        p.command(b'E'); time.sleep(.1)
        while p.read_serial():p.wire=b''
        state=p.root/'state.json'; state.unlink(); state.mkdir()
        os.write(p.master,b'press\rcw\rpress\rpress\r')
        wait_for(lambda:p.proc.poll() is not None or (p.console() and False))
        assert p.proc.returncode != 0
    finally:
        error=p.close(check=False)
    assert b'continuing headless' not in error and error,error
print('Terminal command, quantization, door, overflow, no-scroll, suspend/resize/exit restoration and background checks passed')
