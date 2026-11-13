# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Execute reviewed specification data through a separately built C++ engine.

State construction is test-only; expected output never seeds the engine. No
reference implementation or reference test helper is imported or executed.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'engineering/protocol/test-vectors'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def strict_json(text):
    def invalid_constant(value):
        raise ValueError('non-JSON constant: ' + value)
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def load(name):
    return strict_json((DATA / name).read_text())


def decode_frames(wire):
    if not wire:
        return []
    assert wire.endswith(b'\r\n'), ('unterminated stream', wire)
    frames = wire[:-2].split(b'\r\n')
    result = []
    for line in frames:
        assert len(line) > 2 and line[1:2] == b':', ('bad framing', line)
        assert b'\r' not in line and b'\n' not in line, ('non-CRLF framing', line)
        result.append((chr(line[0]), strict_json(line[2:].decode('cp437'))))
    return result


def equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if type(a) is not type(b) and not (isinstance(a, (float, int)) and isinstance(b, (float, int))):
        return False
    if isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], v) for k, v in b.items())
    if isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    return a == b


def contains(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and contains(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        cursor = iter(actual)
        return all(any(contains(x, v) for x in cursor) for v in expected)
    return equal(actual, expected)


class Driver:
    def __init__(self, executable):
        self.p = subprocess.Popen([executable], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def call(self, op, **args):
        self.p.stdin.write(json.dumps(dict(op=op, **args)) + '\n')
        self.p.stdin.flush()
        # CTest's bounded test timeout also guards failures in the local driver.
        response = json.loads(self.p.stdout.readline())
        if 'error' in response:
            raise AssertionError(response['error'])
        return bytes.fromhex(response['hex']), response['observations']

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=5)
        assert self.p.returncode == 0


def run(executable):
    artifacts = {name: load(name) for name in ['defaults-v1.json', 'protocol-v1.json', 'diagnostics-v1.json']}
    for artifact in artifacts.values():
        assert artifact['schema_version'] == 1 and artifact['spdx_license_identifier'] == 'MIT'
    expected_formats = {
        'defaults-v1.json': 'brewpi-emulator-milestone-1-defaults-v1',
        'protocol-v1.json': 'brewpi-emulator-milestone-1-protocol-v1',
        'diagnostics-v1.json': 'brewpi-emulator-milestone-1-diagnostic-metadata-v1',
    }
    for name, artifact in artifacts.items():
        assert artifact['format'] == expected_formats[name], 'unsupported fixture format'
        assert artifact['reference_firmware_revision'] == '8f1fa1213cbbfc1f987fada5168d01925e1a2ee8'
        assert artifact['reference_host_revision'] == 'd183fb5319b928f78b4c0eb6f05fe3620610ffff'
        assert artifact['reference_panel_revision'] == 'f79631830a99575e250403f08a19be8bf944596c'
    defaults = artifacts['defaults-v1.json']
    cases = artifacts['protocol-v1.json']['cases']
    signatures = {(x['log_type'], x['log_id']): x['argument_types'] for x in artifacts['diagnostics-v1.json']['records']}

    def pointer(ref):
        filename, path = ref.split('#')
        result = artifacts[filename]
        for key in path.split('/')[1:]:
            result = result[int(key)] if isinstance(result, list) else result[key.replace('~1', '/').replace('~0', '~')]
        return result

    def preset(name):
        spec = defaults['presets'][name]
        result = preset(spec['extends']) if 'extends' in spec else {}
        return result | spec

    assert len({c['id'] for c in cases}) == len(cases), 'duplicate case ID'
    report = []
    for case in cases:
        cid = case['id']
        assert case['initial_preset'] in defaults['presets'], 'unknown preset'
        if case['classification'] == 'requires_reference_trace':
            assert case['expected_exact_output'] is None and case['counts_as_pass'] is False
            assert case['required_evidence']
            if cid == 'U_before_E':
                assert preset(case['initial_preset'])['eeprom'] == 'all_FF'
            if cid == 'duplicate_function_remove_history':
                assert preset(case['initial_preset'])['slots'] == 'assigned_slots'
            report.append(dict(id=cid, status='unresolved_reference_characterization'))
            continue
        assert case['classification'] == 'source_defined', 'unsupported case classification'
        driver = Driver(executable)
        try:
            spec = preset(case['initial_preset'])
            assert spec['eeprom'] in ('all_FF', 'valid_version_4_factory'), 'unsupported store preset'
            slots = spec['slots']
            if isinstance(slots, str):
                slots = [] if slots == 'not_initialized' else defaults[slots]
            # Raw facts seed state; rounded wire readbacks are only expectations.
            raw = defaults['raw_defaults']
            def raw_fields(values):
                result = {}
                for key, value in values.items():
                    if isinstance(value, str):
                        result[key] = ord(value)
                    elif value is None:
                        result[key] = -32767
                    elif key in raw:
                        result[key] = raw[key]
                    else:
                        result[key] = value
                return result
            settings = raw_fields(defaults[spec['settings']])
            if 'live_and_saved_settings' in spec:
                for key, value in spec['live_and_saved_settings'].items():
                    if key == 'mode':
                        settings[key] = ord(value)
                    elif key in ('beerSet', 'fridgeSet'):
                        settings[key] = -32767 if value is None else round((value - 48) * 512)
                    else:
                        assert value == defaults[spec['settings']][key], 'unsupported nondefault estimate seed'
            assert all(v == 20 for v in defaults['external_scenario']['initial_temperatures_c'].values())
            conditions = defaults[spec['controller_preconditions']]
            # The milestone 2 engine has no advancing controller clock/history.
            for key in ('controller_seconds', 'controller_millis', 'last_idle_seconds',
                        'last_heat_seconds', 'last_cool_seconds', 'wait_seconds',
                        'integral_evaluation_count', 'camera_last_active_seconds'):
                assert conditions[key] == 0, 'nonzero preset clock/history requires explicit construction'
            for key in ('positive_peak_pending', 'negative_peak_pending', 'door_open',
                        'alarm_active', 'camera_request_active', 'fallback_actuator_active'):
                assert conditions[key] is False, 'nondefault latch/history requires explicit construction'
            assert conditions['ordinary_loop_ticks_suspended'] is True
            assert spec['controller_state'] == 0
            if 'probe_filters' in spec:
                filters = spec['probe_filters']
                assert all(filters[k] == 20 for k in ('beer_fast_c', 'beer_slow_c', 'chamber_fast_c', 'chamber_slow_c'))
                assert filters['beer_slope_raw'] == filters['chamber_slope_raw'] == 0
                assert filters['sensor_update_counters'] == 255
            if 'physical_temperatures_c' in spec:
                assert spec['physical_temperatures_c'] == [20, 20, 20]
            if 'last_saved_beer_target_c' in spec:
                assert round((spec['last_saved_beer_target_c'] - 48) * 512) == settings['beerSet']
            state = dict(valid=spec['eeprom'] != 'all_FF', slots=slots,
                         settings_raw=settings,
                         constants_raw=raw_fields(defaults[spec['constants']]),
                         variables_raw=defaults[conditions['variables_raw']])
            wire, _ = driver.call('construct', state=state)
            assert not wire, ('preset produced unsolicited output', wire)
            for step in case['steps']:
                action = step['action']
                if action == 'serial_write':
                    wire = b''
                    for chunk in step['chunks_hex']:
                        out, observations = driver.call('feed', bytes_hex=chunk)
                        wire += out
                elif action == 'allow_serial_read_timeout':
                    wire, observations = driver.call('timeout')
                elif action == 'controller_boot':
                    wire, observations = driver.call('boot')
                elif action == 'await_controller_restart':
                    wire, observations = driver.call('restart')
                elif action == 'set_fixture_precondition':
                    wire, observations = driver.call('precondition', fields=step['values'])
                elif action in ('controller_pid_evaluation','controller_state_update','controller_output_update'):
                    op={'controller_pid_evaluation':'pid','controller_state_update':'state','controller_output_update':'outputs'}[action]
                    wire, observations=driver.call(op, repeat=step.get('repeat',1))
                else:
                    raise AssertionError('unclassified action: ' + action)
                expected = step.get('expected', {})
                if 'raw_hex' in expected:
                    assert wire == bytes.fromhex(expected['raw_hex']), ('raw stream mismatch', wire)
                    continue
                if 'output_before_read_timeout' in expected:
                    assert not wire, ('premature partial-token result', wire)
                    continue
                replies, diagnostics, order = [], [], []
                for prefix, value in decode_frames(wire):
                    if prefix == 'D':
                        sig = signatures[value['logType'], value['logID']]
                        assert len(sig) == len(value['V'])
                        for typ, arg in zip(sig, value['V']):
                            assert type(arg) is {'integer': int, 'string': str}[typ]
                        diagnostics.append(value)
                        order.append('D:' + value['logType'] + str(value['logID']))
                    else:
                        replies.append((prefix, value))
                        order.append(prefix)
                assert equal(diagnostics, expected.get('diagnostics', [])), ('diagnostics', diagnostics, expected)
                expected_replies = expected.get('replies', [])
                assert len(replies) == len(expected_replies), ('reply count', replies, expected)
                for (prefix, value), want in zip(replies, expected_replies):
                    assert prefix == want['prefix']
                    if 'payload_contains' in want:
                        assert contains(value, want['payload_contains']), ('projection', value, want)
                    else:
                        payload = pointer(want['payload_ref']) if 'payload_ref' in want else want['payload_equals']
                        assert equal(value, payload), ('payload', value, payload)
                if 'output_order' in expected:
                    assert order == expected['output_order'], ('order', order, expected['output_order'])
                if 'postconditions' in expected:
                    assert contains(observations, expected['postconditions']), ('postconditions', observations, expected)
                semantic={k:v for k,v in expected.items() if k not in ('replies','diagnostics','postconditions','additional_output','output_order')}
                assert contains(observations,semantic), ('semantic observations',observations,semantic)
            report.append(dict(id=cid, status='passed'))
        except Exception as exc:
            report.append(dict(id=cid, status='failed', reason=str(exc)))
            print('FAIL', cid, str(exc), file=sys.stderr)
        finally:
            driver.close()
    from collections import Counter
    counts = dict(Counter(x['status'] for x in report))
    out = Path('test-results')
    out.mkdir(exist_ok=True)
    (out / 'milestone3-fixtures.json').write_text(json.dumps(dict(counts=counts, cases=report), indent=2) + '\n')
    print(json.dumps(counts))
    assert counts.get('failed', 0) == 0
    assert counts['passed'] == 48 and counts.get('deferred_milestone_3',0) == 0
    assert counts['unresolved_reference_characterization'] == 9


if __name__ == '__main__':
    run(sys.argv[1])
