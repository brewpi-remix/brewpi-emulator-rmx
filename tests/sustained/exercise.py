# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original lifecycle, clock, and host-filesystem fault scenarios."""
import json
import os
from pathlib import Path
import subprocess
from session import Session
from sample import process


def lifecycle(root,binary,monitor,defaults,count):
    baseline=None;rows=[]
    for index in range(count):
        directory=Path(root)/('%04d'%index);s=Session(directory,binary,monitor)
        try:
            s.initialize(defaults);s.query(b'j{Kp:7}','S');s.expect('C')
            s.query(b'C','C');assert s.query(b'c','C')['Kp']==5
            assert json.loads(s.store.read_text())['constants_raw']['Kp']==3584
            quiescent=process(s.pid);shape=(quiescent['fds'],quiescent['threads'])
            if baseline is None:baseline=shape
            assert shape==baseline,('quiescent resource growth',index,shape,baseline)
            s.close();original=json.loads(s.checkpoint.read_text())['engine']
            s=Session(directory,binary,monitor,fresh=False,resume=directory/'checkpoint.json')
            assert s.query(b'c','C')['Kp']==5
            s.close();assert json.loads(s.checkpoint.read_text())['engine']==original
            s=Session(directory,binary,monitor,fresh=False)
            assert s.query(b'c','C')['Kp']==7
            os.close(s.fd);s.fd=None;s.connect();assert s.query(b'c','C')['Kp']==7
            if index%10==0:
                target=os.readlink(s.serial);s.close(killed=True)
                assert os.readlink(s.serial)==target
                failed=subprocess.run([str(binary),'--serial',str(s.serial),'--state',str(s.store),'--speed','0'],capture_output=True,timeout=5)
                assert failed.returncode!=0 and s.serial.is_symlink()
                s.serial.unlink() # Only this owned stale link; never its PTY target.
                s=Session(directory,binary,monitor,fresh=False);assert s.query(b'c','C')['Kp']==7
            s.close()
            rows.append(dict(cycle=index,status='passed',quiescent_fds=shape[0],quiescent_threads=shape[1],full_snapshot_equal=True))
        except BaseException:s.abort();raise
    return dict(status='passed',cycles=rows,baseline_fds=baseline[0],baseline_threads=baseline[1],qualification=count>=100)


def clocks(driver,source):
    import sys
    sys.path.insert(0,str(Path(source)/'tests'))
    from dynamics import Simulation
    rows=[]
    for start,advance in [(65534000,1000),(65535000,1000),(65535500,1500),(65536000,2000),(4294966000,2000),(4294967000,1000),(4294967295,1),(4294967295,100)]:
        simulation=Simulation(str(driver))
        try:
            simulation.call('precondition',fields=dict(mode='f',fridge_target_c=20,controller_millis=start,controller_seconds=(start//1000)&65535,last_heat_seconds=65530,last_cool_seconds=65530))
            _,observed=simulation.call('advance',milliseconds=advance)
            expected_ms=(start+(advance//100)*100)%(2**32);expected_seconds=(expected_ms//1000)%65536
            if observed['controller_millis']!=expected_ms or observed['controller_seconds']!=expected_seconds or observed['pending_ms']!=advance%100:raise AssertionError('reference-width clock arithmetic changed')
            rows.append(dict(start_millis=start,advance_millis=advance,expected_millis=expected_ms,expected_seconds=expected_seconds,status='passed'))
        finally:simulation.close()
    return dict(status='passed',constructed_history=True,oracle='independent modulo arithmetic from the behavioral contract',cases=rows)


def faults(root,binary,monitor,defaults):
    root=Path(root);root.mkdir();directory=root/'baseline';s=Session(directory,binary,monitor)
    s.initialize(defaults);s.query(b'j{Kp:7}','S');s.expect('C');s.close()
    checkpoint=s.checkpoint.read_bytes();store=s.store.read_bytes();rows=[]
    def reject(name,args):
        p=subprocess.run([str(binary),*map(str,args)],capture_output=True,timeout=5)
        if p.returncode==0 or not p.stderr:raise AssertionError('invalid host input accepted: '+name)
        rows.append(dict(name=name,status='passed',exit_code=p.returncode))
    corrupt=root/'corrupt.json';corrupt.write_bytes(b'{incomplete')
    reject('corrupt store',['--serial',root/'corrupt-store-serial','--state',corrupt])
    reject('corrupt checkpoint',['--serial',root/'corrupt-serial','--state',s.store,'--resume',corrupt])
    wrong=json.loads(store);wrong['constants_raw']['Kp']=4096;s.store.write_text(json.dumps(wrong))
    reject('checkpoint/store mismatch',['--serial',root/'mismatch-serial','--state',s.store,'--resume',s.checkpoint]);s.store.write_bytes(store)
    scenario=root/'scenario.json';scenario.write_text('{"noise_amplitude_c":0.1}\n');before=scenario.read_bytes()
    for kind in ['direct','hardlink','symlink']:
        alias=root/('alias-'+kind)
        if kind=='direct':alias=scenario
        elif kind=='hardlink':os.link(scenario,alias)
        else:alias.symlink_to(scenario)
        reject('scenario/output '+kind,['--serial',root/('alias-serial-'+kind),'--state',root/('alias-state-'+kind),'--scenario',scenario,'--checkpoint',alias])
        assert scenario.read_bytes()==before
    # Inject failure in a test-only preload library, never in candidate bytes.
    for stage in ['before','after']:
        directory=root/stage;directory.mkdir();(directory/'controller.json').write_bytes(store)
        environment=dict(os.environ,LD_PRELOAD='/lab/tools/faultio.so',RMX_FAULT_STAGE=stage,RMX_FAULT_TARGET=str(directory/'controller.json'),RMX_FAULT_ARM=str(directory/'armed'))
        s=Session(directory,binary,monitor,fresh=False,environment=environment)
        try:
            s.query(b'n','N') # Startup completed before arming I/O injection.
            previous=s.store.read_bytes();(directory/'armed').touch()
            s.write(b'j{Kp:9}');s.p.wait(timeout=5)
            if s.p.returncode==0:raise AssertionError('injected filesystem error was accepted')
            actual=s.store.read_bytes()
            if stage=='before':assert actual==previous
            else:assert json.loads(actual)['constants_raw']['Kp']==4608
            rows.append(dict(name='fsync failure '+stage+' replacement',status='passed',old_bytes_retained=actual==previous,power_loss_durability_claimed=False))
        finally:s.abort()
    assert checkpoint==(root/'baseline/checkpoint.json').read_bytes()
    return dict(status='passed',checks=rows)
