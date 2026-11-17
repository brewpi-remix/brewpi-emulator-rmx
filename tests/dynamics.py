# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original controller/energy/clock tests. No reference code or captures are used."""
import json
from pathlib import Path
import sys
from fixtures import Driver, DATA, decode_frames, equal

DEFAULTS = json.loads((DATA / 'defaults-v1.json').read_text())


class Simulation(Driver):
    def __init__(self, executable, scenario=None, assigned=True):
        super().__init__(executable)
        state = dict(valid=True, slots=DEFAULTS['all_assigned_slots'] if assigned else [])
        if scenario is not None:
            state['scenario'] = scenario
        self.call('construct', state=state)

    def send(self, text):
        return self.call('feed', bytes=text)

    def advance(self, seconds, allowed=True):
        return self.call('advance', milliseconds=round(seconds * 1000), controller_allowed=allowed)

    def snapshot(self):
        return self.call('checkpoint')[1]['checkpoint']


def near(a, b, tolerance=1e-6):
    assert abs(a - b) <= tolerance, (a, b, tolerance)


def run(executable):
    checks = []
    # Energy accounting tests use actual physical pin loads in test mode;
    # controller policy is tested separately below.
    d = Simulation(executable)
    try:
        d.send('j{mode:t}d{i:3,w:1}')
        _, obs = d.advance(600)
        p = obs['plant']
        cb, cc = p['beer_capacity_j_per_k'], p['chamber_capacity_j_per_k']
        near(cb, 85114.86)
        near(cc, 2484)
        near(p['load_energy_j'], 15000, .00001)
        beer, chamber, _ = p['temperatures_c']
        assert 20 < beer < chamber
        near(cb * (beer - 20) + cc * (chamber - 20), p['load_energy_j'] + p['room_energy_j'], 1e-5)
        wire, _ = d.send('td{i:1,r:1}l')
        records = decode_frames(wire)
        assert records[0][1]['FridgeTemp'] > 20
        assert records[1][1][0]['v'] > 20
        assert all(len(s) == 20 for s in records[-1][1])
        assert records[-1][1][2].startswith('Fridge')
        d.advance(8)
        wire,_=d.send('l')
        assert decode_frames(wire)[0][1][2].startswith('Room')
        checks.append('heater energy balance, conserved internal conduction, physical lag, live readings, and room LCD')
        # Removing a function leaves its electrical latch in place. E must not
        # introduce a universal quiescent policy that the firmware lacks.
        d.send('U{i:3,f:0}')
        before = d.snapshot()['plant']['load_energy_j']
        _, obs = d.advance(10)
        near(obs['plant']['load_energy_j'] - before, 250)
        age = obs['plant']['age_ms']
        d.send('R')
        _, obs = d.call('restart')
        assert obs['controller_millis'] == 0 and obs['plant']['age_ms'] == age
        assert obs['plant']['temperatures_c'][0] > 20
        checks.append('uninstall preserves a physical latch; R resets MCU state while retaining external plant/age')
    finally:
        d.close()

    for target, watts in [(3,25),(4,-60)]:
        d = Simulation(executable, {'beer_chamber_conductance_w_per_k': 0, 'chamber_room_conductance_w_per_k': 0})
        try:
            d.send('j{mode:t}d{i:' + str(target) + ',w:1}')
            _, obs = d.advance(200)
            p=obs['plant']
            near(p['temperatures_c'][0],20)
            near(p['temperatures_c'][1],20+watts*200/2484,1e-8)
            near(p['room_energy_j'],0)
            near(p['load_energy_j'],watts*200,1e-7)
        finally:
            d.close()
    checks.append('analytic isolated heater/cooler ramps have correct watts, signs, and thermal capacity')

    # Reassigning a logical heater to the zero-watt light pin must not move
    # the physical heater. Other declared physical loads can add their own heat.
    d=Simulation(executable, {'beer_chamber_conductance_w_per_k':0,'chamber_room_conductance_w_per_k':0})
    try:
        d.send('j{mode:t}U{i:3,f:2,h:1,p:2,x:1}d{i:3,w:1}')
        _,obs=d.advance(100)
        near(obs['plant']['load_energy_j'],0)
    finally:
        d.close()
    checks.append('function reassignment follows fixed electrical wiring, without relocating physical equipment')

    d=Simulation(executable, {'fermentation_enabled':True,'fermentation_age_hours':20,
                            'beer_chamber_conductance_w_per_k':0,'chamber_room_conductance_w_per_k':0})
    try:
        _,obs=d.advance(600)
        p=obs['plant']
        near(p['fermentation_energy_j'],3000,1e-6)
        near(p['temperatures_c'][0],20+3000/85114.86,1e-8)
        near(p['temperatures_c'][1],20)
    finally:
        d.close()
    for age,watts in [(0,0),(8,0),(14,2.5),(20,5),(44,5),(68,2.5),(92,0),(100,0)]:
        d=Simulation(executable, {'fermentation_enabled':True,'fermentation_age_hours':age})
        try:
            near(d.snapshot()['plant']['fermentation_watts'],watts)
        finally:
            d.close()
    checks.append('reviewed fermentation breakpoints/interpolation and independent beer-node energy input')

    # Same simulated events and fixed integration step under 1x/10x/60x pacing.
    snapshots=[]
    for chunk in [1,10,60]:
        d=Simulation(executable, {'noise_amplitude_c':.15,'probe_lag_seconds':2,'random_seed':123})
        try:
            d.send('j{mode:f,fridgeSet:24}')
            _,obs=d.call('advance',milliseconds=chunk*1000,repeat=1200//chunk)
            snapshots.append(d.snapshot())
            assert obs['plant']['load_energy_j']>0
            assert obs['plant']['temperatures_c'][1]>20
        finally:
            d.close()
    assert equal(snapshots[0],snapshots[1]) and equal(snapshots[0],snapshots[2])
    checks.append('1x/10x/60x grouping yields identical controller, filter, random, plant, clock, and LCD state')

    # Checkpoint resumes every stateful component, including a fractional step,
    # histories/countdowns, latched pins, raw accumulator, and random state.
    d=Simulation(executable, {'noise_amplitude_c':.15,'probe_lag_seconds':5,'random_seed':91})
    restored=Simulation(executable)
    try:
        d.send('j{mode:f,fridgeSet:24}')
        d.call('advance',milliseconds=723456)
        snap=d.snapshot()
        assert snap['pending_ms']==56
        restored.call('restore',snapshot=snap)
        assert equal(restored.snapshot(),snap)
        wire_a,obs_a=d.advance(1200)
        wire_b,obs_b=restored.advance(1200)
        assert wire_a==wire_b and equal(obs_a,obs_b)
        assert equal(d.snapshot(),restored.snapshot())
        wire,_=d.send('l')
        lcd=decode_frames(wire)[0][1]
        assert all(len(row)==20 for row in lcd)
        assert lcd[0].startswith('Mode   Fridge Const.')
        checks.append('checkpoint resumes exact histories, fractional step, physical state, randomness, and raw LCD bytes')
    finally:
        d.close();restored.close()

    # At a controller stop, leave transition T ahead of output writes. Serial
    # queries do not advance time; parser blocking does advance physical time.
    d=Simulation(executable)
    try:
        d.send('j{mode:f,fridgeSet:24}')
        _,obs=d.advance(599)
        assert obs['state']==6 and obs['plant']['load_energy_j']==0
        wire,obs=d.advance(1)
        assert obs['state']==3 and any(prefix=='T' and payload['State']==3 for prefix,payload in decode_frames(wire))
        initial=d.snapshot()
        for _ in range(5):d.send('ntsv')
        assert equal(d.snapshot(),initial)
        d.send('j{Kp:7')
        _,obs=d.advance(20)
        assert obs['controller_seconds']==620
        assert obs['last_heat_seconds']==0  # Entry changes state/output; the next active evaluation stamps it.
        assert obs['plant']['load_energy_j']>0
        wire,_=d.call('timeout')
        assert decode_frames(wire)[-1][0]=='C'
        _,obs=d.advance(0)
        assert obs['last_heat_seconds']==620
        checks.append('600-second switch/off boundary, transition T, no query ticks, and single post-block controller evaluation')
    finally:
        d.close()

    # A transport's closed output gate defers controller work, not elapsed
    # physical time. Reopening it must not replay every missed evaluation.
    d=Simulation(executable)
    try:
        d.send('j{mode:t}d{i:3,w:1}')
        before=d.snapshot()
        wire,_=d.advance(5.056,allowed=False)
        blocked=d.snapshot()
        assert not wire
        assert blocked['controller_ms']==before['controller_ms']+5000
        assert blocked['pending_ms']==56
        assert blocked['plant']['age_ms']==before['plant']['age_ms']+5000
        near(blocked['plant']['load_energy_j']-before['plant']['load_energy_j'],125)
        for key in ['last_evaluation_ms','histories','variables','last_lcd_reset']:
            assert equal(blocked[key],before[key]),key
        d.advance(0)
        released=d.snapshot()
        assert released['last_evaluation_ms']==released['controller_ms']
        assert equal(released['plant'],blocked['plant'])
        assert released['pending_ms']==56
        d.advance(0)
        assert equal(d.snapshot(),released)
        checks.append('closed output gate retains physical heat and fractional time; release services one controller evaluation without backlog replay')
    finally:
        d.close()

    d=Simulation(executable)
    try:
        # Width wrap is constructed coherently in the controller-only fixture.
        d.call('precondition',fields={'mode':'f','fridge_target_c':20,
                                    'controller_millis':65535000,'controller_seconds':65535,
                                    'last_heat_seconds':65530,'last_cool_seconds':65530})
        _,obs=d.advance(2)
        assert obs['controller_seconds']==1
        assert obs['controller_millis']==65537000
        d.call('precondition',fields={'controller_millis':4294967000})
        _,obs=d.advance(1)
        assert obs['controller_millis']==704 and obs['controller_seconds']==0
        checks.append('controller 16-bit seconds and 32-bit milliseconds wrap independently of plant age')
    finally:
        d.close()

    # Direct evaluations use declared histories and do not stand in for time.
    for error,old,controller_state,previous,measured,expected in [
        (.125,-64,0,20,20,64), (.125,64,0,20,20,128),
        (.125,64,5,20,20,64), (1,800,0,20,20,700),
        (.125,64,0,30,20,64), (-.125,-64,0,20,23,-64),
    ]:
        d=Simulation(executable)
        try:
            d.call('precondition',fields={'mode':'b','beer_target_c':20,'slow_beer_c':20-error,
                    'beer_slope_c_per_hour':0,'diff_integral_raw':old,'integral_evaluation_count':60,
                    'state':controller_state,'fridge_target_c':previous,'fast_fridge_temperature_c':measured})
            _,obs=d.call('pid')
            assert obs['variables_raw']['diffIntegral']==expected, (error,old,obs)
            assert obs['integral_branch_executions']==1
        finally:
            d.close()
    checks.append('integral sign reduction, non-idle suppression, one-eighth decay, limits, and actuator-saturation inhibition')

    for positive,event,turn_temperature in [(True,17,24),(False,18,16)]:
        d=Simulation(executable)
        try:
            d.call('precondition',fields={'physical_temperatures_c':[20,turn_temperature,20]})
            d.call('sensors',repeat=1000)
            estimate=-14336
            d.call('precondition',fields={'state':0,'positive_peak_pending':positive,
                'negative_peak_pending':not positive,'variables_raw':{'posPeakEst':estimate,'negPeakEst':estimate},
                'physical_temperatures_c':[20,20,20]})
            wire,obs=d.call('sensor_peak',repeat=400,until_output=True)
            observed=decode_frames(wire)
            assert len(observed)==1 and observed[0][0]=='D' and observed[0][1]['logID']==event,observed
            args=observed[0][1]['V']
            assert len(args)==4 and all(isinstance(x,str) for x in args)
            estimator='heatEst' if positive else 'coolEst'
            assert obs['store']['settings_raw'][estimator]>(102 if positive else 2560)
            assert obs['positive_peak_pending'] is False and obs['negative_peak_pending'] is False
        finally:
            d.close()
    checks.append('real filtered turning points emit typed I17/I18 and persist adjusted estimators without fabricated captures')

    # Timeout diagnostics retain the error calculated from INVALID_TEMP,
    # even after the logged peak is replaced by the current fast reading.
    for positive,timeout,event,estimate,new in [
        (True,900,19,-13824,67), (False,1800,20,-14848,1705),
    ]:
        d=Simulation(executable)
        try:
            stamp='last_heat_seconds' if positive else 'last_cool_seconds'
            d.call('precondition',fields={'state':0,'controller_seconds':timeout,
                stamp:0,'positive_peak_pending':positive,'negative_peak_pending':not positive,
                'variables_raw':{'posPeakEst':estimate,'negPeakEst':estimate}})
            wire,_=d.call('peaks')
            assert wire==b''
            d.call('precondition',fields={'controller_seconds':timeout+1})
            wire,obs=d.call('peaks')
            estimator='heatEst' if positive else 'coolEst'
            expected_args=[' 20.0',' 21.0' if positive else ' 19.0',
                           ' 0.199' if positive else ' 5.000',
                           ' 0.131' if positive else ' 3.330']
            assert decode_frames(wire)==[('D',dict(logType='I',logID=event,V=expected_args))]
            assert obs['variables_raw']['posPeak' if positive else 'negPeak']==-14336
            assert obs['store']['settings_raw'][estimator]==new
            assert obs['positive_peak_pending'] is False and obs['negative_peak_pending'] is False
        finally:
            d.close()
    checks.append('strict drift timeouts I19/I20 preserve sentinel-derived adaptation, exact formatting, and persistence')

    d=Simulation(executable)
    try:
        snap=d.snapshot()
        corrupt=json.loads(json.dumps(snap));corrupt['histories'].pop()
        try:d.call('restore',snapshot=corrupt)
        except AssertionError as exc:assert 'histories' in str(exc)
        else:raise AssertionError('incomplete history checkpoint accepted')
        assert equal(snap,d.snapshot())
        corrupt=json.loads(json.dumps(snap));del corrupt['settings']['heatEst']
        try:d.call('restore',snapshot=corrupt)
        except AssertionError:pass
        else:raise AssertionError('incomplete live settings accepted')
        assert equal(snap,d.snapshot())
        # This is native instrumentation, not an Arduino-width controller word.
        wide=json.loads(json.dumps(snap));wide['integral_branches']=4294967296
        d.call('restore',snapshot=wide)
        assert equal(wide,d.snapshot())
        snap=wide
        for bad_count in [-1, 1.5, 9007199254740992]:
            corrupt=json.loads(json.dumps(snap));corrupt['integral_branches']=bad_count
            try:d.call('restore',snapshot=corrupt)
            except AssertionError:pass
            else:raise AssertionError('invalid exact counter accepted')
            assert equal(snap,d.snapshot())
        d.advance(3600)
        _,obs=d.advance(1)
        wire,_=d.send('l')
        rows=decode_frames(wire)[0][1]
        assert all(len(row)==20 for row in rows) and rows[3].startswith('Idling for')
        checks.append('checkpoint validation is transactional and periodic LCD reset retains source layout/state behavior')
    finally:
        d.close()

    d=Simulation(executable)
    try:
        d.call('precondition',fields={'connected':[True,False,True]})
        wire,obs=d.advance(61)
        messages=decode_frames(wire)
        assert sum(prefix=='D' and value['logType']=='W' and value['logID']==2 for prefix,value in messages)==1
        assert obs['state']==0
        before=d.snapshot()['histories']
        counter=next(x['history']['countdown'] for x in before if x['function']==5)
        d.call('precondition',fields={'connected':[True,True,True]})
        wire,obs=d.advance(1)
        assert any(prefix=='D' and value['logType']=='I' and value['logID']==0 for prefix,value in decode_frames(wire))
        history=next(x['history'] for x in d.snapshot()['histories'] if x['function']==5)
        assert history['missed']==0 and history['countdown']==(counter-1 if counter>1 else 3)
        checks.append('virtual disconnection/reconnection emits one transition diagnostic and reseeds only stale histories')
    finally:
        d.close()

    d=Simulation(executable)
    try:
        d.send('U{i:7,f:1,h:1,p:4,x:0}')
        d.call('precondition',fields={'door_open':True})
        wire,obs=d.advance(1)
        assert any(prefix=='T' and value['FridgeAnn']=='Fridge door opened' for prefix,value in decode_frames(wire))
        wire,_=d.send('d{i:7,r:1}l')
        frames=decode_frames(wire)
        assert frames[0][1][0]['v']==1
        assert frames[1][1][3].startswith('Door open')
        assert dict(obs['pins'])[2] is False
        d.send('U{i:7,f:1,x:1}')
        wire,_=d.send('d{i:7,r:1}')
        assert decode_frames(wire)[0][1][0]['v']==0
        d.call('precondition',fields={'mode':'o','camera_request_active':True,'camera_last_active_seconds':0,
                                      'controller_millis':599000,'controller_seconds':599})
        _,obs=d.call('outputs');assert obs['camera_request_active'] is True
        d.call('precondition',fields={'controller_millis':600000,'controller_seconds':600})
        _,obs=d.call('outputs');assert obs['camera_request_active'] is False
        checks.append('digital door readback/inversion, door annotation/LCD/light, and exact camera auto-off boundary')
    finally:
        d.close()

    result=dict(status='passed',checks=checks)
    out=Path('test-results');out.mkdir(exist_ok=True)
    (out/'dynamics.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    run(sys.argv[1])
