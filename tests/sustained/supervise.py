# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Target-side bounded supervisor; no shell session or CI job owns the soak."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


def atomic(path,value,uid):
    temporary=path.with_name(path.name+'.new');temporary.write_text(json.dumps(value,sort_keys=True)+'\n')
    os.chown(temporary,uid,-1);os.chmod(temporary,0o600);temporary.replace(path)


def check_worker_progress(progress,current,phase_age):
    if progress.get('phase') not in ['setup','normal','accelerated','latency','backpressure','cleanup','validation','complete']:raise RuntimeError('unknown worker phase')
    if progress['phase'] in ['normal','accelerated','latency','backpressure']:
        if any(type(progress.get(k)) not in [int,float] or not math.isfinite(progress[k]) for k in ['monotonic','utc']):raise RuntimeError('invalid worker heartbeat')
        if abs(current[0]-progress['monotonic'])>5 or abs(current[2]-progress['utc'])>5:raise RuntimeError('worker heartbeat lost')
    elif progress['phase'] in ['setup','validation'] and phase_age>1800:
        raise RuntimeError(progress['phase']+' did not finish')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('base');parser.add_argument('run');parser.add_argument('architecture',choices=['arm64','amd64']);parser.add_argument('--accelerated-only',action='store_true');parser.add_argument('--acceptance',action='store_true');parser.add_argument('--owner',type=int,required=True)
    args=parser.parse_args();base=Path(args.base).resolve();run=Path(args.run).resolve()
    if os.geteuid()!=0 or not run.is_dir() or not (run/'harness/run.py').is_file():raise RuntimeError('explicit private staged run required')
    for name in ['lab','evidence']:
        path=run/name;path.mkdir();os.chown(path,2001,2001);path.chmod(0o700)
    if os.uname().machine!={'arm64':'aarch64','amd64':'x86_64'}[args.architecture]:raise RuntimeError('target architecture mismatch')
    # Restrict only this owned test's processes, not any host service or radio.
    allowed=os.sched_getaffinity(0);cpu=max(allowed);os.sched_setaffinity(0,{cpu});os.nice(10)
    started=time.monotonic();started_utc=time.time();proc=None;error=None;clean=False;identity=None;held=None
    stopped=False
    def stop(signum,frame):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    atomic(run/'status.json',dict(status='starting',r3_complete=False,started_utc=started_utc,cpu=cpu),args.owner)
    try:
        log=(run/'namespace.log').open('xb')
        proc=subprocess.Popen(['unshare','--mount','--pid','--fork','--kill-child=SIGTERM','--net','--ipc','--uts','python3',str(run/'harness/namespace.py'),str(base),str(run),args.architecture,'acceptance' if args.acceptance else 'pilot','accelerated-only' if args.accelerated_only else 'full'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        previous=(time.monotonic(),time.clock_gettime(time.CLOCK_BOOTTIME),time.time())
        phase='setup';phase_started=started
        while proc.poll() is None:
            if stopped:raise RuntimeError('operator interruption')
            current=(time.monotonic(),time.clock_gettime(time.CLOCK_BOOTTIME),time.time())
            if any(not 0<=a-b<=5 for a,b in zip(current,previous)):raise RuntimeError('outer observation gap or suspension')
            previous=current
            if current[0]-started>(31*3600 if args.acceptance else 1800):raise RuntimeError('qualification supervisor deadline')
            metadata=run/'namespace.json'
            if identity is None and metadata.exists():
                identity=json.loads(metadata.read_text())['pid_namespace']
                children=Path('/proc')/str(proc.pid)/'task'/str(proc.pid)/'children'
                for child in children.read_text().split():
                    ns=Path('/proc')/child/'ns/pid'
                    if os.readlink(ns)==identity:held=os.open(ns,os.O_RDONLY);break
            heartbeat=run/'evidence/worker-heartbeat.json'
            progress=json.loads(heartbeat.read_text()) if heartbeat.exists() else dict(phase='setup')
            if progress['phase']!=phase:
                phase=progress['phase'];phase_started=current[0]
            check_worker_progress(progress,current,current[0]-phase_started)
            atomic(run/'status.json',dict(status='running',r3_complete=False,architecture=args.architecture,cpu=cpu,elapsed_wall_seconds=current[0]-started,progress=progress),args.owner)
            time.sleep(.5)
        if proc.returncode:raise RuntimeError('namespace worker failed')
        from validate import saved
        validation=saved(run,base,args.acceptance,args.architecture,'accelerated-only' if args.accelerated_only else 'full')
        atomic(run/'evidence-validation.json',validation,args.owner)
        result=json.loads((run/'evidence/result.json').read_text())
        if result.get('status')!='passed' or result.get('qualification') is not args.acceptance or result.get('r3_complete') is not (args.acceptance and not args.accelerated_only):raise RuntimeError('incomplete worker evidence')
    except BaseException as exc:error=repr(exc)
    finally:
        if proc and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
        remaining=[]
        if identity:
            for p in Path('/proc').iterdir():
                if p.name.isdigit():
                    try:
                        if os.readlink(p/'ns/pid')==identity:remaining.append(int(p.name))
                    except (OSError,FileNotFoundError):pass
        clean=bool(identity) and not remaining
        if held is not None:os.close(held)
        if not clean:error=error or 'owned namespace cleanup could not be verified'
        value=dict(status='passed' if error is None else 'failed',qualification=args.acceptance and error is None,r3_complete=args.acceptance and error is None and not args.accelerated_only,scope='accelerated-only' if args.accelerated_only else 'full',
                   architecture=args.architecture,cleanup_verified=clean,error=error,started_utc=started_utc,finished_utc=time.time(),elapsed_wall_seconds=time.monotonic()-started,cpu=cpu,remaining_owned_pids=remaining)
        atomic(run/'launcher.json',value,args.owner);atomic(run/'status.json',value,args.owner)
        os.chmod(run/'namespace.log',0o644);os.chown(run/'namespace.log',args.owner,-1)
    return 0 if error is None else 1


if __name__=='__main__':raise SystemExit(main())
