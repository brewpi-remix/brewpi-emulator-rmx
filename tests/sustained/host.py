# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original socket/profile orchestration for an unmodified external BrewPi host."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time


class Host:
    def __init__(self,root,script_ref,panel_ref):
        self.root=Path(root);self.root.mkdir();self.script=self.root/'host';self.www=self.root/'www';self.proc=None
        for source,destination,revision in [(script_ref,self.script,'d183fb5319b928f78b4c0eb6f05fe3620610ffff'),(panel_ref,self.www,'f79631830a99575e250403f08a19be8bf944596c')]:
            source=Path(source)
            actual=subprocess.check_output(['git','-c','safe.directory='+str(source),'-C',str(source),'rev-parse','HEAD'],text=True).strip()
            if actual!=revision:raise RuntimeError('external client revision changed')
            config=self.root/(destination.name+'-gitconfig')
            for trusted in [source,source/'.git']:subprocess.run(['git','config','--file',str(config),'--add','safe.directory',str(trusted)],check=True)
            subprocess.run(['git','clone','--quiet','--no-hardlinks',str(source),str(destination)],check=True,env=dict(os.environ,GIT_CONFIG_GLOBAL=str(config)))
            subprocess.run(['git','-C',str(destination),'checkout','--quiet','-B','main','HEAD'],check=True)
        self.code={}
        for tree in [self.script,self.www]:
            names=subprocess.check_output(['git','-C',str(tree),'ls-files','-z']).decode().split('\0')
            for name in names:
                if name and not (tree==self.script and name=='settings/tempProfile.csv'):
                    path=tree/name;self.code[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root/'tools').mkdir();(self.script/'logs').mkdir(exist_ok=True)

    def start(self,serial):
        cfg=self.script/'settings/config.cfg'
        cfg.write_text('chamber = R3\nscriptPath = '+str(self.script)+'/\nwwwPath = '+str(self.www)+'/\ntoolPath = '+str(self.root/'tools')+'/\nport = '+str(serial)+'\naltport = None\nstartupDelay = 0\ninterval = 10\nbeerName = OriginalR3\ndataLogging = active\nlogJson = True\n')
        self.log=(self.root/'host.log').open('xb')
        self.proc=subprocess.Popen(['python3','-u',str(self.script/'brewpi.py'),'-c',str(cfg),'-l'],cwd=self.script,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+30
        while not (self.script/'BEERSOCKET').exists():
            if self.proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('external host startup failed')
            time.sleep(.1)
        self.until(lambda:self.get('getControlSettings').get('mode') in ['b','p'])

    def request(self,text):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(3);conn.connect(str(self.script/'BEERSOCKET'));conn.sendall(text.encode());conn.shutdown(socket.SHUT_WR)
            if text=='quit':return b''
            data=b''
            while True:
                part=conn.recv(65536)
                if not part:break
                data+=part
                if len(data)>1024*1024:raise RuntimeError('host socket reply exceeded capture budget')
                # The external host keeps its connection open after responding.
                # Complete JSON and the profile acknowledgment delimit our replies.
                if text.startswith('get'):
                    try:json.loads(data);return data
                    except (ValueError,UnicodeDecodeError):pass
                elif text.startswith('setActiveProfile=') and data.endswith(b'.'):return data
            return data

    def get(self,name):return json.loads(self.request(name))

    def until(self,condition):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:
                if condition():return
            except (OSError,ValueError,KeyError):pass
            if self.proc.poll() is not None:raise RuntimeError('external host exited')
            time.sleep(.5)
        raise RuntimeError('host cache did not converge')

    def profile(self,points):
        now=datetime.datetime.now(datetime.timezone.utc)
        folder=self.www/'data/profiles';folder.mkdir(parents=True,exist_ok=True)
        rows=['Date,Temp']+[(now+datetime.timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%S')+','+('' if value is None else str(value)) for seconds,value in points]
        (folder/'OriginalR3.csv').write_text('\n'.join(rows)+'\n')
        reply=self.request('setActiveProfile=OriginalR3')
        if b'successfully' not in reply:raise RuntimeError('profile activation failed')
        self.until(lambda:self.get('getControlSettings').get('mode')=='p')
        return now.timestamp()

    def close(self):
        if self.proc and self.proc.poll() is None:
            try:self.request('quit');self.proc.wait(timeout=10)
            except BaseException:
                os.killpg(self.proc.pid,15)
                try:self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(self.proc.pid,9);self.proc.wait(timeout=3)
        if self.proc and self.proc.returncode:raise RuntimeError('external host did not exit cleanly')
        if hasattr(self,'log'):self.log.close()
        changed=[path for path,digest in self.code.items() if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest]
        if changed:raise RuntimeError('external reference implementation changed: '+str(changed))
        return dict(status='passed',checked_reference_files=len(self.code),unchanged=True)
