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
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    (out / 'protocol-edges.json').write_text(json.dumps(dict(status='passed', checks=checks), indent=2) + '\n')
    print(json.dumps(dict(status='passed', checks=checks)))


if __name__ == '__main__':
    run(sys.argv[1])
