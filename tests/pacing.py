# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Exercise real-process pacing, pause, checkpoint resume, and environment errors."""
import json
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
    result=dict(status='passed',platform=sys.platform,checks=checks)
    out=Path('test-results');out.mkdir(exist_ok=True)
    (out/'milestone3-process.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    run()
