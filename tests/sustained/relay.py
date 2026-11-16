# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original byte-transparent single-consumer relay for the separate real host."""
import os
from pathlib import Path
import pty
import select
import threading
import time
import tty
from measurement import Evidence
from wire import Frames


class Requests:
    def __init__(self):self.token=False;self.counts={}
    def feed(self,data):
        for byte in data:
            if self.token:
                if byte==ord('}'):self.token=False
                continue
            char=chr(byte)
            if char in 'jUhd':self.token=True
            if char in 'nslv':self.counts[char]=self.counts.get(char,0)+1
            if char=='R':raise RuntimeError('unexpected controller reset during continuous workload')


class Relay:
    def __init__(self,session,path,capture):
        if session.fd is None:raise RuntimeError('sole-client transition needs an owned descriptor')
        os.close(session.fd);session.fd=None
        self.source=os.open(session.serial,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
        self.master,self.slave=pty.openpty();tty.setraw(self.slave);os.set_blocking(self.master,False)
        self.path=Path(path);self.path.symlink_to(os.ttyname(self.slave))
        self.frames=Frames();self.requests=Requests();self.capture=Evidence(capture)
        self.stop=threading.Event();self.error=None;self.states=set()
        self.thread=threading.Thread(target=self.run);self.thread.start()

    def run(self):
        try:
            while not self.stop.is_set():
                for fd in select.select([self.source,self.master],[],[],.1)[0]:
                    data=os.read(fd,65536)
                    if not data:continue
                    if fd==self.source:
                        pending=self.frames.buffer
                        try:frames=self.frames.feed(data)
                        except BaseException:
                            (self.capture.root/'invalid-wire.bin').write_bytes(pending+data);raise
                        for row in frames:
                            if row.startswith(b'T:'):
                                import re
                                match=re.search(rb'"State":(\d+)',row)
                                if match:self.states.add(int(match.group(1)))
                            self.capture.append(dict(direction='controller',monotonic=time.monotonic(),hex=(row+b'\r\n').hex()))
                        destination=self.master
                    else:
                        self.requests.feed(data);destination=self.source
                        self.capture.append(dict(direction='host',monotonic=time.monotonic(),hex=data.hex()))
                    view=memoryview(data);deadline=time.monotonic()+5
                    while view:
                        if time.monotonic()>deadline or self.stop.is_set():raise RuntimeError('relay write did not complete')
                        if select.select([],[destination],[],.1)[1]:
                            try:view=view[os.write(destination,view):]
                            except BlockingIOError:pass
        except BaseException as exc:self.error=repr(exc)

    def check(self):
        if self.error or not self.thread.is_alive():raise RuntimeError('relay failed: '+str(self.error))

    def close(self):
        time.sleep(.2);self.stop.set();self.thread.join(timeout=6)
        for fd in [self.source,self.master,self.slave]:os.close(fd)
        self.path.unlink();capture=self.capture.close()
        if self.thread.is_alive() or self.error:raise RuntimeError('relay cleanup failed: '+str(self.error))
        summary=self.frames.summary(True)
        for command,prefix in [('n','N'),('l','L'),('v','V')]:
            if self.requests.counts.get(command,0)!=summary['counts'].get(prefix,0):raise RuntimeError('lost/reordered required reply: '+prefix)
        return dict(stream=summary,capture=capture,requests=self.requests.counts,states=sorted(self.states))
