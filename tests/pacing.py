# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise real-process pacing, pause, checkpoint resume, and environment errors."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from transport import Session, EXE


def setup(session):
    session.write(b'EU{i:3,f:2,h:1,p:5,x:1}j{mode:t}d{i:3,w:1}')
    session.expect('D', dict(logType='I',logID=15,V=[]))
    session.expect('U')
    session.expect('D')
    session.expect('T')
    session.expect('S')
    session.expect('C')
    session.expect('d')


def run():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='rmx-pacing-') as tmp:
        root=Path(tmp)
        for profile, shield, bus, pins in [('revc', 2, 18, [2,5,6,19]),
                                           ('i2c', 5, 14, [5,6,2,10])]:
            expected_identity=dict(v='0.2.13',n='da7e14a9',
                                   s=shield,y=0,b='s',l='3')
            directory=root/profile;directory.mkdir()
            checkpoint=directory/'checkpoint.json'
            options=['--profile',profile,'--speed','0','--checkpoint',str(checkpoint)]
            s=Session(directory,options=options)
            try:
                s.write(b'Enh{}')
                s.expect('D',dict(logType='I',logID=15,V=[]))
                assert s.expect('N')==expected_identity
                inventory=s.expect('h')
                assert [d['p'] for d in inventory]==[bus]*3+pins
                s.write(('U{i:0,f:9,h:2,p:%d,a:28A10100000001E6}'%bus).encode())
                assert s.expect('U')['p']==bus
            finally:s.close()
            image=json.loads((directory/'controller.json').read_text())
            assert image['profile']==profile
            snapshot=json.loads(checkpoint.read_text())
            resumed=directory/'resumed.json'
            s=Session(directory,fresh=False,options=['--profile',profile,'--speed','0',
                      '--resume',str(checkpoint),'--checkpoint',str(resumed)])
            try:
                s.write(b'nd{i:0}')
                assert s.expect('N')==expected_identity
                assert s.expect('d')[0]['p']==bus
            finally:s.close()
            assert json.loads(resumed.read_text())['engine']==snapshot['engine']
            s=Session(directory,fresh=False,options=['--profile',profile,'--speed','0'])
            try:
                s.write(b'nd{i:0}')
                assert s.expect('N')==expected_identity
                assert s.expect('d')[0]['p']==bus
            finally:s.close()
            original=(directory/'controller.json').read_bytes()
            for extra in [[],['--resume',str(checkpoint)]]:
                result=subprocess.run([EXE,'--serial',str(directory/'serial'),
                    '--state',str(directory/'controller.json'),'--profile',
                    'i2c' if profile=='revc' else 'revc',*extra],capture_output=True,timeout=5)
                assert result.returncode!=0 and b'profile mismatch' in result.stderr
                assert (directory/'controller.json').read_bytes()==original
                assert not (directory/'serial').is_symlink()
            # Exercise local metadata failures through the public application too.
            for bad_tag in ['bogus',5,None]:
                malformed=dict(image,profile=bad_tag)
                state=directory/'controller.json'
                state.write_text(json.dumps(malformed))
                invalid_bytes=state.read_bytes()
                result=subprocess.run([EXE,'--serial',str(directory/'serial'),
                    '--state',str(state),'--profile',profile],capture_output=True,timeout=5)
                assert result.returncode!=0
                assert state.read_bytes()==invalid_bytes
                assert not (directory/'serial').is_symlink()
            state.write_bytes(original)
        checks.append('explicit RevC/I2C profiles preserve identity, inventory, assignments, and checkpoint state; mismatches fail without publishing a PTY or changing stores')
        for index, arguments in enumerate([['--profile','I2C'], ['--profile',''],
                                             ['--profile'], ['--profile','--speed','0']]):
            directory=root/('invalid-profile-%d'%index);directory.mkdir()
            result=subprocess.run([EXE,'--serial',str(directory/'serial'),
                '--state',str(directory/'controller.json'),*arguments],capture_output=True,timeout=5)
            assert result.returncode!=0
            assert list(directory.iterdir())==[]
        checks.append('unknown, empty, missing, and option-shaped profile values fail before creating runtime files')
        for factor in [1,10,60]:
            directory=root/str(factor);directory.mkdir()
            checkpoint=directory/'checkpoint.json'
            s=Session(directory,options=['--speed',str(factor),'--checkpoint',str(checkpoint)])
            start=time.monotonic()
            try:
                setup(s)
                time.sleep(.3)
                # Normal queries still work during autonomous simulation.
                s.write(b'n')
                s.expect('N')
                # Clock advancement ends before process/sanitizer teardown.
                stop_requested=time.monotonic()
            finally:
                s.close()
            elapsed=stop_requested-start
            snapshot=json.loads(checkpoint.read_text())
            plant=snapshot['engine']['plant']
            simulated=plant['age_ms']/1000
            assert max(0,elapsed*factor-.3*factor-.2)<=simulated<=elapsed*factor+.5*factor, (factor,simulated,elapsed)
            assert simulated>0 and plant['temperatures_c'][1]>20
            assert snapshot['engine']['settings']['mode']==ord('t')
            # A paused resume must not add time spent stopped, nor reseed histories.
            time.sleep(.05)
            resumed=directory/'resumed.json'
            s=Session(directory,fresh=False,options=['--speed','0','--resume',str(checkpoint),'--checkpoint',str(resumed)])
            try:
                time.sleep(.05)
                s.write(b'ns')
                s.expect('N')
                assert s.expect('S')['mode']=='t'
            finally:
                s.close()
            assert json.loads(resumed.read_text())['engine']==snapshot['engine']
        checks.append('real process 1x/10x/60x pacing advances external heat; paused resume adds no downtime or reseeding')
        paused=root/'pause';paused.mkdir()
        checkpoint=paused/'paused.json'
        s=Session(paused,options=['--speed','0','--checkpoint',str(checkpoint)])
        try:
            s.write(b'j{Kp:7')
            start=time.monotonic()
            s.expect('D',dict(logType='I',logID=12,V=['Kp','7']))
            assert .6<time.monotonic()-start<2.5
            s.expect('S');s.expect('C')
            s.silent()
        finally:
            s.close()
        assert json.loads(checkpoint.read_text())['engine']['controller_ms']==0
        checks.append('pause stops simulated time but retains real wall-clock token waiting and command effects')
        # Resume a known suspended short command at1x. The parser's wall-clock
        # timeout begins when dispatch resumes, rather than during the bus wait.
        for profile in ('revc','i2c'):
            directory=root/('display-pause-'+profile);directory.mkdir()
            captured=directory/'captured.json'
            s=Session(directory,options=['--profile',profile,'--speed','0','--checkpoint',str(captured)])
            try:
                s.write(b'E');s.expect('D',dict(logType='I',logID=15,V=[]))
            finally:s.close()
            image=json.loads(captured.read_text());engine=image['engine']
            engine['controller_ms']=3600000;engine['last_evaluation_ms']=3599000;engine['last_lcd_reset']=3600
            engine['display_reset']=dict(started_ms=3600000,queued_hex=b'j{Kp:7'.hex().upper())
            suspended=directory/'suspended.json';suspended.write_text(json.dumps(image))
            frozen=directory/'frozen.json'
            s=Session(directory,fresh=False,options=['--profile',profile,'--speed','0',
                      '--resume',str(suspended),'--checkpoint',str(frozen)])
            try:s.silent(1.15)
            finally:s.close()
            assert json.loads(frozen.read_text())['engine']==engine
            s=Session(directory,fresh=False,options=['--profile',profile,'--speed','1','--resume',str(suspended)])
            start=time.monotonic()
            try:
                first=s.line(timeout=5)
                assert first.startswith(b'D:') and json.loads(first[2:])==dict(logType='I',logID=12,V=['Kp','7'])
                assert 2.9<time.monotonic()-start<4.8
                s.expect('S');assert s.expect('C')['Kp']==7
            finally:s.close()
            checks.append(profile+' suspended input survives resume and gets a fresh wall-clock token timeout after dispatch resumes')
        # Resume must not silently mix a checkpoint with subsequently changed saved configuration.
        state=root/'1'/'controller.json'
        mismatched_checkpoint=root/'1'/'checkpoint.json'
        image=json.loads(state.read_text());image['constants_raw']['Kp']=4096
        state.write_text(json.dumps(image))
        p=subprocess.run([EXE,'--serial',str(paused/'serial'),'--state',str(state),'--resume',str(mismatched_checkpoint)],capture_output=True,timeout=5)
        assert p.returncode!=0 and b'does not match' in p.stderr
        assert json.loads(state.read_text())==image
        checks.append('mismatched saved state is rejected outside serial without rolling back the controller store')
        # Scenarios are read-only inputs; they must not require adjacent writable lock files.
        scenario=root/'scenario.json';scenario.write_text(json.dumps({'fermentation_enabled':True,'fermentation_age_hours':20}))
        directory=root/'scenario';directory.mkdir()
        s=Session(directory,options=['--speed','0','--scenario',str(scenario)])
        try:s.write(b'n');s.expect('N')
        finally:s.close()
        assert not Path(str(scenario)+'.lock').exists()
        checks.append('scenario input is read without creating adjacent locks or modifying input data')
        original=scenario.read_bytes()
        linked=root/'scenario-hardlink.json';os.link(scenario,linked)
        symlink=root/'scenario-link.json';symlink.symlink_to(scenario)
        for target in [scenario,root/'scenario'/'..'/'scenario.json',linked,symlink]:
            result=subprocess.run([EXE,'--serial',str(root/'collision-serial'),
                '--state',str(root/'collision-store.json'),'--scenario',str(scenario),
                '--checkpoint',str(target),'--speed','0'],capture_output=True,timeout=5)
            assert result.returncode!=0 and b'scenario input overlaps' in result.stderr
            assert scenario.read_bytes()==original and linked.read_bytes()==original
            assert not (root/'collision-serial').is_symlink()
            assert not Path(str(target)+'.lock').exists()
        checks.append('scenario/checkpoint direct, normalized, hardlink, and symlink collisions fail before locks, PTY publication, or input replacement')

    result=dict(status='passed',platform=sys.platform,checks=checks)
    out=Path('test-results');out.mkdir(exist_ok=True)
    (out/'process.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    run()
