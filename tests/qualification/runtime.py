# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original unprivileged Linux qualification through real PTY processes."""
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from transport import Session, EXE

ROOT=Path('/qualification/runtime')
OUT=Path('/qualification/results')
READY='/opt/brewpi-emulator-rmx/libexec/brewpi-emulator-rmx/wait-ready.py'
DEFAULTS=json.loads(Path('/work/engineering/protocol/test-vectors/defaults-v1.json').read_text())
IDENTITY=DEFAULTS['identity']


def receive(session,prefix,timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        line=session.line(max(.01,deadline-time.monotonic()))
        assert line[1:2]==b':',line
        value=json.loads(line[2:].decode('cp437'))
        if line[:1]==prefix.encode():
            return value
        assert line[:1] in [b'T',b'D'],line
    raise AssertionError('missing response '+prefix)


def feed(session,bytes_,prefix=None):
    session.write(bytes_)
    return receive(session,prefix) if prefix else None


def initialize(session,mode='b'):
    feed(session,b'E','D')
    for expected in DEFAULTS['all_assigned_slots']:
        fields={key:value for key,value in expected.items() if key!='t'}
        assert feed(session,b'U'+json.dumps(fields).encode(),'U')['f']==expected['f']
    command=dict(mode=mode)
    if mode=='b':command['beerSet']=22
    feed(session,b'j'+json.dumps(command).encode(),'S')
    receive(session,'C')


def quantiles(samples):
    ordered=sorted(samples)
    return dict(samples=len(samples),median_ms=statistics.median(samples)*1000,
                p95_ms=ordered[min(len(ordered)-1,int(.95*len(ordered)))]*1000,
                max_ms=max(samples)*1000)


def run():
    assert os.geteuid()!=0
    os.umask(0o077)
    ROOT.mkdir();OUT.mkdir(exist_ok=True)
    results=[]
    def record(name,details):
        results.append(dict(name=name,status='passed',details=details))
        print(json.dumps(results[-1]),flush=True)
    active=[]
    try:
        # Readiness opens/inspects the endpoint without consuming even W3.
        directory=ROOT/'ownership';directory.mkdir(mode=0o700)
        s=Session(directory,fresh=False,options=['--speed','0']);active.append(s)
        probe=subprocess.run([READY,'--serial',str(s.path),'--pid',str(s.p.pid),'--timeout','2'],capture_output=True,timeout=4)
        assert probe.returncode==0,probe.stderr
        s.expect('D',dict(logType='W',logID=3,V=[]))
        assert feed(s,b'n','N')==IDENTITY
        pty=s.path.stat()
        assert pty.st_uid==os.geteuid()
        for path in [s.store.with_name(s.store.name+'.lock'),s.path.with_name(s.path.name+'.lock')]:
            assert path.stat().st_uid==os.geteuid() and path.stat().st_mode&0o777==0o600
        record('unprivileged ownership and nonconsuming readiness',dict(uid=os.geteuid(),gid=os.getegid(),pty_uid=pty.st_uid,pty_mode=oct(pty.st_mode&0o777),ready_stdout=probe.stdout.decode().strip()))
        # Negative readiness does not rewrite a foreign file or consume bytes.
        regular=directory/'regular';regular.write_text('untouched')
        rejected=subprocess.run([READY,'--serial',str(regular),'--pid',str(s.p.pid),'--timeout','.1'],capture_output=True,timeout=2)
        assert rejected.returncode!=0 and regular.read_text()=='untouched'
        duplicate=subprocess.run([EXE,'--serial',str(directory/'other'),'--state',str(s.store)],capture_output=True,timeout=3)
        assert duplicate.returncode!=0 and b'store' in duplicate.stderr
        s.close();active.remove(s)
        record('readiness rejection and exclusive ownership',dict(regular_file_preserved=True,duplicate_store_rejected=True))

        # Measure a configured controller workload without changing firmware thresholds.
        for speed in [1,10,60]:
            directory=ROOT/('speed-'+str(speed));directory.mkdir()
            checkpoint=directory/'checkpoint.json'
            before_spawn=time.monotonic()
            s=Session(directory,options=['--speed',str(speed),'--checkpoint',str(checkpoint)]);active.append(s)
            initialize(s)
            latencies=[]
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                before=time.monotonic();assert feed(s,b'n','N')==IDENTITY
                latencies.append(time.monotonic()-before)
                time.sleep(.1)
            # Partial scalar deadline is wall time at every rate.
            start=time.monotonic();s.write(b'j{Kp:7')
            value=receive(s,'D',3)
            while value['logID']!=12:
                value=receive(s,'D',3)
            blocked=time.monotonic()-start
            assert .6<blocked<2.5,blocked
            receive(s,'S');assert receive(s,'C')['Kp']==7
            time.sleep(.1)
            stop_requested=time.monotonic();s.close();active.remove(s)
            snapshot=json.loads(checkpoint.read_text())
            simulated=(snapshot['engine']['plant']['age_ms']+snapshot['engine']['pending_ms'])/1000
            wall=stop_requested-before_spawn
            achieved=simulated/wall
            assert .85*speed<achieved<1.15*speed,(speed,achieved,wall)
            assert max(latencies)<1,latencies
            record('pacing and response '+str(speed),dict(requested_factor=speed,achieved_factor=achieved,
                simulated_seconds=simulated,measured_wall_seconds=wall,partial_token_wait_seconds=blocked,
                ordinary_n=quantiles(latencies),workload='seven assigned devices, beer target 22 C, native filters/PID/model'))

        # Backpressure must defer the final mutation and preserve every ordered reply.
        directory=ROOT/'backpressure';directory.mkdir()
        s=Session(directory,options=['--speed','10']);active.append(s)
        initialize(s,'t')
        count=12000
        errors=[]
        def produce():
            try:s.write(b'ns'*(count//2)+b'j{Kp:9}')
            except BaseException as exc:errors.append(repr(exc))
        writer=threading.Thread(target=produce);writer.start()
        time.sleep(.5)
        assert json.loads(s.store.read_text())['constants_raw']['Kp']==2560
        started=time.monotonic()
        for _ in range(count//2):
            assert receive(s,'N')==IDENTITY
            assert receive(s,'S')['mode']=='t'
        receive(s,'D');receive(s,'S');assert receive(s,'C')['Kp']==9
        writer.join(timeout=5);assert not writer.is_alive() and not errors,errors
        elapsed=time.monotonic()-started
        s.close();active.remove(s)
        record('slow-reader backpressure',dict(ordered_replies=count,reader_pause_seconds=.5,
            drain_seconds=elapsed,reply_pattern='N,S repeated',final_mutation_deferred=True,writer_errors=errors))

        # Nontrivial running histories survive a real process checkpoint/resume.
        directory=ROOT/'continuation';directory.mkdir()
        checkpoint=directory/'checkpoint.json'
        scenario=directory/'scenario.json';scenario.write_text(json.dumps(dict(noise_amplitude_c=.15,probe_lag_seconds=5,random_seed=91)))
        s=Session(directory,options=['--speed','60','--scenario',str(scenario),'--checkpoint',str(checkpoint)]);active.append(s)
        initialize(s)
        time.sleep(18)
        assert feed(s,b'n','N')==IDENTITY
        time.sleep(.1);s.close();active.remove(s)
        original=json.loads(checkpoint.read_text())
        assert original['engine']['plant']['age_ms']>1000000
        resumed=directory/'resumed.json'
        s=Session(directory,fresh=False,options=['--speed','0','--resume',str(checkpoint),'--checkpoint',str(resumed)]);active.append(s)
        assert feed(s,b'n','N')==IDENTITY
        time.sleep(.1);s.close();active.remove(s)
        assert json.loads(resumed.read_text())['engine']==original['engine']
        record('coherent checkpoint continuation',dict(age_ms=original['engine']['plant']['age_ms'],
            full_engine_snapshot_equal=True,noise_and_lag=True,stopped_time_added=False))
        # An incomplete command cannot replace the prior checkpoint.
        previous=checkpoint.read_bytes()
        s=Session(directory,fresh=False,options=['--speed','0','--resume',str(checkpoint),'--checkpoint',str(checkpoint)]);active.append(s)
        s.write(b'j{Kp:')
        time.sleep(.1)
        os.close(s.fd);s.fd=None
        s.p.terminate();stdout,stderr=s.p.communicate(timeout=5);active.remove(s)
        assert s.p.returncode!=0 and b'quiescent' in stderr
        assert checkpoint.read_bytes()==previous
        record('failed checkpoint preservation',dict(incomplete_command_rejected=True,previous_bytes_preserved=True))

        # SIGKILL releases locks but leaves the owned link; recovery is deliberate.
        directory=ROOT/'killed';directory.mkdir()
        s=Session(directory);active.append(s)
        feed(s,b'E','D');feed(s,b'j{Kp:7}','S');receive(s,'C')
        saved=s.store.read_bytes();old_target=os.readlink(s.path)
        os.close(s.fd);s.fd=None;s.p.kill();s.p.communicate(timeout=5);active.remove(s)
        assert s.path.is_symlink() and os.readlink(s.path)==old_target
        restart=subprocess.run([EXE,'--serial',str(s.path),'--state',str(s.store)],capture_output=True,timeout=3)
        assert restart.returncode!=0 and s.store.read_bytes()==saved
        # Only this controlled test's private link is removed; never touch the PTY target.
        s.path.unlink()
        s=Session(directory,fresh=False);active.append(s)
        assert feed(s,b'c','C')['Kp']==7
        s.close();active.remove(s)
        record('forced-stop recovery and saved state',dict(stale_link_preserved=True,implicit_replacement_rejected=True,saved_gain=7))
        (OUT/'runtime-results.json').write_text(json.dumps(dict(status='passed',checks=results),indent=2)+'\n')
    except BaseException:
        (OUT/'runtime-results.json').write_text(json.dumps(dict(status='failed',checks=results),indent=2)+'\n')
        raise
    finally:
        for session in active:
            if session.fd is not None:os.close(session.fd)
            if session.p.poll() is None:
                session.p.terminate()
                try:session.p.communicate(timeout=5)
                except subprocess.TimeoutExpired:session.p.kill();session.p.communicate(timeout=3)


if __name__=='__main__':
    run()
