# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original sole-client PTY session backed by an exact-child resource supervisor."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import termios
import time
from measurement import Evidence,canonical
from wire import Frames,IDENTITY


class Session:
    def __init__(self,root,binary,monitor,speed=0,fresh=True,resume=None,scenario=None,environment=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.serial=self.root/'serial';self.store=self.root/'controller.json';self.checkpoint=self.root/'checkpoint.json'
        self.ordinal=len(list(self.root.glob('lifetime-*.json')))
        self.pidfile=self.root/('pid-%04d'%self.ordinal);self.lifetime=self.root/('lifetime-%04d.json'%self.ordinal)
        self.fd=None;self.buffer=b'';self.frames=Frames();self.capture=Evidence(self.root/('wire-%04d'%self.ordinal));self.sampler=None
        self.log=(self.root/('process-%04d.log'%self.ordinal)).open('xb')
        args=[str(monitor),str(self.pidfile),str(self.lifetime),str(binary),'--serial',str(self.serial),'--state',str(self.store),
              '--checkpoint',str(self.checkpoint),'--speed',str(speed)]
        if resume:args+=['--resume',str(resume)]
        if scenario:args+=['--scenario',str(scenario)]
        self.p=subprocess.Popen(args,stdout=self.log,stderr=self.log,env=environment,start_new_session=True)
        try:
            deadline=time.monotonic()+10
            while not self.serial.is_symlink() or not self.pidfile.exists() or not self.pidfile.read_text().strip():
                if self.p.poll() is not None:raise RuntimeError('emulator startup failed: '+(self.root/('process-%04d.log'%self.ordinal)).read_text())
                if time.monotonic()>deadline:raise TimeoutError('emulator readiness timeout')
                time.sleep(.01)
            self.pid=int(self.pidfile.read_text());self.connect()
            if fresh:self.expect('D',dict(logType='W',logID=3,V=[]))
        except BaseException:
            self.abort();raise

    def connect(self):
        if self.fd is not None:raise RuntimeError('second PTY consumer refused')
        self.fd=os.open(self.serial,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
        attrs=termios.tcgetattr(self.fd)
        if attrs[3]&(termios.ICANON|termios.ECHO) or attrs[1]&termios.OPOST:raise RuntimeError('PTY not raw')

    def write(self,data):
        view=memoryview(data);deadline=time.monotonic()+5
        self.capture.append(dict(direction='client',monotonic=time.monotonic(),hex=bytes(view).hex()))
        while view:
            if time.monotonic()>deadline:raise TimeoutError('PTY write timeout')
            if select.select([],[self.fd],[],.1)[1]:
                try:view=view[os.write(self.fd,view):]
                except BlockingIOError:pass

    def line(self,timeout=5):
        deadline=time.monotonic()+timeout
        while b'\r\n' not in self.buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('PTY read timeout')
            if self.p.poll() is not None:raise RuntimeError('emulator exited unexpectedly')
            if select.select([self.fd],[],[],min(.5,remaining))[0]:
                data=os.read(self.fd,65536)
                if not data:raise RuntimeError('PTY closed')
                pending=self.frames.buffer
                try:frames=self.frames.feed(data)
                except BaseException:
                    (self.root/('invalid-wire-%04d.bin'%self.ordinal)).write_bytes(pending+data);raise
                for frame in frames:self.capture.append(dict(direction='controller',monotonic=time.monotonic(),hex=(frame+b'\r\n').hex()))
                self.buffer+=data
        row,self.buffer=self.buffer.split(b'\r\n',1)
        return row

    def expect(self,prefix,value=None,timeout=5):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            line=self.line(max(.01,deadline-time.monotonic()))
            if line[:1]==prefix.encode():
                actual=json.loads(line[2:].decode('cp437'))
                if value is not None and actual!=value:raise AssertionError((prefix,actual,value))
                return actual
            if line[:1] not in [b'D',b'T']:raise AssertionError(('reply order',line,prefix))
        raise TimeoutError(prefix)

    def query(self,data,prefix,value=None):
        self.write(data);return self.expect(prefix,value)

    def initialize(self,defaults,mode='b',target=22):
        self.query(b'E','D',dict(logType='I',logID=15,V=[]))
        for expected in defaults['all_assigned_slots']:
            fields={key:value for key,value in expected.items() if key!='t'}
            row=self.query(b'U'+json.dumps(fields).encode(),'U')
            if row['i']!=expected['i'] or row['f']!=expected['f']:raise AssertionError('assignment mismatch')
        self.query(b'j'+json.dumps(dict(mode=mode,beerSet=target)).encode(),'S');self.expect('C')
        self.query(b'n','N',IDENTITY)

    def start_sampler(self):
        self.sample_root=self.root/('resources-%04d'%self.ordinal)
        self.sampler=subprocess.Popen(['python3',str(Path(__file__).with_name('sample.py')),str(self.pid),str(self.sample_root)])
        deadline=time.monotonic()+5
        while not (self.sample_root/'heartbeat.json').exists():
            if self.sampler.poll() is not None or time.monotonic()>deadline:raise RuntimeError('sampler did not start')
            time.sleep(.02)

    def check(self):
        if self.p.poll() is not None:raise RuntimeError('continuous emulator process exited')
        if self.sampler:
            if self.sampler.poll() is not None:raise RuntimeError('independent resource observer exited')
            heartbeat=json.loads((self.sample_root/'heartbeat.json').read_text())
            if time.monotonic()-heartbeat['monotonic']>5 or abs(time.time()-heartbeat['utc'])>5:raise RuntimeError('resource observer heartbeat lost')

    def stop_sampler(self):
        if self.sampler:
            if self.sampler.poll() is None:self.sampler.terminate()
            self.sampler.wait(timeout=5)
            summary=json.loads((self.sample_root/'summary.json').read_text())
            if self.sampler.returncode or summary['status']!='passed':raise RuntimeError('resource observer failed: '+str(summary))

    def close(self,killed=False):
        if self.fd is not None:os.close(self.fd);self.fd=None
        if self.p.poll() is None:os.kill(self.pid,signal.SIGKILL if killed else signal.SIGTERM)
        self.p.wait(timeout=10);self.stop_sampler();self.log.close();self.capture_summary=self.capture.close()
        record=json.loads(self.lifetime.read_text())
        if killed:
            if record['exit_code']!=137 or not self.serial.is_symlink():raise AssertionError('SIGKILL/stale-link behavior changed')
        elif self.p.returncode or record['exit_code'] or record['interrupted'] or self.serial.is_symlink():
            raise RuntimeError('emulator did not cleanly stop: '+str(record))
        return record

    def abort(self):
        if self.fd is not None:os.close(self.fd);self.fd=None
        if getattr(self,'p',None) and self.p.poll() is None:
            self.p.terminate()
            try:self.p.wait(timeout=8)
            except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=3)
        if self.sampler:
            self.sampler.terminate()
            try:self.sampler.wait(timeout=5)
            except subprocess.TimeoutExpired:self.sampler.kill();self.sampler.wait(timeout=2)
        self.log.close();self.capture.close()
