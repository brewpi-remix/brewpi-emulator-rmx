# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original regressions for the milestone 2 clarification notes and local codec."""
import json
from pathlib import Path
import subprocess
import sys
from fixtures import Driver, decode_frames


def records(wire):
    return decode_frames(wire)


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
    finally:
        d.close()
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    (out / 'milestone2-edges.json').write_text(json.dumps(dict(status='passed', checks=checks), indent=2) + '\n')
    print(json.dumps(dict(status='passed', checks=checks)))


if __name__ == '__main__':
    run(sys.argv[1])
