# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original lossless stream observer; diagnostics are not forced through JSON."""
import hashlib
import json
import re

IDENTITY=dict(v='0.2.13',n='8f1fa12',s=2,y=0,b='s',l='3')


class Frames:
    def __init__(self):
        self.buffer=b'';self.bytes=0;self.frames=0;self.counts={};self.digest=hashlib.sha256()

    def feed(self,data):
        self.bytes+=len(data);self.digest.update(data);self.buffer+=data;rows=[]
        if len(self.buffer)>1024*1024:raise ValueError('serial frame budget exceeded')
        while b'\r\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\r\n',1)
            if len(line)<3 or line[1:2]!=b':' or b'\r' in line or b'\n' in line:
                raise ValueError('invalid serial framing')
            prefix=line[:1].decode('ascii')
            if prefix not in ['N','S','C','V','T','L','U','h','d','D']:
                raise ValueError('unexpected serial prefix')
            if prefix=='D':
                # Values can contain firmware-unescaped quotes/backslashes. Do
                # not impose strict JSON on this diagnostic wire format.
                if not re.match(rb'^D:\{"logType":"[EWI]","logID":\d+,"V":\[',line):
                    raise ValueError('invalid diagnostic header')
            elif prefix=='N' and json.loads(line[2:].decode('cp437'))!=IDENTITY:
                raise ValueError('firmware identity changed')
            elif prefix=='L':
                rows_lcd=json.loads(line[2:].decode('cp437'))
                if len(rows_lcd)!=4 or any(len(row)!=20 for row in rows_lcd) or b'\xb0' not in line:
                    raise ValueError('LCD width or raw degree byte changed')
            elif prefix!='D':json.loads(line[2:].decode('cp437'))
            self.frames+=1;self.counts[prefix]=self.counts.get(prefix,0)+1;rows.append(line)
        return rows

    def summary(self,quiescent=False):
        if quiescent and self.buffer:raise ValueError('incomplete serial frame at accepted boundary')
        return dict(bytes=self.bytes,frames=self.frames,counts=self.counts,sha256=self.digest.hexdigest(),pending_bytes=len(self.buffer))
