# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Opt-in candidate-byte qualification; pilots never satisfy sustained gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import statistics
import subprocess
import sys
import threading
import time
from measurement import canonical,DURATIONS,validate_resources
from session import Session
from host import Host
from relay import Relay
from exercise import lifecycle,clocks,faults

SOURCE=Path('/source');OUT=Path('/evidence');LAB=Path('/lab')
sys.path.insert(0,str(SOURCE/'tests/ci'))
from payload import Payload,sha


def save(name,data):
    path=OUT/name;temp=path.with_name(path.name+'.new');temp.write_bytes(canonical(data));temp.replace(path)


def heartbeat(phase,**values):save('worker-heartbeat.json',dict(phase=phase,monotonic=time.monotonic(),utc=time.time(),**values))


def read_samples(session):
    return [json.loads(line) for line in (session.sample_root/'samples.jsonl').read_text().splitlines()]


def latency(session):
    samples=[]
    for _ in range(30):
        started=time.monotonic();session.query(b'n','N');samples.append(time.monotonic()-started)
        if samples[-1]>=1:raise AssertionError('ordinary n query exceeded one second')
        heartbeat('latency',pid=session.pid);time.sleep(.05)
    start=time.monotonic();session.write(b'j{Kp:7')
    while True:
        row=session.line()
        if row==b'D:{"logType":"I","logID":12,"V":["Kp","7"]}':break
        if row[:1] not in [b'D',b'T']:raise AssertionError('partial command diagnostic order')
    waited=time.monotonic()-start
    if not .6<waited<2.5:raise AssertionError('wall token timeout changed')
    session.expect('S');assert session.expect('C')['Kp']==7
    return dict(samples=len(samples),seconds=samples,max_seconds=max(samples),median_seconds=statistics.median(samples),partial_token_seconds=waited)


def pressure(session,pairs=1000):
    error=[]
    def send():
        try:session.write(b'ns'*pairs)
        except BaseException as exc:error.append(repr(exc))
    producer=threading.Thread(target=send);producer.start();time.sleep(.5)
    for index in range(pairs):
        session.expect('N');session.expect('S')
        if index%50==0:heartbeat('backpressure',pid=session.pid,replies=2*index)
    producer.join(timeout=5)
    if producer.is_alive() or error:raise RuntimeError('backpressure transport failure: '+str(error))
    return dict(ordered_replies=2*pairs,pause_seconds=.5,status='passed')


def soak(kind,duration,acceptance,binary,monitor,defaults,manifest):
    speed=1 if kind=='normal' else 60
    directory=LAB/kind;scenario=LAB/(kind+'-scenario.json')
    scenario.write_text(json.dumps(manifest['scenario']))
    s=Session(directory,binary,monitor,speed=speed,scenario=scenario);host=None;relay=None;started=time.monotonic()
    context_start=dict(loadavg=os.getloadavg(),disk_free_bytes=shutil.disk_usage(LAB).free)
    try:
        s.start_sampler();s.initialize(defaults);heartbeat('setup',pid=s.pid)
        profile_start=None;seen=set();states=set();pressures=[]
        if kind=='normal':
            host=Host(LAB/'client','/refs/script','/refs/panel')
            relay=Relay(s,LAB/'host-serial',directory/'host-wire')
            host.start(LAB/'host-serial')
            points=manifest['normal']['profile_points_seconds'] if acceptance else manifest['pilot_normal_profile_points_seconds']
            profile_start=host.profile(points)
        else:pressures.append(pressure(s))
        began=time.monotonic();deadline=began+duration;next_read=0;next_target=1800;next_pressure=3600;target=22
        while time.monotonic()<deadline:
            s.check();elapsed=time.monotonic()-began
            if host:
                relay.check()
                if host.proc.poll() is not None:raise RuntimeError('host exited during continuous workload')
                if elapsed>=next_read:
                    settings=host.get('getControlSettings');assert settings['mode']=='p'
                    seen.add('disabled' if settings['beerSet'] is None else 'active')
                    if elapsed>30 and json.loads(s.store.read_text())['settings_raw']['mode']!=ord('p'):raise AssertionError('optimistic host mode differs from persisted controller mode')
                    # Plateau readbacks have independent scheduled expectations;
                    # interpolation/transition grace is excluded from exact checks.
                    relative=time.time()-profile_start
                    for left,right in zip(points,points[1:]):
                        if left[0]+30<relative<right[0]-30 and left[1]==right[1]:
                            if left[1] is None:assert settings['beerSet'] is None
                            else:assert abs(settings['beerSet']-left[1])<.02
                    next_read=elapsed+1 if not acceptance else elapsed+10
                if (host.root/'host.log').stat().st_size>64*1024*1024:raise RuntimeError('host log capture budget exhausted')
            else:
                s.query(b'n','N');s.query(b's','S');s.query(b'l','L');variables=s.query(b't','T');states.add(variables['State'])
                if elapsed>=next_target:
                    target=18 if target==22 else 22;s.query(b'j'+json.dumps(dict(beerSet=target)).encode(),'S');s.expect('C');next_target+=1800
                if elapsed>=next_pressure:pressures.append(pressure(s));next_pressure+=3600
            heartbeat(kind,pid=s.pid,elapsed_wall_seconds=elapsed,required_wall_seconds=duration)
            time.sleep(min(.5,max(0,deadline-time.monotonic())))
        observed=time.monotonic()-began
        heartbeat('cleanup',pid=s.pid)
        client_audit=None;relay_audit=None
        if host:
            client_audit=host.close();host=None;relay_audit=relay.close();relay=None
            states=set(relay_audit['states']);s.connect()
            if seen!={'active','disabled'}:raise AssertionError('profile disabled/resumed segments were not observed')
        if acceptance and not (states&{3,9} and states&{4,8}):raise AssertionError('heating/cooling demands were not both exercised')
        timings=latency(s);lifetime=s.close();snapshot=json.loads(s.checkpoint.read_text())['engine']
        heartbeat('validation',pid=s.pid)
        simulated=(snapshot['plant']['age_ms']+snapshot['pending_ms'])/1000
        process_wall=time.monotonic()-started;achieved=simulated/process_wall
        if not .85*speed<achieved<1.15*speed:raise AssertionError(('pacing',speed,achieved))
        rows=read_samples(s);resource=validate_resources(rows,lifetime,kind,rows[-1]['elapsed'],acceptance)
        if acceptance and observed<DURATIONS[kind]:raise AssertionError('short wall observation')
        wraps=int(snapshot['controller_ms']//1000//65536)
        if kind=='accelerated' and acceptance and wraps<16:raise AssertionError('missing repeated 16-bit-second wraps')
        return dict(status='passed',qualification=acceptance,workload=kind,required_wall_seconds=DURATIONS[kind],observed_wall_seconds=observed,
            pid=s.pid,resource=resource,lifetime=lifetime,requested_speed=speed,achieved_speed=achieved,simulated_seconds=simulated,
            states=sorted(states),profile_observations=sorted(seen),host=client_audit,relay=relay_audit,solo_stream=s.frames.summary(True),
            capture=s.capture_summary,latency=timings,backpressure=pressures,controller_second_wraps=wraps,
            resource_context=dict(start=context_start,end=dict(loadavg=os.getloadavg(),disk_free_bytes=shutil.disk_usage(LAB).free),
                retained_workload_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
                cpu_seconds=lifetime['user_seconds']+lifetime['system_seconds']))
    except BaseException:
        if host:
            try:host.close()
            except BaseException:pass
        if relay:
            try:relay.close()
            except BaseException:pass
        s.abort();raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--accelerated-only',action='store_true');parser.add_argument('--acceptance',action='store_true');parser.add_argument('--architecture',required=True,choices=['arm64','amd64'])
    parser.add_argument('--pilot-normal',type=int,default=45);parser.add_argument('--pilot-accelerated',type=int,default=15)
    args=parser.parse_args()
    if not __debug__ or os.geteuid()==0:raise RuntimeError('assertions and unprivileged execution required')
    if platform.machine()!={'arm64':'aarch64','amd64':'x86_64'}[args.architecture]:raise RuntimeError('guest architecture mismatch')
    os.umask(0o077);LAB.mkdir(exist_ok=True);(LAB/'home').mkdir(exist_ok=True)
    def interrupt(signum,frame):raise KeyboardInterrupt('qualification interrupted')
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    manifest=json.loads(Path('/harness/workloads.json').read_text());defaults=json.loads((SOURCE/'engineering/protocol/test-vectors/defaults-v1.json').read_text())
    if sha('/candidate.json')!=manifest['payload_manifest_sha256_by_architecture'][args.architecture]:raise RuntimeError('candidate manifest differs from reviewed saved package')
    payload=Payload('/usr/local','/candidate.json',args.architecture);binary=payload.binary;results=[]
    harness=json.loads(Path('/harness/INPUTS.json').read_text())
    for name,value in harness['files'].items():
        if sha(Path('/harness')/name)!=value:raise RuntimeError('harness input mismatch')
    save('harness-inputs.json',harness)
    save('environment.json',dict(machine=platform.machine(),kernel=platform.release(),os_release=Path('/etc/os-release').read_text(),uid=os.geteuid(),affinity=sorted(os.sched_getaffinity(0)),python=sys.version))
    if 'VERSION_ID="12"' not in Path('/etc/os-release').read_text():raise RuntimeError('Debian 12 runtime required')
    save('result.json',dict(status='running',qualification=False,r3_complete=False))
    try:
        heartbeat('setup');payload.verify('before-r3',OUT/'payload-execution.jsonl')
        for command,log in [(['c++','-std=c++17','-Wall','-Wextra','-Werror','-O2','/harness/monitor.cpp','-o','/lab/monitor'],'monitor-build.log'),
                            (['c++','-std=c++17','-Wall','-Wextra','-Werror','-shared','-fPIC','/harness/faultio.cpp','-ldl','-o','/lab/faultio.so'],'fault-build.log')]:
            with (OUT/log).open('w') as stream:subprocess.run(command,check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
        (LAB/'tools').mkdir();(LAB/'faultio.so').rename(LAB/'tools/faultio.so')
        with (OUT/'helper-checks.log').open('w') as stream:
            subprocess.run(['python3','/harness/checks.py'],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=60)
            subprocess.run(['python3','/harness/native_checks.py','/lab/monitor'],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=60)
        with (OUT/'driver-build.log').open('w') as stream:
            subprocess.run(['cmake','-S','/source','-B','/lab/driver-build','-DCMAKE_BUILD_TYPE=Release'],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
            subprocess.run(['cmake','--build','/lab/driver-build','--target','rmx-fixture-driver','-j1'],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
        runtime_files={str(p):sha(p) for p in sorted(Path('/opt/rmx-r3-inputs').iterdir()) if p.is_file()}
        tools=[LAB/'monitor',LAB/'tools/faultio.so',LAB/'driver-build/rmx-fixture-driver']
        save('runtime-inputs.json',dict(external_package_records=runtime_files,test_tools={str(p):sha(p) for p in tools},
             compiler=subprocess.check_output(['c++','--version'],text=True),
             linked_libraries=subprocess.check_output(['ldd',str(binary)],text=True),
             cpuinfo=Path('/proc/cpuinfo').read_text(),meminfo=Path('/proc/meminfo').read_text()))
        results.append(dict(kind='clock',result=clocks(LAB/'driver-build/rmx-fixture-driver',SOURCE)));save('clock.json',results[-1])
        results.append(dict(kind='faults',result=faults(LAB/'faults',binary,LAB/'monitor',defaults)));save('faults.json',results[-1])
        results.append(dict(kind='lifecycle',result=lifecycle(LAB/'cycles',binary,LAB/'monitor',defaults,100 if args.acceptance else 3)));save('lifecycle.json',results[-1])
        for kind,pilot in ([('accelerated',args.pilot_accelerated)] if args.accelerated_only else [('normal',args.pilot_normal),('accelerated',args.pilot_accelerated)]):
            duration=DURATIONS[kind] if args.acceptance else pilot
            result=soak(kind,duration,args.acceptance,binary,LAB/'monitor',defaults,manifest);results.append(dict(kind=kind,result=result));save(kind+'.json',result)
        for name,value in harness['files'].items():
            if sha(Path('/harness')/name)!=value:raise RuntimeError('harness changed during qualification')
        payload.verify('after-r3',OUT/'payload-execution.jsonl')
        save('result.json',dict(status='passed',qualification=args.acceptance,r3_complete=args.acceptance and not args.accelerated_only,scope='accelerated-only' if args.accelerated_only else 'full',architecture=args.architecture,
             candidate=payload.verify('summary'),workloads=results,unresolved_arduino_cases=9))
        heartbeat('complete')
    except BaseException as exc:
        save('result.json',dict(status='failed',qualification=False,r3_complete=False,architecture=args.architecture,error=repr(exc),workloads=results))
        raise


if __name__=='__main__':main()
