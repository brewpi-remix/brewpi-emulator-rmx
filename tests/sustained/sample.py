# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Independent Linux process observer; never opens the emulator PTY."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
from measurement import canonical,compare_clocks


def clocks():
    return dict(monotonic=time.monotonic(),boottime=time.clock_gettime(time.CLOCK_BOOTTIME),utc=time.time())


def process(pid):
    root=Path('/proc')/str(pid)
    stat=(root/'stat').read_text().rpartition(') ')[2].split()
    if stat[0]=='Z':raise ProcessLookupError(pid)
    values={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (root/'status').read_text().splitlines() if ':' in line}
    if 'VmRSS' not in values:
        if (root/'stat').read_text().rpartition(') ')[2].split()[0]=='Z':raise ProcessLookupError(pid)
        raise RuntimeError('live process lost RSS accounting')
    mappings={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (root/'smaps_rollup').read_text().splitlines() if ':' in line}
    if 'Rss' not in mappings:
        if (root/'stat').read_text().rpartition(') ')[2].split()[0]=='Z':raise ProcessLookupError(pid)
        raise RuntimeError('live process lost mapping accounting')
    return dict(pid=pid,start_ticks=int(stat[19]),rss_kib=int(mappings['Rss'].split()[0]),status_rss_kib=int(values['VmRSS'].split()[0]),
                fds=len(list((root/'fd').iterdir())),threads=len(list((root/'task').iterdir())),
                cpu_ticks=int(stat[11])+int(stat[12]))


def atomic(path,value):
    temporary=path.with_name(path.name+'.new')
    with temporary.open('w') as stream:stream.write(canonical(value).decode())
    temporary.replace(path)


def run(pid,output):
    output=Path(output);output.mkdir()
    stopped=False
    def stop(signum,frame):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    first=clocks();previous=None;identity=None;count=0;status='passed';error=None
    try:
        with (output/'samples.jsonl').open('xb') as stream:
            while not stopped:
                current=clocks()
                if previous:
                    delta=compare_clocks(previous,current)
                    if delta['monotonic']>1:raise RuntimeError('independent sampler gap exceeds one second')
                try:row=process(pid)
                except (FileNotFoundError,ProcessLookupError):break
                if identity is None:identity=row['start_ticks']
                if row['start_ticks']!=identity:raise RuntimeError('observed PID was reused')
                row.update(current,elapsed=current['monotonic']-first['monotonic'])
                data=canonical(row)
                if stream.tell()+len(data)>128*1024*1024:raise RuntimeError('resource evidence budget exhausted')
                stream.write(data);stream.flush();count+=1
                atomic(output/'heartbeat.json',dict(status='running',pid=pid,samples=count,**current))
                previous=current
                time.sleep(max(0,.5-(time.monotonic()-current['monotonic'])))
    except BaseException as exc:
        status='failed';error=repr(exc)
    atomic(output/'summary.json',dict(status=status,pid=pid,start_ticks=identity,samples=count,error=error,started=first,finished=clocks()))
    return 0 if status=='passed' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('pid',type=int);parser.add_argument('output')
    args=parser.parse_args();raise SystemExit(run(args.pid,args.output))
