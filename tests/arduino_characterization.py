# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Opt-in physical Uno I2C characterization; never part of normal validation.

Original experiments from the interoperability specification, not reference code.
Raw device captures remain external evidence, not MIT fixture inputs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import signal
import sys
import time


def frames(raw, prefix):
    values = []
    for line in raw.splitlines():
        if line.startswith(prefix.encode() + b':'):
            try:
                values.append(json.loads(line[2:].decode('cp437')))
            except (ValueError, UnicodeError):
                pass
    return values


class Bench:
    def __init__(self, serial, directory):
        self.serial = serial
        self.directory = directory
        self.trace = (directory / 'wire.jsonl').open('x')
        self.checks = []
        self.counter = 0

    def log(self, item):
        self.trace.write(json.dumps(item) + '\n')
        self.trace.flush()

    def collect(self, seconds):
        end = time.monotonic() + seconds
        raw = bytearray()
        while time.monotonic() < end:
            data = self.serial.read(max(1, self.serial.in_waiting))
            if data:
                raw.extend(data)
                self.log({'event': 'rx', 'monotonic': time.monotonic(), 'hex': data.hex()})
        return bytes(raw)

    def query(self, command, prefix=None, timeout=8, settle=.25):
        data = command.encode('ascii')
        self.counter += 1
        start = time.monotonic()
        self.log({'event': 'tx', 'id': self.counter, 'monotonic': start, 'hex': data.hex()})
        self.serial.write(data)
        self.serial.flush()
        raw = bytearray()
        first = None
        last = start
        while time.monotonic() - start < timeout:
            chunk = self.serial.read(max(1, self.serial.in_waiting))
            now = time.monotonic()
            if chunk:
                first = first if first is not None else now - start
                last = now
                raw.extend(chunk)
                self.log({'event': 'rx', 'id': self.counter, 'monotonic': now, 'hex': chunk.hex()})
            complete = frames(raw, prefix) if prefix else bool(raw and raw.endswith(b'\r\n'))
            if complete and now - last >= settle:
                break
        result = bytes(raw)
        self.log({'event': 'exchange', 'id': self.counter, 'command': command,
                  'first_byte_seconds': first, 'duration_seconds': time.monotonic() - start,
                  'hex': result.hex()})
        return result

    def read(self, command, prefix):
        raw = self.query(command, prefix)
        rows = frames(raw, prefix)
        if not rows:
            raise RuntimeError('No complete ' + prefix + ' reply to ' + command)
        return rows[-1]

    def change(self, text):
        return self.query('j{' + text + '}', 'C')

    def assign(self, record):
        keys = ('i', 'f', 'h', 'p', 'a', 'x', 'd', 'j')
        text = ','.join(str(k) + ':' + str(record[k]) for k in keys if k in record)
        return self.read('U{' + text + '}', 'U')

    def reboot(self):
        self.query('R', timeout=1)
        self.collect(10)
        return self.read('n', 'N')

    def record(self, name, passed, observed):
        result = {'case': name, 'status': 'confirmed' if passed else 'different_or_inconclusive',
                  'observed': observed}
        self.checks.append(result)
        (self.directory / 'checks.json').write_text(json.dumps(self.checks, indent=2) + '\n')
        print(json.dumps(result), flush=True)


def run(bench, baseline):
    b = bench
    probes = baseline['devices']
    identity = baseline['identity']
    b.record('i2c_identity', identity.get('s') == 5, identity)
    inventory = b.read('h{v:1}', 'h')
    pins = [r['p'] for r in inventory if r.get('h') == 1]
    b.record('i2c_output_inventory', pins == [5, 6, 2, 10], pins)
    raw = b.query('l', 'L')
    b.record('lcd_raw_degree_byte', b'\xb0' in raw, {'hex': raw.hex()})

    raw = b.change('Kp:6,unknownBenchKey:1,Ki:0.5,Kp:7')
    c = frames(raw, 'C')[-1]
    b.record('incremental_unknown_and_duplicate_keys', c['Kp'] == 7 and c['Ki'] == .5,
             {'constants': c, 'diagnostics': frames(raw, 'D')})
    raw = b.query('j{Kp:8', 'C')
    b.record('partial_pair_applied_after_timeout', frames(raw, 'C')[-1]['Kp'] == 8,
             {'diagnostics': frames(raw, 'D')})
    raw = b.query('j{Kp:7,' + 'q' * 30 + ':1}', 'C')
    diag = frames(raw, 'D')
    b.record('long_key_reuses_previous_value', any(d.get('V') == ['q' * 29, '7'] for d in diag), diag)
    b.change('Kp:6')
    raw = b.change('Kp:+7,Ki:1e2')
    c = frames(raw, 'C')[-1]
    b.record('plus_and_exponent_conversion_rejected', c['Kp'] == 6 and c['Ki'] == .5,
             {'Kp': c['Kp'], 'Ki': c['Ki'], 'diagnostics': frames(raw, 'D')})
    b.change('maxHeatTimeForEst:70000')
    high = b.read('c', 'C')['maxHeatTimeForEst']
    b.change('maxHeatTimeForEst:-1')
    negative = b.read('c', 'C')['maxHeatTimeForEst']
    b.record('unsigned_time_clip_and_negative_ignore', high == 65535 and negative == high,
             {'oversize': high, 'after_negative': negative})
    b.change('beerFastFilt:257')
    filt = b.read('c', 'C')['beerFastFilt']
    b.record('filter_index_byte_wrap', filt == 1, filt)

    beer = next(r for r in probes if r['f'] == 9)
    room = next(r for r in probes if r['f'] == 6)
    chamber = next(r for r in probes if r['f'] == 5)
    raw = b.query('U{i:%d,j:0.5}' % beer['i'], 'U')
    b.record('beer_patch_without_function', [d.get('logID') for d in frames(raw, 'D')
             if d.get('logType') == 'E'] == [7, 3],
             {'diagnostics': frames(raw, 'D'), 'result': frames(raw, 'U')})
    raw = b.query('U{i:%d,f:9,c:127,b:127,h:2,p:14,a:%s}' % (beer['i'], beer['a']), 'U')
    record = frames(raw, 'U')[-1]
    b.record('forced_ownership', record['c'] == 1 and record['b'] == 1, record)
    b.assign(dict(beer, j=.5))
    raw = b.query('U{i:%d,f:9,j:-0.0625}' % beer['i'], 'U')
    record = frames(raw, 'U')[-1]
    b.record('calibration_minus_one_sentinel', record['j'] == .5, record)
    b.assign(beer)
    b.assign({'i': room['i'], 'f': 0})
    inventory = b.read('h{h:2,p:14,u:0}', 'h')
    unassigned = next(r for r in inventory if r['a'] == room['a'])
    unused = b.read('h{h:2,p:14,u:-1}', 'h')
    b.record('discovery_assigned_field_leak', unassigned['i'] == -1 and unassigned['f'] != 0,
             {'all': inventory, 'unused': unused})
    b.assign(room)
    duplicate = dict(chamber, i=8, a=beer['a'])
    raw = b.assign(duplicate)
    slots = b.read('d{e:1}', 'd')
    b.record('duplicate_rom_and_function_accepted', raw.get('a') == beer['a'] and
             sum(r.get('f') == 5 for r in slots) == 2, slots)
    b.assign({'i': 8, 'f': 0})
    b.assign(chamber)
    b.assign(dict(room, a='0000000000000000'))
    telemetry = b.read('t', 'T')
    discovery = b.read('h{h:2,p:14}', 'h')
    b.record('zero_rom_is_not_first_live_probe', 'RoomTemp' not in telemetry,
             {'telemetry': telemetry, 'discovery': discovery})
    b.assign(room)
    raw = b.query('d{i:%d,r:1,w:0}' % beer['i'], 'd')
    row = frames(raw, 'd')[-1][0]
    b.record('sensor_read_with_write_selector', 'v' in row and row['a'] == beer['a'], row)
    b.query('d{i:-2,w:0}', 'd')

    b.change('Kp:7')
    b.query('C', 'C')
    volatile = b.read('c', 'C')['Kp']
    b.reboot()
    saved = b.read('c', 'C')['Kp']
    b.record('constant_defaults_are_volatile', volatile == 5 and saved == 7,
             {'after_C': volatile, 'after_restart': saved})
    v = b.read('v', 'V')
    b.record('cold_start_peak_48', all(v.get(k) == 48 for k in ('estPeak', 'negPeakEst', 'posPeakEst', 'negPeak', 'posPeak')), v)
    b.change('mode:p,beerSet:20,heatEst:0.5')
    b.query('S', 'S')
    live = b.read('s', 'S')
    b.reboot()
    saved = b.read('s', 'S')
    b.record('settings_reset_saves_intermediate_snapshot', live['heatEst'] != saved['heatEst'] and saved['heatEst'] == .5,
             {'live': live, 'after_restart': saved})
    b.change('mode:p,beerSet:20')
    b.change('beerSet:20.25')
    live = b.read('s', 'S')
    b.reboot()
    saved = b.read('s', 'S')
    b.record('profile_exact_quarter_not_saved', live['beerSet'] == 20.25 and saved['beerSet'] == 20,
             {'live': live, 'after_restart': saved})
    b.change('mode:p,beerSet:20')
    b.change('beerSet:20.3125')
    b.reboot()
    saved = b.read('s', 'S')
    b.record('profile_above_quarter_saved', abs(saved['beerSet'] - 20.3125) < .011, saved)
    b.change('mode:o,beerSet:21')
    b.change('mode:o')
    live = b.read('s', 'S')
    b.reboot()
    saved = b.read('s', 'S')
    b.record('off_mode_noop_vs_restart', live['beerSet'] == 21 and saved['beerSet'] is None,
             {'live': live, 'after_restart': saved})

    b.change('mode:t')
    outputs = [dict(i=3, f=3, h=1, p=5, x=1, d=0),
               dict(i=4, f=2, h=1, p=6, x=1, d=0),
               dict(i=5, f=4, h=1, p=2, x=1, d=0),
               dict(i=6, f=7, h=1, p=10, x=1, d=0)]
    for output in outputs:
        b.assign(output)
        index = output['i']
        b.query('d{i:%d,w:1}' % index, 'd')
        active = b.read('d{i:%d,r:1}' % index, 'd')
        b.query('d{i:%d,w:0}' % index, 'd')
        inactive = b.read('d{i:%d,r:1}' % index, 'd')
        b.record('logical_output_pin_%d' % output['p'], active[0].get('v') == 1 and inactive[0].get('v') == 0,
                 {'on': active, 'off': inactive, 'physical_pin_observation': False})
    b.assign(dict(i=8, f=2, h=1, p=2, x=1, d=0))
    before = b.read('d{e:1,r:1}', 'd')
    b.query('d{i:8,w:0}', 'd')
    b.assign(dict(i=8, f=0))
    after = b.read('d{e:1,r:1}', 'd')
    b.record('duplicate_output_function_removal', sum(r.get('f') == 2 for r in before) == 2,
             {'before': before, 'after': after, 'physical_pin_observation': False})
    # Reinstall and explicitly deactivate every touched output before restoration.
    for output in outputs:
        b.assign(output)
        b.query('d{i:%d,w:0}' % output['i'], 'd')
    b.change('mode:o')


def restore(b, baseline):
    b.query('E', timeout=8)
    b.collect(3)
    # Short writes avoid overrunning the Uno's small receive buffer during EEPROM writes.
    for key, value in baseline['constants'].items():
        b.change(key + ':' + str(value))
    settings = baseline['settings']
    b.change('mode:o,heatEst:%s,coolEst:%s' % (settings['heatEst'], settings['coolEst']))
    target = baseline['devices'] + [
        dict(i=3, f=3, h=1, p=5, x=1, d=0),
        dict(i=4, f=2, h=1, p=6, x=1, d=0),
        dict(i=5, f=4, h=1, p=2, x=1, d=0),
        dict(i=6, f=7, h=1, p=10, x=1, d=0),
        dict(i=7, f=1, h=1, p=4, x=1, d=0),
    ]
    for row in target:
        b.assign(row)
    b.change('mode:t')
    for row in target:
        if row['f'] in (2, 3, 4, 7):
            b.query('d{i:%d,w:0}' % row['i'], 'd')
    b.change('mode:o')
    b.reboot()
    actual = b.read('d{e:1,r:1}', 'd')
    actual = [row for row in actual if row['f'] != 0]
    c = b.read('c', 'C')
    s = b.read('s', 'S')
    t = b.read('t', 'T')
    b.query('l', 'L')
    keys = ('i', 'f', 'h', 'p', 'a', 'x', 'd', 'j')
    good = len(actual) == len(target) and all(
        any(all(observed.get(k) == wanted[k] for k in keys if k in wanted)
            for observed in actual) for wanted in target)
    constants_ok = c == baseline['constants']
    settings_ok = s == settings
    b.record('final_restoration', good and constants_ok and settings_ok and
             all(k in t and t[k] is not None for k in ('BeerTemp', 'FridgeTemp', 'RoomTemp')),
             {'devices': actual, 'constants': c, 'settings': s, 'telemetry': t,
              'constants_match': constants_ok, 'settings_match': settings_ok})
    if not (good and constants_ok and settings_ok):
        raise RuntimeError('Restoration differs from baseline plus authorized I/O assignments')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='Explicit physical Uno serial path')
    parser.add_argument('--output', required=True, type=Path, help='New external evidence directory')
    parser.add_argument('--authorize-hardware', action='store_true', required=True,
                        help='Authorize mutations, resets, output toggles, and final I/O assignments')
    args = parser.parse_args()
    import serial
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'python': platform.python_version(), 'pyserial': serial.__version__,
              'port': args.port, 'baud': 57600, 'status': 'starting'}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))
    with serial.Serial(args.port, 57600, timeout=.02, exclusive=True) as connection:
        b = Bench(connection, args.output)
        b.collect(10)
        baseline = {'identity': b.read('n', 'N'), 'settings': b.read('s', 'S'),
                    'constants': b.read('c', 'C'), 'devices': b.read('d{e:1}', 'd')}
        baseline['all_slots'] = baseline['devices']
        baseline['devices'] = [row for row in baseline['devices'] if row['f'] != 0]
        (args.output / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n')
        if (baseline['identity'].get('s') != 5 or baseline['settings']['mode'] != 'o' or
                baseline['settings']['beerSet'] is not None or
                baseline['settings']['fridgeSet'] is not None):
            raise RuntimeError('Requires I2C build with control off and null targets')
        expected = {(0, 9), (1, 5), (2, 6)}
        actual = {(r['i'], r['f']) for r in baseline['devices']}
        valid_probes = all(r.get('h') == 2 and r.get('p') == 14 and r.get('d') == 0
                           and len(r.get('a', '')) == 16 and r.get('a') != '0' * 16
                           for r in baseline['devices'])
        distinct_roms = len({r.get('a') for r in baseline['devices']}) == 3
        if (actual != expected or not valid_probes or not distinct_roms or
                baseline['constants']['tempFormat'] != 'C'):
            raise RuntimeError('Requires three active A0 probes: slots 0 beer, 1 chamber, 2 ambient, in C')
        try:
            run(b, baseline)
            report['status'] = 'completed'
        except BaseException as error:
            report['status'] = 'interrupted'
            report['error'] = repr(error)
            print('EXPERIMENT ERROR: ' + repr(error), flush=True)
        finally:
            try:
                restore(b, baseline)
                report['restored'] = True
            except BaseException as error:
                report['restored'] = False
                report['restore_error'] = repr(error)
                print('RESTORE ERROR: ' + repr(error), flush=True)
            b.trace.close()
            report['checks'] = b.checks
            report['wire_sha256'] = hashlib.sha256((args.output / 'wire.jsonl').read_bytes()).hexdigest()
            (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        return 0 if report['status'] == 'completed' and report['restored'] else 1


if __name__ == '__main__':
    sys.exit(main())
