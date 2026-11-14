#!/usr/bin/env python3
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Check a live process and owned raw PTY without consuming serial bytes."""
import argparse
import os
from pathlib import Path
import stat
import sys
import termios
import time


def wait_ready(serial, pid, timeout):
    if pid<=0 or not 0<timeout<=300:
        raise ValueError('positive PID and timeout in (0,300] required')
    deadline=time.monotonic()+timeout
    last='endpoint not published'
    while time.monotonic()<deadline:
        os.kill(pid,0)
        try:
            link=Path(serial)
            if not link.is_symlink():
                raise OSError('serial endpoint is not a symlink')
            target=link.stat()
            if not stat.S_ISCHR(target.st_mode) or target.st_uid!=os.geteuid():
                raise OSError('serial endpoint must be an owned character device')
            fd=os.open(link,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
            try:
                opened=os.fstat(fd)
                if (opened.st_dev,opened.st_ino)!=(target.st_dev,target.st_ino) or opened.st_uid!=os.geteuid():
                    raise OSError('serial endpoint changed while opening')
                attrs=termios.tcgetattr(fd)
                input_flags=(termios.IGNBRK|termios.BRKINT|termios.PARMRK|termios.ISTRIP|
                             termios.INLCR|termios.IGNCR|termios.ICRNL|termios.IXON)
                local_flags=termios.ECHO|termios.ECHONL|termios.ICANON|termios.ISIG|termios.IEXTEN
                if (attrs[0]&input_flags or attrs[1]&termios.OPOST or attrs[3]&local_flags or
                    attrs[2]&termios.CSIZE!=termios.CS8 or attrs[2]&termios.PARENB):
                    raise OSError('serial endpoint is not raw/no-echo')
            finally:
                os.close(fd)
            os.kill(pid,0)
            return
        except OSError as exc:
            last=str(exc)
        time.sleep(.02)
    raise TimeoutError('serial readiness timed out: '+last)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--timeout',type=float,default=10)
    args=parser.parse_args()
    try:
        wait_ready(args.serial,args.pid,args.timeout)
    except (OSError,ValueError,TimeoutError) as exc:
        print('brewpi-emulator readiness: '+str(exc),file=sys.stderr)
        return 1
    print('serial endpoint ready: '+args.serial)
    return 0


if __name__=='__main__':
    sys.exit(main())
