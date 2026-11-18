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


def qualified_minimum_on(executable, direction, profile):
    """Original replay of the identified LED-bench heating/cooling hold observations.

    Constant 20 C synthetic inputs replace physical temperatures. No private
    timer/history injection is used to create the observed public transition.
    """
    assert direction in ('heat', 'cool')
    heating = direction == 'heat'
    slot, wait_state, active_state, hold_state = (4,6,3,9) if heating else (3,5,4,8)
    bus=14 if profile=='i2c' else 18
    pins=(5,6,2,10) if profile=='i2c' else (6,5,2,19)
    d=Driver(executable,profile=profile)
    try:
        d.call('construct',state={'valid':True,'slots':[], 'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A1010000000204'),(1,5,'28A10100000001E6'),(2,6,'28A101000000035A')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}'%(i,f,bus,rom))
        for i,f,pin in [(3,3,pins[0]),(4,2,pins[1]),(5,4,pins[2]),(6,7,pins[3])]:
            d.call('feed',bytes='U{i:%d,f:%d,h:1,p:%d,x:1}'%(i,f,pin))
        d.call('feed',bytes='j{fridgeSlowFilt:7,heatEst:5,coolEst:5}')
        d.call('feed',bytes='R');d.call('restart')
        d.call('feed',bytes='j{mode:f,fridgeSet:%d}' % (23 if heating else 17))
        d.call('advance',milliseconds=599000)
        rows=decode_frames(d.call('feed',bytes='tld{i:%d,r:1}' % slot)[0])
        assert rows[0][1]['State']==wait_state and rows[1][1][3].endswith('00m01') and rows[2][1][0]['v']==0
        d.call('advance',milliseconds=1000)
        rows=decode_frames(d.call('feed',bytes='td{i:%d,r:1}' % slot)[0])
        assert rows[0][1]['State']==active_state and rows[1][1][0]['v']==1
        d.call('advance',milliseconds=10000)
        d.call('feed',bytes='j{fridgeSet:%d}' % (17 if heating else 23))
        d.call('advance',milliseconds=170000)
        rows=decode_frames(d.call('feed',bytes='tld{i:%d,r:1}' % slot)[0])
        assert rows[0][1]['State']==hold_state and rows[1][1][3]==('Heat' if heating else 'Cool')+' time left 00m00' and rows[2][1][0]['v']==1
        d.call('advance',milliseconds=1000)
        rows=decode_frames(d.call('feed',bytes='td{i:%d,r:1}' % slot)[0])
        assert rows[0][1]['State']==0 and rows[1][1][0]['v']==0
    finally:
        d.close()
    return [profile+'.observed_%s_hold_zero_countdown_then_idle_output_off' % direction]


def qualified_missing_peak(executable, profile, direction):
    """Reached artifact-specific I19/I20 adaptation through ordinary commands and real history.

    Constant synthetic20.5 C replaces the uncontrolled measured input. The
    assertion is the reached sentinel-error factor, saved result, and gate;
    it does not import the physical trace or claim its exact host latency.
    """
    positive=direction=='heat'
    assert direction in ('heat','cool')
    bus=14 if profile=='i2c' else 18
    pins=(5,6) if profile=='i2c' else (6,5)
    d=Driver(executable,profile=profile)
    try:
        d.call('construct',state={'valid':True,'slots':[], 'scenario':{
            'physical_loads':[], 'initial_temperatures_c':{'beer':20.5,'chamber':20.5,'room':20.5}}})
        for i,f,rom in [(0,9,'28A1010000000204'),(1,5,'28A10100000001E6'),(2,6,'28A101000000035A')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}'%(i,f,bus,rom))
        for i,f,pin in [(3,3,pins[0]),(4,2,pins[1])]:
            d.call('feed',bytes='U{i:%d,f:%d,h:1,p:%d,x:1}'%(i,f,pin))
        d.call('feed',bytes='j{fridgeSlowFilt:7,heatEst:%d,coolEst:%d}'%(40 if positive else 5,5 if positive else 20))
        d.call('feed',bytes='R');d.call('restart')
        d.call('feed',bytes='j{mode:f,fridgeSet:%s}'%(23.5 if positive else 17.5))
        d.call('advance',milliseconds=600000)
        assert decode_frames(d.call('feed',bytes='t')[0])[0][1]['State']==(3 if positive else 4)
        d.call('advance',milliseconds=10000)
        d.call('feed',bytes='j{fridgeSet:%s}'%(17.5 if positive else 23.5))
        d.call('advance',milliseconds=171000)
        assert decode_frames(d.call('feed',bytes='t')[0])[0][1]['State']==0
        d.call('advance',milliseconds=600000)
        rows=decode_frames(d.call('feed',bytes='tld{i:%d,r:1}'%(3 if positive else 4))[0])
        assert rows[0][1]['State']==7 and rows[1][1][3]=='Waiting for peak    ' and rows[2][1][0]['v']==0
        wire,_=d.call('advance',milliseconds=(900 if positive else 1800)*1000-600000)
        assert not [r for p,r in decode_frames(wire) if p=='D' and r['logID'] in (17,18,19,20)]
        wire,_=d.call('advance',milliseconds=1000)
        diagnostic=[r for p,r in decode_frames(wire) if p=='D']
        assert diagnostic==[dict(logType='I',logID=19 if positive else 20,V=([' 20.5',' 22.5',' 40.000',' 26.641'] if positive else [' 20.5',' 19.5',' 20.000',' 13.320']))]
        rows=decode_frames(d.call('feed',bytes='s')[0])
        assert rows[0][1]['heatEst' if positive else 'coolEst']==(26.641 if positive else 13.32)
        d.call('feed',bytes='R');d.call('restart')
        assert decode_frames(d.call('feed',bytes='s')[0])[0][1]['heatEst' if positive else 'coolEst']==(26.641 if positive else 13.32)
    finally:d.close()
    return [profile+'.observed_missing_'+direction+'_peak_factor_persistence_and_competing_gate']


def qualified_beer_live_writes(executable, profile):
    """Observed live-write invariants under an original, synthetic input ramp.

    The two matched controls have equal effective coefficients and equal seeded
    histories, despite deliberately different stored constants. A named-write
    implementation must violate these physically observed invariants.
    """
    def trace(fast, slow, patch=None):
        d=Driver(executable,profile=profile)
        try:
            d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
            for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204'),(2,6,'28A101000000035A')]:
                d.call('feed',bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}'%(i,f,14 if profile=='i2c' else 18,rom))
            d.call('feed',bytes='j{beerFastFilt:%d,beerSlowFilt:%d,beerSlopeFilt:3}'%(fast,slow))
            d.call('feed',bytes='R');d.call('restart')
            d.call('feed',bytes='j{Kp:1,Ki:0,Kd:0,mode:b,beerSet:25}')
            if patch:d.call('feed',bytes=patch)
            constants=decode_frames(d.call('feed',bytes='c')[0])[0][1]
            d.call('advance',milliseconds=0)
            values=[]
            waveform=[20]*10+[20+i/5 for i in range(1,21)]+[24]*10+[24-i/5 for i in range(1,21)]+[20]*20
            for temperature in waveform:
                d.call('precondition',fields={'physical_temperatures_c':[temperature,20,20]})
                d.call('advance',milliseconds=1000)
                rows=decode_frames(d.call('feed',bytes='tv')[0])
                values.append((rows[0][1]['BeerTemp'],rows[1][1]['beerDiff']))
            return constants,values
        finally:d.close()

    baseline,ordinary=trace(1,2)
    stored_fast,unchanged=trace(1,2,'j{beerFastFilt:4}')
    named_fast,changed=trace(4,2)
    assert baseline['beerFastFilt']==1 and stored_fast['beerFastFilt']==4
    assert unchanged==ordinary and unchanged!=changed
    stored_slow,misrouted=trace(1,2,'j{beerSlowFilt:4}')
    assert stored_slow['beerSlowFilt']==4 and named_fast['beerSlowFilt']==2
    assert misrouted==changed and misrouted!=ordinary
    stored_slope, changed_slow=trace(1,2,'j{beerSlopeFilt:1}')
    named_slow, reference_slow=trace(1,1)
    assert stored_slope['beerSlopeFilt']==1 and named_slow['beerSlopeFilt']==3
    assert changed_slow==reference_slow and changed_slow!=ordinary
    assert [v[0] for v in changed_slow]==[v[0] for v in ordinary]
    return [profile+'.observed_fast_write_saved_only_and_slow_write_live_fast',
            profile+'.observed_slope_write_changes_live_slow']


def qualified_filter_reset_history(executable, profile):
    """Observed C history retention and R reseeding, using an original input step.

    These assertions cover the discontinuity/readback facts, not an invented
    exact replay of the physical trace's unobserved startup input values.
    """
    d=Driver(executable,profile=profile)
    try:
        d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204'),(2,6,'28A101000000035A')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}'%(i,f,14 if profile=='i2c' else 18,rom))
        d.call('feed',bytes='j{beerFastFilt:1,beerSlowFilt:2,beerSlopeFilt:3,Kp:1,Ki:0,Kd:0,mode:b,beerSet:25}')
        d.call('feed',bytes='R');d.call('restart');d.call('advance',milliseconds=0)
        d.call('precondition',fields={'physical_temperatures_c':[24,20,20]})
        d.call('advance',milliseconds=5000)
        d.call('feed',bytes='j{beerSlopeFilt:1}')
        d.call('advance',milliseconds=5000)
        before=decode_frames(d.call('feed',bytes='tv')[0])
        assert before[0][1]['BeerTemp']!=24 and before[1][1]['beerDiff']!=1
        d.call('feed',bytes='C')
        after=decode_frames(d.call('feed',bytes='tv')[0])
        assert before==after
        factory=decode_frames(d.call('feed',bytes='c')[0])[0][1]
        assert [factory[k] for k in ('beerFastFilt','beerSlowFilt','beerSlopeFilt')]==[3,4,4]
        d.call('advance',milliseconds=1000)
        after=decode_frames(d.call('feed',bytes='tv')[0])
        assert after[0][1]['BeerTemp']!=24 and after[1][1]['beerDiff']!=1
        d.call('feed',bytes='R');d.call('restart');d.call('advance',milliseconds=0)
        rows=decode_frames(d.call('feed',bytes='tvc')[0])
        assert rows[0][1]['BeerTemp']==24 and rows[1][1]['beerDiff']==1 and rows[1][1]['beerSlope']==0
        assert [rows[2][1][k] for k in ('beerFastFilt','beerSlowFilt','beerSlopeFilt')]==[1,2,1]
    finally:d.close()
    return [profile+'.observed_factory_history_retention_and_saved_restart_reseeding']


def qualified_revc_slope_restart(executable):
    """Original public-path probe of the observed saved reload and slope cadence.

    A gentle synthetic ramp replaces the measured hand pulse. No captured bytes
    or private filter histories are inputs to these assertions.
    """
    def trace(saved_slope, live_patch=False):
        d=Driver(executable,profile='revc')
        try:
            d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
            for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204')]:
                d.call('feed',bytes='U{i:%d,f:%d,h:2,p:18,a:%s}'%(i,f,rom))
            d.call('feed',bytes='j{beerFastFilt:1,beerSlowFilt:2,beerSlopeFilt:%d,Kp:1,Ki:0,Kd:0,mode:b,beerSet:25}'%saved_slope)
            if live_patch:
                d.call('advance',milliseconds=12000)
                d.call('feed',bytes='j{beerSlopeFilt:1}')
                d.call('feed',bytes='C')
            d.call('feed',bytes='R');d.call('restart')
            saved=decode_frames(d.call('feed',bytes='c')[0])[0][1]
            d.call('advance',milliseconds=0)
            values=[]
            for sample in range(1,331):
                temperature=20+sample/1024
                d.call('precondition',fields={'physical_temperatures_c':[temperature,20,20]})
                d.call('advance',milliseconds=1000)
                values.append(decode_frames(d.call('feed',bytes='v')[0])[0][1]['beerSlope'])
            return saved,values
        finally:d.close()
    saved,restored=trace(3,True)
    _,reference=trace(1)
    _,different=trace(3)
    assert [saved[k] for k in ('beerFastFilt','beerSlowFilt','beerSlopeFilt')]==[1,2,1]
    assert restored==reference and restored!=different
    assert all(v==0 for v in restored[:255]) and any(v!=0 for v in restored[255:])
    changes=[i+1 for i in range(1,len(restored)) if restored[i]!=restored[i-1]]
    assert len(changes)>2 and all(b-a==3 for a,b in zip(changes,changes[1:])), changes
    return ['revc.observed_saved_slope_reload_and_three_evaluation_response']


def observed_revc_long_loss_recovery(executable):
    """Observed long-absence first-recovery equality with the raw input.

    A small synthetic step checks that equality. This does not identify all
    hidden physical pre-loss histories, conversion freshness, or the threshold.
    """
    d=Driver(executable,profile='revc')
    try:
        d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204'),(2,6,'28A101000000035A')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:18,a:%s}'%(i,f,rom))
        d.call('advance',milliseconds=10000)
        assert decode_frames(d.call('feed',bytes='t')[0])[0][1]['BeerTemp']==20
        d.call('precondition',fields={'connected':[False,False,False]})
        d.call('advance',milliseconds=125000)
        assert decode_frames(d.call('feed',bytes='t')[0])[0][1]['BeerTemp'] is None
        d.call('precondition',fields={'connected':[True,True,True],'physical_temperatures_c':[20.0625,20,20]})
        d.call('advance',milliseconds=1000)
        rows=dict(decode_frames(d.call('feed',bytes='td{r:1}')[0]))
        assert rows['T']['BeerTemp']==20.06 and rows['d'][0]['v']==20.063
    finally:d.close()
    return ['revc.observed_long_absence_first_recovery_raw_fast_equality']


def ordinary_revc_timer_sequence(executable):
    """Public ordinary stops isolate five documented off/switch waits.

    Constant synthetic temperatures remove thermal-peak ambiguity. Each real
    next demand cancels peak detection without resetting the last-active age.
    """
    d=Driver(executable,profile='revc')
    seconds=0;clock_ms=0
    def send(command):return d.call('feed',bytes=command)
    def tick():
        nonlocal seconds,clock_ms
        d.call('advance',milliseconds=1000);clock_ms+=1000
        wire=send('tld{r:1}')[0]
        for _ in range(30):
            if any(p=='L' for p,v in decode_frames(wire)):break
            more,_=d.call('advance',milliseconds=100);clock_ms+=100;wire+=more
        else:raise AssertionError('No reply after the bounded periodic display pause')
        seconds=clock_ms//1000
        return dict(decode_frames(wire))
    def active(direction,cap):
        for _ in range(cap):
            rows=tick()
            if rows['T']['State']==(3 if direction=='heat' else 4):
                outputs={r['f']:r['v'] for r in rows['d'] if r['h']==1}
                assert outputs[2 if direction=='heat' else 3]==1
                return seconds
        raise AssertionError('No eligible demand activation')
    try:
        d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A1010000000204'),(1,5,'28A10100000001E6')]:
            send('U{i:%d,f:%d,h:2,p:18,a:%s}'%(i,f,rom))
        for i,f,pin in [(3,3,6),(4,2,5)]:send('U{i:%d,f:%d,h:1,p:%d,x:1}'%(i,f,pin))
        send('j{fridgeSlowFilt:1,Kp:1,Ki:0,Kd:0,heatEst:5,coolEst:5}')
        send('R');d.call('restart')
        send('j{mode:f,fridgeSet:1}');on=active('cool',601);prior='cool';mode='f'
        schedule=[(600,'cool','f'),(300,'cool','b'),(600,'heat','f'),(300,'heat','f'),(600,'cool','f')]
        for threshold,direction,next_mode in schedule:
            while seconds-on<185:tick()
            send('j{beerSet:20.25}' if mode=='b' else 'j{fridgeSet:%s}'%(19.5 if prior=='heat' else 20.5))
            rows=tick()
            assert rows['T']['State'] not in (3,4,8,9)
            assert all(r['v']==0 for r in rows['d'] if r['h']==1)
            off=seconds
            send('j{mode:b,beerSet:10}' if next_mode=='b' else 'j{mode:f,fridgeSet:%s}'%(30 if direction=='heat' else 1))
            previous=None
            for _ in range(threshold+30):
                rows=tick()
                outputs={r['f']:r['v'] for r in rows['d'] if r['h']==1}
                if rows['T']['State']==(3 if direction=='heat' else 4) and outputs[2 if direction=='heat' else 3]==1:
                    assert previous is not None and previous['L'][3].endswith('00m01')
                    on=seconds
                    break
                assert rows['T']['State']==(6 if direction=='heat' else 5)
                assert all(v==0 for v in outputs.values())
                previous=rows
            else:raise AssertionError('No eligible timer release')
            # The callback origin precedes the off write; bus blocking does not
            # restart it or convert it into time since the latest read request.
            assert on-off==threshold-1
            prior=direction;mode=next_mode
    finally:d.close()
    return ['revc.public_five_ordinary_off_and_switch_timer_histories']


def qualified_revc_factory_routes(executable):
    """C applies named factory coefficients while retaining transient histories.

    The independently specified control retains the pre-C state and changes
    only the three live coefficient values. Public responses must agree under
    a discriminating synthetic continuation; stored labels alone cannot pass.
    """
    d=Driver(executable,profile='revc')
    try:
        d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:18,a:%s}'%(i,f,rom))
        d.call('feed',bytes='j{beerFastFilt:1,beerSlowFilt:2,beerSlopeFilt:3,Kp:1,Ki:0,Kd:0,mode:b,beerSet:25}')
        d.call('feed',bytes='R');d.call('restart')
        for sample in range(300):
            d.call('precondition',fields={'physical_temperatures_c':[20+sample/1024,20,20]})
            d.call('advance',milliseconds=1000)
        before=d.call('checkpoint')[1]['checkpoint']
        d.call('feed',bytes='C')
        after=d.call('checkpoint')[1]['checkpoint']
        expected=json.loads(json.dumps(after))
        expected['histories']=json.loads(json.dumps(before['histories']))
        for entry in expected['histories']:
            if entry['function'] in (5,9):
                for name,b in [('fast',3 if entry['function']==9 else 1),('slow',4),('slope',4 if entry['function']==9 else 3)]:
                    entry['history'][name]['b']=b
        def continuation(snapshot):
            d.call('restore',snapshot=snapshot)
            values=[]
            for sample in range(150):
                d.call('precondition',fields={'physical_temperatures_c':[20.5+sample/2048,20,20]})
                d.call('advance',milliseconds=1000)
                rows=dict(decode_frames(d.call('feed',bytes='tv')[0]))
                values.append((rows['T']['BeerTemp'],rows['V']['beerDiff'],rows['V']['beerSlope']))
            return values
        actual=continuation(after);control=continuation(expected)
        assert actual==control
        for channel,(name,old_b) in enumerate([('fast',1),('slow',2),('slope',3)]):
            unchanged=json.loads(json.dumps(expected))
            entry=next(v for v in unchanged['histories'] if v['function']==9)
            entry['history'][name]['b']=old_b
            wrong=continuation(unchanged)
            assert [v[channel] for v in actual]!=[v[channel] for v in wrong], name
    finally:d.close()
    return ['revc.observed_factory_named_live_coefficients_with_retained_transient_history']


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
        assert wire==b'', 'Periodic RevC reset must finish before dispatch'
        wire,_=d.advance(2)
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

    for profile in ('i2c','revc'):
        for direction in ('heat','cool'):
            checks.extend(qualified_minimum_on(executable, direction, profile))
    checks.extend(qualified_missing_peak(executable, 'i2c', 'cool'))
    checks.extend(qualified_missing_peak(executable, 'revc', 'heat'))
    checks.extend(qualified_revc_slope_restart(executable))
    checks.extend(observed_revc_long_loss_recovery(executable))
    checks.extend(ordinary_revc_timer_sequence(executable))
    checks.extend(qualified_revc_factory_routes(executable))
    for profile in ('i2c','revc'):
        checks.extend(qualified_beer_live_writes(executable, profile))
        checks.extend(qualified_filter_reset_history(executable, profile))
    result=dict(status='passed',checks=checks)
    out=Path('test-results');out.mkdir(exist_ok=True)
    (out/'dynamics.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    run(sys.argv[1])
