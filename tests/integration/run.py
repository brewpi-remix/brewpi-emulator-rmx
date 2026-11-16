# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Execute external-client integration against separate, pinned, unmodified host/panel clients."""
import csv
import datetime as dt
import json
from pathlib import Path
import time
import traceback
import signal
import relay_trace
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright
from lab import Lab, LAB, EVIDENCE, wait_until
from client import Client, maintenance, close_maintenance, assign_all, set_mode


class Run:
    def __init__(self):
        self.lab = Lab()
        self.client = Client()
        self.results = []
        self.errors = []
        self.page = None

    def record(self, name, interface, evidence):
        self.results.append(dict(name=name,interface=interface,status='passed',evidence=evidence))
        print(json.dumps(self.results[-1]),flush=True)
        self.save('running')

    def save(self, status, error=None):
        EVIDENCE.mkdir(exist_ok=True)
        (EVIDENCE/'integration-results.json').write_text(json.dumps(dict(
            status=status,workflows=self.results,browser_errors=self.errors,error=error),indent=2)+'\n')

    @staticmethod
    def wire(direction, session=None):
        return relay_trace.wire(EVIDENCE/'wire.jsonl',direction,session)

    def frames(self, prefix, session=None):
        return relay_trace.frames(EVIDENCE/'wire.jsonl',prefix,session)

    def change_parameter_ui(self, name, value):
        maintenance(self.page,'advanced-settings')
        field=self.page.locator(f'#control-constants-container [name="{name}"]')
        if field.evaluate('(element) => element.tagName')=='SELECT':
            field.select_option(str(value))
        else:
            field.fill(str(value))
        field.locator('..').locator('button.send-button').click()
        return self.client.until(lambda: self.client.get('getControlConstants')[name]==value)

    def execute(self):
        self.lab.prepare()
        self.lab.start_emulator()
        self.lab.start_host()
        self.lab.start_panel()
        self.client.until(lambda: self.client.get('getVersion').get('version')=='0.2.13')
        self.client.until(lambda: self.client.get('getControlConstants')['Kp']==5)
        startup=self.wire('host')
        assert startup.startswith(b'ns\nc\nv\n'),startup[:40]
        assert not (LAB/'controller.json').exists()
        self.record('startup','real host / captured serial',dict(sequence='n,s,c,v',erased_store=True))
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            self.page=browser.new_page(viewport={'width':1440,'height':1200})
            self.page.on('pageerror',lambda error:self.errors.append(str(error)))
            self.page.goto('http://127.0.0.1:8080',wait_until='domcontentloaded')
            self.page.wait_for_selector('#maintenance')
            self.client.until(lambda: 'Mode' in self.client.get('lcd')[0])
            maintenance(self.page,'advanced-settings')
            self.page.click('.reset-controller-button')
            wait_until(lambda:(LAB/'controller.json').exists(),message='panel E initialization')
            assert self.client.store()['controller_version']==4
            self.record('factory initialization','browser button → PHP → host → serial',dict(command='E'))
            devices=assign_all(self.page,self.client)
            self.record('discovery and assignment','browser controls → PHP → host → serial',devices)
            for mode,target in [('b',22),('f',24),('o',None)]:
                self.record('mode '+mode,'browser control panel',set_mode(self.page,self.client,mode,target))
            self.client.post('refreshControlVariables')
            variables=self.client.get('getControlVariables')
            assert set(['p','i','d','beerSlope','diffIntegral']).issubset(variables)
            # Source L bytes and the host's rendered representation are separate assertions.
            self.client.until(lambda: len(self.frames('L'))>1)
            for rows in self.frames('L'):
                assert all(len(row)==20 for row in rows)
                assert all(row[18]=='\u2591' for row in rows[1:3])
            seen=set()
            deadline=time.monotonic()+22
            while time.monotonic()<deadline and len(seen)<2:
                line=self.client.get('lcd')[2]
                seen.add(line[:6].strip())
                time.sleep(1)
            assert {'Room','Fridge'}.issubset(seen),seen
            self.record('LCD bytes and alternation','captured serial / host LCD endpoint',dict(width=20,degree_hex='B0',seen=sorted(seen)))
            celsius=self.client.devices()['installed'][:3]
            self.change_parameter_ui('tempFormat','F')
            self.client.until(lambda: 'F' in self.client.get('lcd')[1][-1:])
            assert self.client.store()['constants_raw']['tempFormat']==ord('F')
            fahrenheit=self.client.devices()['installed'][:3]
            for c,f in zip(celsius,fahrenheit):
                assert c['i']==f['i'] and abs(f['v']-(c['v']*1.8+32))<.15,(c,f)
            self.change_parameter_ui('tempFormat','C')
            roundtrip=self.client.devices()['installed'][:3]
            for c,r in zip(celsius,roundtrip):
                assert abs(c['v']-r['v'])<.1,(c,r)
            assert self.client.store()['constants_raw']['tempFormat']==ord('C')
            self.record('temperature units','browser maintenance controls',dict(round_trip='C→F→C',saved=True,
                celsius=celsius,fahrenheit=fahrenheit,restored=roundtrip))
            # C is volatile. S stores through its off-mode transition before replacing estimators.
            self.change_parameter_ui('Kp',7)
            self.page.locator('.cc.load-defaults').click()
            self.client.until(lambda:self.client.get('getControlConstants')['Kp']==5)
            assert self.client.store()['constants_raw']['Kp']==3584
            close_maintenance(self.page)
            set_mode(self.page,self.client,'b',22)
            self.client.post('setParameters',json.dumps(dict(heatEst=.5,coolEst=6)))
            self.client.until(lambda:self.client.get('getControlSettings')['heatEst']==.5)
            maintenance(self.page,'advanced-settings')
            self.page.locator('.cs.load-defaults').click()
            self.client.until(lambda:self.client.get('getControlSettings')['mode']=='o')
            live=self.client.get('getControlSettings')
            assert live['heatEst']==.199 and self.client.store()['settings_raw']['heatEst']==256
            self.record('default actions retain persistence quirks','browser defaults / PHP parameter endpoint',dict(live_heat_est=.199,saved_heat_raw=256,live_Kp=5,saved_Kp_raw=3584))
            self.change_parameter_ui('Kp',5)
            self.profile_workflow()
            self.socket_workflows()
            # Reset through the panel, rediscover, and assign again before restart qualification.
            maintenance(self.page,'advanced-settings')
            self.page.click('.reset-controller-button')
            self.client.until(lambda:all(d['f']==0 for d in self.client.store()['devices']))
            empty=self.client.devices()
            assert empty['installed']==[] and len(empty['available'])==7
            assign_all(self.page,self.client)
            self.record('reset and rediscovery','browser reset/assignment + host cache check',dict(installed_after_reset=0,available_after_reset=7,reassigned=7))
            self.accelerated_and_restart()
            assert not self.errors,self.errors
            self.page.screenshot(path=str(EVIDENCE/'panel-final.png'),full_page=True)
            maintenance(self.page,'view-logs')
            self.page.click('#refresh-logs')
            self.page.locator('#view-logs .stdout').filter(has_text='Found BrewPi').wait_for(timeout=15000)
            assert 'Cannot open log file' not in self.page.locator('#view-logs').inner_text()
            self.record('maintenance log viewer','browser View logs → PHP → real host log files',dict(stdout_contains_controller_identity=True))
            close_maintenance(self.page)
            assert not self.errors,self.errors
            self.record('browser execution','headless Chromium',dict(javascript_errors=self.errors))
            browser.close()

    def profile_workflow(self):
        # Original input data, consumed by the real PHP profile endpoint and host.
        close_maintenance(self.page)
        set_mode(self.page,self.client,'b',22)
        # Let the panel's pending five-second Apply refresh finish before editing another tab.
        self.page.wait_for_timeout(6000)
        now=dt.datetime.now()
        rows=[('Date','Temp')]+[((now+dt.timedelta(seconds=s)).strftime('%Y-%m-%dT%H:%M:%S'),t)
                                 for s,t in [(-60,''),(25,''),(26,'21'),(120,'21')]]
        contents='\n'.join(','.join(row) for row in rows)+'\n'
        (LAB/'www/data/profiles').mkdir(parents=True,exist_ok=True)
        payload=urllib.parse.urlencode(dict(name='OriginalM4',profile=contents)).encode()
        with urllib.request.urlopen('http://127.0.0.1:8080/save_beer_profile.php',payload,timeout=10) as response:
            assert json.load(response)['status']=='success'
        # Use the panel's normal Open dialog, select the file, then Apply.
        self.page.locator("#control-panel a[href='#profile-control']").click()
        # The legacy chart was initially rendered in a hidden tab. A normal
        # window resize lets its own handler recompute its visible dimensions.
        self.page.set_viewport_size({'width':1400,'height':1180})
        self.page.wait_for_timeout(300)
        self.page.screenshot(path=str(EVIDENCE/'profile-before-open.png'),full_page=True)
        self.page.locator('#load-controls').click()
        self.page.locator('#profileSelect li').filter(has_text='OriginalM4').click()
        self.page.get_by_role('button',name='OK',exact=True).click()
        self.page.locator('#profileTableName').filter(has_text='OriginalM4').wait_for()
        wire_start=len(self.wire('host'))
        set_mode(self.page,self.client,'p')
        disabled=self.client.until(lambda:(s if s['mode']=='p' and s['beerSet'] is None else False)
                                   if (s:=self.client.get('getControlSettings')) else False,timeout=12)
        active=self.client.until(lambda:(s if s['mode']=='p' and s['beerSet']==21 else False)
                                 if (s:=self.client.get('getControlSettings')) else False,timeout=40)
        assert b'j{beerSet:null}' in self.wire('host')[wire_start:]
        self.record('profile disabled segment and resumption','PHP profile input + browser Open/Apply + real host wall clock',dict(disabled=disabled,resumed=active,clock_speed=1))
        set_mode(self.page,self.client,'o')

    def socket_workflows(self):
        # No UI control exists for these fields. Exercise the real host socket explicitly.
        self.client.socket_send('applyDevice='+json.dumps(dict(i=0,f=9,j=.25)))
        calibrated=self.client.devices()['installed'][0]
        assert calibrated['j']==.25
        assert abs(calibrated['v']-20.25)<.07,calibrated
        self.client.socket_send('applyDevice='+json.dumps(dict(i=0,f=9,d=1)))
        deactivated=self.client.devices()['installed'][0]
        assert deactivated['d']==1 and deactivated['v'] is None
        self.client.socket_send('applyDevice='+json.dumps(dict(i=0,f=9,d=0)))
        reactivated=self.client.devices()['installed'][0]
        assert reactivated['d']==0 and reactivated['j']==.25 and abs(reactivated['v']-calibrated['v'])<.07
        self.client.socket_send('setParameters='+json.dumps(dict(mode='t')))
        self.client.until(lambda:self.client.get('getControlSettings')['mode']=='t')
        assert self.client.store()['settings_raw']['mode']==ord('t')
        self.client.socket_send('writeDevice='+json.dumps(dict(i=3,w=1)))
        manual=self.client.devices()['installed'][3]
        assert manual['v']==1
        self.client.socket_send('writeDevice='+json.dumps(dict(i=3,w=0)))
        assert self.client.devices()['installed'][3]['v']==0
        self.record('calibration, deactivation, and manual output','real host UNIX socket (no browser-control claim)',dict(calibrated=calibrated,deactivated=deactivated,reactivated=reactivated,manual_on=manual))
        self.client.post('setOff')

    def accelerated_and_restart(self):
        set_mode(self.page,self.client,'b',22)
        # A quiescent checkpoint allows a separate, declared accelerated constant-target phase.
        self.lab.stop_host()
        self.lab.stop_process(self.lab.emulator)
        assert self.lab.emulator.returncode==0
        self.lab.tap.close();self.lab.tap=None
        self.lab.start_emulator(speed=60,resume=True)
        self.lab.start_host()
        self.client.until(lambda:self.client.get('getControlSettings')['beerSet']==22)
        session=self.lab.session
        self.client.until(lambda:any(t.get('State') in [3,9] and t.get('BeerSet')==22
                                     for t in self.frames('T',session)),timeout=35)
        time.sleep(18)
        heating=self.client.devices()['installed']
        assert heating[0]['v']>20 and heating[1]['v']>20,heating
        cooling_start=len(self.frames('T',session))
        set_mode(self.page,self.client,'b',18)
        self.client.until(lambda:any(t.get('State') in [4,8] and t.get('BeerSet')==18
                                     for t in self.frames('T',session)[cooling_start:]),timeout=70)
        time.sleep(15)
        cooling=self.client.devices()['installed']
        assert cooling[1]['v']<heating[1]['v'],(heating,cooling)
        self.record('evolving temperatures and control states','browser targets / real host logs at declared 60x plant pacing',dict(heating=heating[:2],cooling=cooling[:2],host_clock='unchanged wall time'))
        # Finish on an intentionally unsaved C reset; restart must load the saved gain.
        self.change_parameter_ui('Kp',7)
        self.page.locator('.cc.load-defaults').click()
        self.client.until(lambda:self.client.get('getControlConstants')['Kp']==5)
        before=self.client.store()
        assert before['constants_raw']['Kp']==3584
        self.lab.stop_host()
        self.lab.stop_process(self.lab.emulator)
        assert self.lab.emulator.returncode==0
        self.lab.tap.close();self.lab.tap=None
        self.lab.start_emulator(speed=1,resume=False)
        self.lab.start_host()
        self.client.until(lambda:self.client.get('getControlConstants')['Kp']==7)
        restored=self.client.devices()
        assert len(restored['installed'])==7
        assert self.client.store()['devices']==before['devices']
        assert self.client.get('getControlSettings')['beerSet']==18
        # The fresh physical scenario is independent of the saved controller configuration.
        assert abs(restored['installed'][0]['v']-20)<.07
        self.record('actual process restart','host/emulator stop and fresh start; real host queries',dict(restored_gain=7,restored_beer_target=18,restored_slots=7,fresh_beer_c=restored['installed'][0]['v']))
        with self.page.expect_response(lambda response:response.url.endswith('/get_beer_data.php')) as chart_reply:
            self.page.reload(wait_until='domcontentloaded')
        chart=chart_reply.value.json()
        columns={col['id']:i for i,col in enumerate(chart['cols'])}
        assert {'Time','BeerTemp','FridgeTemp','State'}.issubset(columns)
        states={row['c'][columns['State']]['v'] for row in chart['rows'] if row['c'][columns['State']]}
        assert {3,4}.issubset(states),states
        samples=[row['c'][columns['FridgeTemp']]['v'] for row in chart['rows'] if row['c'][columns['FridgeTemp']]]
        assert any(22<value<30 for value in samples) and any(0<value<15 for value in samples),samples
        self.page.wait_for_selector('#curr-beer-chart canvas',timeout=20000)
        files=list((LAB/'www/data/IntegrationTest').glob('*.csv'))
        assert files
        with files[-1].open() as source:
            rows=list(csv.reader(source))
        assert len(rows)>5 and len(rows[1])==9 and rows[1][0]=='Timestamp'
        assert all(len(row)==len(rows[1]) for row in rows[2:])
        self.record('logs and chart','real host CSV/JSON → PHP → browser canvas',dict(csv_rows=len(rows),json_rows=len(chart['rows']),logged_states=sorted(states),canvas_count=self.page.locator('#curr-beer-chart canvas').count()))


def main():
    run=Run()
    def terminated(number,frame):
        raise SystemExit(143)
    signal.signal(signal.SIGTERM,terminated)
    error=None
    try:
        run.execute()
    except BaseException:
        error=traceback.format_exc()
    try:
        run.lab.close()
    except BaseException:
        error=(error or '')+'\nCleanup: '+traceback.format_exc()
    if error:
        print(error,flush=True)
        run.save('failed',error)
        raise RuntimeError('integration failed; see integration-results.json')
    run.save('passed')


if __name__=='__main__':
    main()
