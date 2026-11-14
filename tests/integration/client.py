# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original black-box clients for the separate pinned host and panel."""
import json
import socket
import time
import urllib.parse
import urllib.request
from lab import LAB, EVIDENCE
from pathlib import Path


class Client:
    def post(self, message_type, message=''):
        data = urllib.parse.urlencode(dict(messageType=message_type, message=message)).encode()
        with urllib.request.urlopen('http://127.0.0.1:8080/socketmessage.php', data, timeout=20) as reply:
            result = reply.read().decode()
        with (EVIDENCE/'http.jsonl').open('a') as log:
            log.write(json.dumps(dict(type=message_type, message=message, response=result))+'\n')
        return result

    def get(self, message_type):
        return json.loads(self.post(message_type))

    def until(self, fn, timeout=30):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = fn()
                if last:
                    return last
            except (OSError, ValueError, KeyError) as exc:
                last = repr(exc)
            # Allow the host's 0.5 s socket timeout to service queued serial data.
            time.sleep(.7)
        raise AssertionError(f'client condition timed out: {last!r}')

    def devices(self):
        self.post('refreshDeviceList', 'readValues')
        def updated():
            text = self.post('getDeviceList')
            return json.loads(text) if text.startswith('{') else False
        return self.until(updated)['deviceList']

    def socket_send(self, message):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(5)
            conn.connect(str(LAB/'host/BEERSOCKET'))
            conn.sendall(message.encode())
            conn.shutdown(socket.SHUT_WR)
            # Mutation commands have no application acknowledgment.
            while conn.recv(65536):
                pass
        time.sleep(.7)

    def store(self):
        return json.loads((LAB/'controller.json').read_text())


def maintenance(page, tab):
    if not page.locator('#maintenance-panel').is_visible():
        page.click('#maintenance')
    page.locator(f"#maintenance-panel a[href='#{tab}']").click()


def close_maintenance(page):
    if page.locator('#maintenance-panel').is_visible():
        page.locator('.ui-dialog').filter(has=page.locator('#maintenance-panel')).locator('.ui-dialog-titlebar-close').click()


def assign_all(page, client):
    maintenance(page, 'device-config')
    page.locator('#read-values').check()
    page.click('.refresh-device-list')
    page.wait_for_selector('.device-container', timeout=15000)
    mapping = [('28A10100000001E6',0,9), ('28A1010000000204',1,5),
               ('28A101000000035A',2,6), ('5(Act2)',3,2), ('6(Act1)',4,3),
               ('2(Act3)',5,4), ('A5(Act4)',6,7)]
    for identity, slot, function in mapping:
        row = page.locator('.device-container').filter(has=page.get_by_text(identity, exact=True))
        row.locator('.device-slot select').select_option(str(slot))
        row.locator('.chamber select').select_option('1')
        row.locator('.beer select').select_option('1' if function==9 else '0')
        row.locator('.function select').select_option(str(function))
        if row.locator('.pin-type select').count():
            row.locator('.pin-type select').select_option('1')
        row.locator('button.apply').click()
        client.until(lambda: client.store()['devices'][slot]['f']==function)
        page.wait_for_timeout(1400)
    devices = client.devices()
    expected=json.loads(Path('/work/engineering/protocol/test-vectors/defaults-v1.json').read_text())['all_assigned_slots']
    validate_devices(devices,expected)
    return devices


def set_mode(page, client, mode, target=None):
    close_maintenance(page)
    anchor = {'b':'beer-constant-control','f':'fridge-constant-control','o':'temp-control-off','p':'profile-control'}[mode]
    page.locator(f"#control-panel a[href='#{anchor}']").click()
    if target is not None:
        page.locator('#beer-temp input' if mode=='b' else '#fridge-temp input').fill(str(target))
    page.click('#apply-settings')
    def accepted():
        settings = client.get('getControlSettings')
        key = 'beerSet' if mode=='b' else 'fridgeSet'
        accepted = settings['mode']==mode and (target is None or (settings[key] is not None and abs(settings[key]-target)<.02))
        # Do not count the host's optimistic cache mutation as controller acceptance.
        saved = client.store()['settings_raw']
        accepted = accepted and saved['mode']==ord(mode)
        if target is not None:
            accepted = accepted and saved[key]==round((target-48)*512)
        if mode=='o':
            accepted = accepted and settings['beerSet'] is None and settings['fridgeSet'] is None
        return settings if accepted else False
    return client.until(accepted)


def validate_devices(devices, expected):
    assert not devices['available'] and len(devices['installed'])==len(expected),devices
    actual={row['i']:row for row in devices['installed']}
    assert len(actual)==len(expected),devices
    for row in expected:
        assert all(actual[row['i']].get(key)==value for key,value in row.items()),(row,actual)
