# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original regressions for the command semantics and local codec."""
import json
from pathlib import Path
import subprocess
import sys
from fixtures import Driver, decode_frames, equal


def records(wire):
    return decode_frames(wire)


def nested_discovery_observation(executable, profile):
    """Original byte assertion for the observed Uno zero-ROM discovery reply."""
    bus = 14 if profile == 'i2c' else 18
    d = Driver(executable, profile=profile)
    try:
        d.call('construct', state=dict(valid=True, slots=[]))
        for index, function, rom in [(0,9,'28A1010000000204'),
                                     (1,5,'28A10100000001E6'),
                                     (2,6,'0000000000000000')]:
            d.call('feed', bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}' % (index,function,bus,rom))
        wire, _ = d.call('feed', bytes='h{h:2,p:%d,v:1,u:0}' % bus)
        expected = (
            b'h:[{"i":0,"t":1,"c":1,"b":1,"f":9,"h":2,"d":0,"p":14,"v": 20.000,"a":"28A1010000000204","j": 0.000},'
            b'{"i":1,"t":1,"c":1,"b":0,"f":5,"h":2,"d":0,"p":14,"v": 20.000,"a":"28A10100000001E6","j": 0.000}'
            b'D:{"logType":"W","logID":2,"V":[14,"0000000000000000"]}\r\n'
            b',{"i":2,"t":1,"c":1,"b":0,"f":6,"h":2,"d":0,"p":14,"v":null,"a":"0000000000000000","j": 0.000}]\r\n')
        expected = expected.replace(b'"p":14', ('"p":%d' % bus).encode()).replace(
            b'"V":[14,', ('"V":[%d,' % bus).encode())
        assert wire == expected, wire
        # A repeated discovery creates the same temporary failed reader again.
        assert d.call('feed', bytes='h{h:2,p:%d,v:1,u:0}' % bus)[0] == expected
        wire, _ = d.call('feed', bytes='h{h:2,p:%d,v:0,u:0}' % bus)
        assert len(records(wire)[0][1]) == 3 and b'D:' not in wire
        assert 'RoomTemp' not in records(d.call('feed', bytes='t')[0])[0][1]
        d.call('feed', bytes='U{i:2,f:6,h:2,p:%d,a:28A101000000035A}' % bus)
        wire, _ = d.call('feed', bytes='h{h:2,p:%d,v:1,u:0}' % bus)
        assert b'D:' not in wire and records(wire)[0][1][2]['v'] == 20
    finally:
        d.close()
    return ['%s.zero_rom_embedded_discovery_diagnostic' % profile]


def read_time_loss_observation(executable):
    """Original byte assertions for RevC loss first noticed by serial reads.

    The control loop is paused between physical loss and the reads, matching
    the observed cached T values and nested ambient/beer/chamber warnings.
    """
    d = Driver(executable, profile='revc')
    roms = ['28A1010000000204', '28A10100000001E6', '28A101000000035A']
    def warning(rom):
        return ('D:{"logType":"W","logID":2,"V":[18,"%s"]}\r\n' % rom).encode()
    def row(i, f, b):
        return ('{"i":%d,"t":1,"c":1,"b":%d,"f":%d,"h":2,"d":0,"p":18,"v":null,"a":"%s","j": 0.000}' % (i,b,f,roms[i])).encode()
    prefix = (b'T:{"BeerTemp": 20.00,"BeerSet":null,"BeerAnn":null,'
              b'"FridgeTemp": 20.00,"FridgeSet":null,"FridgeAnn":null')
    try:
        d.call('construct', state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f in enumerate((9,5,6)):
            d.call('feed', bytes='U{i:%d,f:%d,h:2,p:18,a:%s}' % (i,f,roms[i]))
        normal = d.call('feed', bytes='t')[0]
        d.call('precondition', fields={'connected':[False,False,False]})
        wire = d.call('feed', bytes='t')[0]
        assert wire == prefix + warning(roms[2]) + b',"State":0}\r\n', ('read-time T bytes', wire)
        wire = d.call('feed', bytes='d{r:1}')[0]
        expected = (b'd:[' + warning(roms[0]) + row(0,9,1) + warning(roms[1]) +
                    b',' + row(1,5,0) + b',' + row(2,6,0) + b']\r\n')
        assert wire == expected, ('read-time d bytes', wire)
        assert normal == prefix + b',"RoomTemp": 20.00,"State":0}\r\n'
        wire = d.call('feed', bytes='td{r:1}')[0]
        readings = dict(records(wire))
        assert b'D:' not in wire and readings['T']['BeerTemp'] is None and readings['T']['FridgeTemp'] is None
        assert 'RoomTemp' not in readings['T'] and all(v['v'] is None for v in readings['d'])
        wire,_ = d.call('advance', milliseconds=1000)
        assert b'D:' not in wire, 'Read-time transitions must not be logged again by the next ordinary evaluation'
        d.call('precondition', fields={'connected':[True,True,True]})
        wire,_ = d.call('advance', milliseconds=1000)
        assert [v for p,v in records(wire) if p=='D'] == [
            dict(logType='I',logID=0,V=[18,rom]) for rom in roms]
        # The ordinary-demand capture first noticed all three losses in d.
        d.call('precondition', fields={'connected':[False,False,False]})
        wire = d.call('feed', bytes='d{r:1}')[0]
        assert wire == (b'd:[' + warning(roms[0]) + row(0,9,1) + warning(roms[1]) +
                        b',' + row(1,5,0) + warning(roms[2]) + b',' + row(2,6,0) + b']\r\n')
        following = d.call('feed', bytes='t')[0]
        assert b'D:' not in following and records(following)[0][1]['BeerTemp'] is None
    finally:
        d.close()
    return ['revc.observed_read_time_nested_loss_diagnostics_and_cached_fast_values']


def shared_loss_observation(executable, profile):
    """Observable shared-DATA loss, including required-probe shutdown during heat.

    Physical sensor values are substituted with constant synthetic 20 C inputs;
    this asserts presence, records, diagnostics, and control, not filter reseeding.
    """
    bus = 14 if profile=='i2c' else 18
    pins = (5,6,2,10) if profile=='i2c' else (6,5,2,19)
    d = Driver(executable, profile=profile)
    roms = ['28A1010000000204','28A10100000001E6','28A101000000035A']
    try:
        for heating in (False, True):
            d.call('construct', state=dict(valid=True, slots=[],scenario={'physical_loads':[]}))
            for i, function in enumerate((9,5,6)):
                d.call('feed', bytes='U{i:%d,f:%d,h:2,p:%d,a:%s}' % (i,function,bus,roms[i]))
            for i, function, pin in [(3,3,pins[0]),(4,2,pins[1]),(5,4,pins[2]),(6,7,pins[3])]:
                d.call('feed', bytes='U{i:%d,f:%d,h:1,p:%d,x:1}' % (i,function,pin))
            before = records(d.call('feed', bytes='d{r:1}')[0])[0][1]
            if heating:
                d.call('advance', milliseconds=600000)
                d.call('feed', bytes='j{mode:f,fridgeSet:23}')
                d.call('advance', milliseconds=1000)
                assert records(d.call('feed',bytes='t')[0])[0][1]['State'] == 3
                assert records(d.call('feed',bytes='d{i:4,r:1}')[0])[0][1][0]['v'] == 1
                d.call('advance',milliseconds=60000)
            d.call('precondition', fields={'connected':[False,False,False]})
            wire, _ = d.call('advance',milliseconds=1000)
            diagnostics = [r for p,r in records(wire) if p=='D']
            assert equal(diagnostics,[dict(logType='W',logID=2,V=[bus,rom]) for rom in roms])
            telemetry = records(d.call('feed',bytes='t')[0])[0][1]
            assert telemetry['State']==0 and telemetry['BeerTemp'] is None and telemetry['FridgeTemp'] is None
            assert 'RoomTemp' not in telemetry
            lost = records(d.call('feed',bytes='d{r:1}')[0])[0][1]
            assert all(row['v'] is None for row in lost[:3])
            assert all(row['v']==0 for row in lost[3:])
            assert [{k:v for k,v in r.items() if k!='v'} for r in lost] == [
                {k:v for k,v in r.items() if k!='v'} for r in before]
            wire, _ = d.call('advance',milliseconds=5000)
            assert not [r for p,r in records(wire) if p=='D']
            d.call('precondition',fields={'connected':[True,True,True]})
            wire, _ = d.call('advance',milliseconds=1000)
            diagnostics = [r for p,r in records(wire) if p=='D']
            assert equal(diagnostics,[dict(logType='I',logID=0,V=[bus,rom]) for rom in roms])
            telemetry = records(d.call('feed',bytes='t')[0])[0][1]
            assert all(telemetry[k]==20 for k in ('BeerTemp','FridgeTemp','RoomTemp'))
            assert telemetry['State']==(6 if heating else 0)
            restored = records(d.call('feed',bytes='d{r:1}')[0])[0][1]
            assert all(row['v']==0 for row in restored[3:])
            wire, _ = d.call('advance',milliseconds=3000)
            assert not [r for p,r in records(wire) if p=='D']
    finally:
        d.close()
    return [profile+'.shared_data_loss_off_and_heating_recovery']


def revc_periodic_dispatch_pause(executable):
    """The observed hourly RevC pause defers reads and skips catch-up work.

    Mandatory driver waits total at least2201 ms; the engine's existing100 ms
    clock grid releases at2300 ms. This is not an exact SPI-wire latency claim.
    """
    d=Driver(executable,profile='revc')
    try:
        d.call('construct',state={'valid':True,'slots':[],'scenario':{'physical_loads':[]}})
        for i,f,rom in [(0,9,'28A10100000001E6'),(1,5,'28A1010000000204')]:
            d.call('feed',bytes='U{i:%d,f:%d,h:2,p:18,a:%s}'%(i,f,rom))
        d.call('feed',bytes='U{i:3,f:2,h:1,p:5,x:1}')
        d.call('feed',bytes='j{Kp:0,Ki:0,Kd:0,mode:b,beerSet:20}')
        d.call('feed',bytes='R');d.call('restart')
        d.call('advance',milliseconds=3599900)
        # A direct pin write just before the reset is latched until the next
        # ordinary output evaluation; initialization must not clear it early.
        d.call('feed',bytes='d{i:3,w:1}')
        before=d.call('checkpoint')[1]['checkpoint']
        assert dict(before['pins'])[5] is False
        d.call('advance',milliseconds=100)
        assert d.call('feed',bytes='n')[0]==b'', 'RevC must defer serial dispatch during periodic display initialization'
        paused=d.call('checkpoint')[1]['checkpoint']
        assert paused['last_evaluation_ms']==before['last_evaluation_ms']
        assert d.call('advance',milliseconds=2200)[0]==b''
        assert dict(d.call('checkpoint')[1]['checkpoint']['pins'])[5] is False
        wire,_=d.call('advance',milliseconds=100)
        assert [p for p,v in records(wire)]==['N']
        after=d.call('checkpoint')[1]['checkpoint']
        assert after['last_evaluation_ms']==after['controller_ms']
        assert dict(after['pins'])[5] is True
        assert after['integral_counter']==(before['integral_counter']+1)%61
        for f in (5,9):
            old=next(v['history']['countdown'] for v in before['histories'] if v['function']==f)
            new=next(v['history']['countdown'] for v in after['histories'] if v['function']==f)
            next_count=(old-1)&255
            assert new==(3 if next_count==0 else next_count), (f,old,new)
        assert after['plant']['age_ms']==before['plant']['age_ms']+2400
        # A suspended request survives checkpoint continuation without dispatch.
        d.call('restore',snapshot=paused)
        for field,bad in [('started_ms',-1),('started_ms',3600100),('queued_hex','0Z')]:
            corrupt=json.loads(json.dumps(paused));corrupt['display_reset'][field]=bad
            try:d.call('restore',snapshot=corrupt)
            except AssertionError:pass
            else:raise AssertionError('Invalid suspended checkpoint accepted')
            assert d.call('checkpoint')[1]['checkpoint']==paused
        assert d.call('feed',bytes='c')[0]==b''
        wire,_=d.call('advance',milliseconds=2300)
        assert [p for p,v in records(wire)]==['N','C']
    finally:d.close()
    return ['revc.observed_periodic_display_pause_defers_serial_without_catchup']


def i2c_observations(executable):
    """Original assertions from recorded Uno I2C observations, never raw captures.

    Synthetic probe ROMs substitute for bench IDs in the same enumeration/role
    order. Temperatures are fixed at 20 C; uncontrolled bench temperatures and
    host delivery intervals are deliberately not numerical parity expectations.
    """
    d = Driver(executable, profile='i2c')
    checks = []
    roms = ('28A1010000000204', '28A10100000001E6', '28A101000000035A')

    def send(command):
        return records(d.call('feed', bytes=command)[0])

    def one(command, prefix):
        rows = [value for kind, value in send(command) if kind == prefix]
        assert len(rows) == 1, (command, rows)
        return rows[0]

    def fresh():
        d.call('construct', state=dict(valid=True, slots=[]))
        for index, function in enumerate((9, 5, 6)):
            row = one('U{i:%d,f:%d,h:2,p:14,a:%s}' % (index, function, roms[index]), 'U')
            assert row['p'] == 14 and row['f'] == function
        telemetry = one('t','T')
        assert all(equal(telemetry[k],20) for k in ('BeerTemp','FridgeTemp','RoomTemp'))

    def reboot():
        assert d.call('feed', bytes='R')[0] == b''
        d.call('restart')

    def diagnostics(rows):
        return [value for kind, value in rows if kind == 'D']

    try:
        fresh()
        wire, _ = d.call('feed', bytes='n')
        assert wire == b'N:{"v":"0.2.13","n":"da7e14a9","s":5,"y":0,"b":"s","l":"3"}\r\n', wire
        rows = send('h{v:1}')
        assert diagnostics(rows) == []
        inventory = next(value for kind,value in rows if kind=='h')
        assert [r['p'] for r in inventory] == [14,14,14,5,6,2,10]
        assert all('v' in r for r in inventory[:3])
        assert all('v' not in r for r in inventory[3:])
        wire, _ = d.call('feed', bytes='l')
        assert wire.count(b'\xdf') == 2 and b'\xb0' not in wire
        checks.append('i2c.identity_inventory_degree')

        rows = send('j{Kp:6,unknownBenchKey:1,Ki:0.5,Kp:7}')
        assert equal(diagnostics(rows), [dict(logType='I',logID=12,V=['Kp','6']),
            dict(logType='I',logID=12,V=['unknownBenchKey','1']),dict(logType='W',logID=0,V=[]),
            dict(logType='I',logID=12,V=['Ki','0.5']),dict(logType='I',logID=12,V=['Kp','7'])])
        constants = one('c','C')
        assert equal(constants['Kp'],7) and equal(constants['Ki'],.5)
        assert d.call('feed',bytes='j{Kp:8')[0] == b''
        rows = records(d.call('timeout')[0])
        assert equal(diagnostics(rows), [dict(logType='I',logID=12,V=['Kp','8'])])
        assert rows[-1][1]['Kp'] == 8
        rows = send('j{Kp:7,' + 'q'*30 + ':1}')
        assert equal(diagnostics(rows), [dict(logType='I',logID=12,V=['Kp','7']),
            dict(logType='I',logID=12,V=['q'*29,'7']),dict(logType='W',logID=0,V=[]),
            *[dict(logType='W',logID=1,V=[v]) for v in (58,49,125)]])
        checks.append('i2c.incremental_partial_long_key')

        send('j{Kp:6}')
        rows = send('j{Kp:+7,Ki:1e2}')
        assert equal(diagnostics(rows), [dict(logType='I',logID=12,V=['Kp','+7']),
                                        dict(logType='I',logID=12,V=['Ki','1e2'])])
        constants = one('c','C')
        assert equal(constants['Kp'],6) and equal(constants['Ki'],.5)
        send('j{maxHeatTimeForEst:70000}')
        assert one('c','C')['maxHeatTimeForEst'] == 65535
        send('j{maxHeatTimeForEst:-1}')
        assert one('c','C')['maxHeatTimeForEst'] == 65535
        send('j{beerFastFilt:257}')
        assert equal(one('c','C')['beerFastFilt'],1)
        checks.append('i2c.scalar_and_byte_conversions')

        fresh()
        before = one('d{i:0}','d')[0]
        rows = send('U{i:0,j:0.5}')
        assert equal(diagnostics(rows), [dict(logType='E',logID=7,V=[2,0,1]),dict(logType='E',logID=3,V=[])])
        assert equal([value for kind,value in rows if kind=='U'], [before])
        row = one('U{i:0,f:9,c:127,b:127,h:2,p:14,a:'+roms[0]+'}','U')
        assert equal(row['c'],1) and equal(row['b'],1) and row['a'] == roms[0]
        one('U{i:0,f:9,j:0.5}','U')
        assert equal(one('U{i:0,f:9,j:-0.0625}','U')['j'],.5)
        one('U{i:0,f:9,j:0}','U')
        checks.append('i2c.ownership_and_calibration')

        one('U{i:2,f:0}','U')
        all_rows = one('h{h:2,p:14,u:0}','h')
        assert [(r['i'],r['f']) for r in all_rows] == [(0,9),(1,5),(-1,5)]
        assert all_rows[-1]['a'] == roms[2] and all_rows[-1]['t'] == 1
        assert equal(one('h{h:2,p:14,u:-1}','h'), [dict(i=-1,t=0,c=1,b=0,f=0,h=2,d=0,p=14,a=roms[2],j=0)])
        one('U{i:2,f:6,h:2,p:14,a:'+roms[2]+'}','U')
        assert equal(one('t','T')['RoomTemp'],20)
        row = one('U{i:8,f:5,h:2,p:14,a:'+roms[0]+'}','U')
        assert row['a'] == roms[0] and row['f'] == 5
        assert sum(r['f']==5 for r in one('d{e:1}','d')) == 2
        one('U{i:8,f:0}','U')
        one('U{i:1,f:5,h:2,p:14,a:'+roms[1]+'}','U')
        one('U{i:2,f:6,h:2,p:14,a:0000000000000000}','U')
        assert 'RoomTemp' not in one('t','T')
        assert one('h{h:2,p:14}','h')[-1]['a'] == '0000000000000000'
        assert equal(one('d{i:0,r:1,w:0}','d')[0]['v'],20)
        checks.append('i2c.discovery_duplicates_zero_rom_selectors')

        fresh()
        send('j{Kp:7}');send('C')
        assert equal(one('c','C')['Kp'],5)
        reboot()
        assert equal(one('c','C')['Kp'],7)
        variables = one('v','V')
        assert all(equal(variables[k],48) for k in ('estPeak','negPeakEst','posPeakEst','negPeak','posPeak'))
        assert all(equal(variables[k],0) for k in ('beerDiff','diffIntegral','beerSlope','p','i','d'))
        send('j{mode:p,beerSet:20,heatEst:0.5}');send('S')
        assert equal(one('s','S')['heatEst'],.199)
        reboot()
        assert equal(one('s','S')['heatEst'],.5)
        send('j{mode:p,beerSet:20}');send('j{beerSet:20.25}')
        assert equal(one('s','S')['beerSet'],20.25)
        reboot()
        assert equal(one('s','S')['beerSet'],20)
        send('j{mode:p,beerSet:20}');send('j{beerSet:20.3125}')
        reboot()
        assert equal(one('s','S')['beerSet'],20.31)
        send('j{mode:o,beerSet:21}');send('j{mode:o}')
        assert equal(one('s','S')['beerSet'],21)
        reboot()
        assert one('s','S')['beerSet'] is None
        checks.append('i2c.persistence_cold_values_off_noop')

        fresh();send('j{mode:t}')
        for slot,function,pin in ((3,3,5),(4,2,6),(5,4,2),(6,7,10)):
            one('U{i:%d,f:%d,h:1,p:%d,x:1,d:0}'%(slot,function,pin),'U')
            for active in (1,0):
                assert 'v' not in one('d{i:%d,w:%d}'%(slot,active),'d')[0]
                assert equal(one('d{i:%d,r:1}'%slot,'d'),
                    [dict(i=slot,t=3,c=1,b=0,f=function,h=1,d=0,p=pin,v=active,x=1)])
        send('d{i:4,w:1}');one('U{i:4,f:0}','U');send('j{mode:o}')
        _,obs=d.call('outputs')
        assert dict(obs['pins'])[6] is False
        one('U{i:4,f:2,h:1,p:6,x:1,d:0}','U');send('d{i:4,w:0}')
        assert equal(one('d{i:4,r:1}','d')[0]['v'],0)
        checks.append('i2c.logical_outputs_and_removed_pin')

        one('U{i:7,f:1,h:1,p:4,x:1,d:0}','U')
        for opened,active in ((True,1),(False,0)):
            # Model the physical door; the observed I2C contact grounds D4 when open.
            d.call('precondition',fields={'door_open':opened})
            d.call('advance',milliseconds=1000)
            assert equal(one('d{i:7,r:1}','d'),[dict(i=7,t=2,c=1,b=0,f=1,h=1,d=0,p=4,v=active,x=1)])
            assert equal(one('d{i:5,r:1}','d'),[dict(i=5,t=3,c=1,b=0,f=4,h=1,d=0,p=2,v=active,x=1)])
            assert equal(one('t','T')['State'],0)
            assert one('l','L')[3].startswith('Door open') == bool(active)
        checks.append('i2c.door_light_and_lcd_override')

        for test_mode in (False,True):
            fresh()
            one('U{i:5,f:4,h:1,p:2,x:1,d:0}','U')
            send('j{mode:o,lah:0}');send('d{i:-2,w:0}');send('d{i:-2,w:1}')
            d.call('outputs')
            assert equal(one('d{i:5,r:1}','d')[0]['v'],1)
            if test_mode:
                send('j{mode:t}');d.call('advance',milliseconds=615000)
                assert equal(one('d{i:5,r:1}','d')[0]['v'],1)
                send('j{mode:o}');d.call('outputs')
            else:
                d.call('advance',milliseconds=590000)
                assert equal(one('d{i:5,r:1}','d')[0]['v'],1)
                d.call('advance',milliseconds=13000)
            assert equal(one('d{i:5,r:1}','d')[0]['v'],0)
        checks.append('i2c.camera_ordinary_expiry_and_test_retention')
        return checks
    finally:
        d.close()


def run(executable):
    d = Driver(executable)
    checks = []
    try:
        d.call('construct', state=dict(valid=True, slots=[]))
        for token in ['notanumber', '+1', '1e2']:
            wire, _ = d.call('feed', bytes='j{hs:' + token + ',maxCoolTimeForEst:' + token + '}')
            rows = records(wire)
            constants = rows[-1][1]
            assert constants['hs'] == 0 and constants['maxCoolTimeForEst'] == 1200
            assert all(row[1]['logType'] == 'I' for row in rows if row[0] == 'D')
        checks.append('invalid known flag/time inputs leave values unchanged without W0')
        for token, value in [('1.24', 1.24), ('-1-2', -12), ('1.2.3', 1.199), ('.5', 1.199)]:
            wire, _ = d.call('feed', bytes='j{Kp:' + token + '}')
            assert records(wire)[-1][1]['Kp'] == value, (token, wire)
        checks.append('custom scalar grammar and repeated decimal rounding')
        wire, _ = d.call('feed', bytes='j{Kp:-64,tempSetMin:-999}')
        constants = records(wire)[-1][1]
        assert constants['Kp'] == -63.996 and constants['tempSetMin'] == -16.0
        wire, _ = d.call('feed', bytes='j{beerSet:-999}')
        assert records(wire)[-2][1]['beerSet'] == -16.0
        d.call('construct', state=dict(valid=True, slots=[]))
        checks.append('numeric clipping preserves finite minimum values and reserves explicit null for disabled temperatures')
        wire, _ = d.call('feed', bytes=r'j{unknown:\x}')
        first = wire.split(b'\r\n')[0]
        assert first == b'D:{"logType":"I","logID":12,"V":["unknown","\\x"]}', first
        checks.append('raw diagnostic backslash remains unescaped, independently of local JSON')
        d.call('feed', bytes='j{beerSet:20,fridgeSet:19}')
        wire, _ = d.call('feed', bytes='s')
        assert records(wire)[0][1]['beerSet'] == 20
        d.call('feed', bytes='Rns')
        wire, _ = d.call('restart')
        assert not wire
        wire, observations = d.call('feed', bytes='s')
        assert records(wire)[0][1]['beerSet'] is None
        assert observations['store']['settings_raw']['beerSet'] == -32767
        checks.append('forced off-mode action on reload and discarded coalesced reboot bytes')
        wire, _ = d.call('feed', bytes='U{i:0,f:-2,h:0}')
        assert records(wire) == [('U', dict(i=0, t=0, c=0, b=0, f=0, h=0, d=0, p=0))]
        d.call('feed', bytes='U{i:0,f:2,h:1,p:5,x:1}')
        wire, _ = d.call('feed', bytes='U{i:0,f:2,p:6,p:-2,h:-128,x:-2,d:-2}')
        assert records(wire) == [('U', dict(i=0, t=3, c=1, b=0, f=2, h=1, d=0, p=5, x=1))]
        checks.append('all negative ordinary patches are omitted; a final negative duplicate cancels a pending update')
        wire, _ = d.call('feed', bytes='U{i:4,f:16,h:0,x:2}')
        assert records(wire)[:2] == [('D', dict(logType='E',logID=6,V=[16])), ('D',dict(logType='E',logID=3,V=[]))]
        assert records(wire)[2][0] == 'U'
        checks.append('ordinary validation failures precede any unneeded noncanonical-boolean observation')
        d.call('feed', bytes='U{i:0,f:9,h:2,p:18,a:28A10100000001E6}')
        wire, _ = d.call('feed', bytes='U{i:0,f:9,a:FF00000000000000}')
        assert records(wire)[0][1]['a'] == '28A10100000001E6'
        checks.append('FF-family ROM sentinel retains the previous address')
        d.call('feed', bytes='U{i:1,f:9,h:2,p:18,a:28A10100000001E6}')
        wire, _ = d.call('feed', bytes='U{i:1,f:9,j:-0.125}')
        assert records(wire)[0][1]['j'] == -.125
        wire, _ = d.call('feed', bytes='U{i:1,f:9,j:0.5,j:bad}')
        assert records(wire)[0][1]['j'] == .5
        wire, _ = d.call('feed', bytes='d{i:1,r:1,w:1}')
        assert records(wire)[0][1][0]['v'] == 20.5 and b'"v": 20.500' in wire
        checks.append('negative calibration applies and sensor reads still work alongside actuator-only w')
        wire, _ = d.call('feed', bytes='h{h:1,v:1}')
        assert all('v' not in row for row in records(wire)[0][1])
        wire, _ = d.call('feed', bytes='h{v:1}')
        rows = records(wire)[0][1]
        first_pin = next(row for row in rows if row['h'] == 1)
        assert first_pin['p'] == 2 and first_pin['f'] == first_pin['b'] == 0
        assert b'"v": 20.000' in wire
        checks.append('discovery values/precision and independent OneWire/digital cursor state')
        wire, _ = d.call('feed', bytes='U{i:2,f:10,h:2,p:18,a:00A101000000035A}h{h:2,u:-1}')
        assert records(wire)[-1] == ('h', [])
        wire, _ = d.call('feed', bytes='U{i:3,f:10,h:2,p:18,a:28A1}')
        assert records(wire)[0][1]['a'] == '28A1FFFFFFFFFFFF'
        wire, _ = d.call('feed', bytes='U{i:3,f:10,a:28A101000000035A,a:2812}')
        assert records(wire)[0][1]['a'] == '281201000000035A'
        wire, _ = d.call('feed', bytes='U{i:3,f:10,a:1aA101000000035A}')
        assert records(wire)[0][1]['a'] == '3AA101000000035A'
        checks.append('first-byte ROM wildcard, short/repeated address prefix writes, and bounded lowercase conversion')
        d.call('precondition', fields={'persisted_device_records': [dict(i=0,c=1,b=1,f=11,h=1,p=200,x=1,d=0)]})
        d.call('feed', bytes='R')
        d.call('restart')
        wire, _ = d.call('feed', bytes='d{i:0}')
        assert records(wire)[0][1][0]['p'] == -56
        checks.append('signed-byte device attribute output without inventing a live target')
        d.call('construct', state=dict(valid=True, slots=[]))
        wire, _ = d.call('feed', bytes='h{' + 'h:2,unknown:1,' * 10000 + 'hardware:1}')
        rows = records(wire)[0][1]
        assert [row['p'] for row in rows] == [2, 5, 6, 19]
        checks.append('long duplicate/unknown selector streams retain final fields without a command-length rejection')
        for bad in [b'N:{}', b'N:{}\n', b'N:{}\r', b'N:{}\r\n\r\n',
                    b'N:{"x":1,"x":2}\r\n', b'N:{"x":NaN}\r\n']:
            try:
                decode_frames(bad)
            except (AssertionError, ValueError):
                pass
            else:
                raise AssertionError('fixture matcher accepted malformed framing/JSON: ' + repr(bad))
        checks.append('fixture matcher rejects missing CRLF, bare LF/CR, blank frames, duplicate keys, and nonfinite numbers')
        wire, _ = d.call('feed', bytes_hex=b'j{Kp:7\0junk,Ki:1}'.hex())
        rows=records(wire)
        assert rows[0] == ('D', dict(logType='I', logID=12, V=['Kp','7']))
        assert rows[-1][1]['Kp'] == 7 and rows[-1][1]['Ki'] == 1
        wire, _ = d.call('feed', bytes_hex=b'j{Kp\0junk:8}'.hex())
        assert records(wire)[-1][1]['Kp'] == 8
        checks.append('raw NUL bytes truncate callback strings while token capacity still counts the received bytes')
        # The strict test/storage codec must reject ambiguous envelopes independently
        # of the deliberately permissive Arduino serial grammar.
        for line in ['{"op":"boot","op":"restart"}', '{"op":+1}', '{"op":"\\ud800"}', '[' * 70 + '0' + ']' * 70]:
            d.p.stdin.write(line + '\n')
            d.p.stdin.flush()
            reply = json.loads(d.p.stdout.readline())
            assert 'error' in reply
        checks.append('local codec rejects duplicate keys, invalid number, lone surrogate, and excess nesting')
        # Local JSON is UTF-8; the wire protocol deliberately remains a byte stream.
        for data in [b'\x80',b'\xc0\xaf',b'\xc2 ',b'\xe2\x82',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xf5\x80\x80\x80']:
            reply=subprocess.run([executable],input=b'{"op":"boot","unused":"'+data+b'"}\n',capture_output=True,timeout=5)
            assert reply.returncode==0 and 'error' in json.loads(reply.stdout),data
        for text in ['café','😀','\u0800','\U0010ffff']:
            request=json.dumps(dict(op='boot',unused=text),ensure_ascii=False).encode()+b'\n'
            reply=subprocess.run([executable],input=request,capture_output=True,timeout=5)
            assert reply.returncode==0 and 'error' not in json.loads(reply.stdout),text
        checks.append('local JSON rejects invalid/overlong/surrogate/out-of-range UTF-8 and accepts valid multibyte Unicode')

    finally:
        d.close()
    checks.extend(i2c_observations(executable))
    checks.extend(nested_discovery_observation(executable, 'i2c'))
    checks.extend(nested_discovery_observation(executable, 'revc'))
    checks.extend(read_time_loss_observation(executable))
    checks.extend(revc_periodic_dispatch_pause(executable))
    for profile in ('i2c','revc'):
        checks.extend(shared_loss_observation(executable, profile))
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    (out / 'protocol-edges.json').write_text(json.dumps(dict(status='passed', checks=checks), indent=2) + '\n')
    print(json.dumps(dict(status='passed', checks=checks)))


if __name__ == '__main__':
    run(sys.argv[1])
