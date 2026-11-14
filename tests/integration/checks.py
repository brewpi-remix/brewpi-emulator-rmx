# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative regressions for integration evidence and isolation gates."""
if not __debug__:
    raise SystemExit("Python assertions must be enabled")

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import lab
import relay_trace
from client import validate_devices

LAUNCHER=Path(__file__).with_name('run-isolated.sh').resolve()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='rmx-m4-check-')
        self.root=Path(self.tmp.name)
        self.bin=self.root/'bin';self.bin.mkdir()
        self.calls=self.root/'calls.jsonl'
        fake=self.bin/'docker'
        fake.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['RMX_TEST_CALLS'],'a') as out:out.write(json.dumps(args)+'\\n')
if args[0]=='build' and os.environ['RMX_TEST_MODE']=='build-fail':sys.exit(9)
if args[:2]==['image','inspect']:print('sha256:review-image' if '--format' in args else '[]')
if args[0]=='run':
 evidence=next(args[i+1][:-len(':/evidence')] for i in range(len(args)-1) if args[i]=='-v' and args[i+1].endswith(':/evidence'))
 Path(args[args.index('--cidfile')+1]).write_text('only-this-test-container')
 result=dict(status='passed',workflows=[dict(name=name,status='passed') for name in ['startup', 'factory initialization', 'discovery and assignment', 'mode b', 'mode f', 'mode o', 'LCD bytes and alternation', 'temperature units', 'default actions retain persistence quirks', 'profile disabled segment and resumption', 'calibration, deactivation, and manual output', 'reset and rediscovery', 'evolving temperatures and control states', 'actual process restart', 'logs and chart', 'maintenance log viewer', 'browser execution']],browser_errors=[])
 Path(evidence,'integration-results.json').write_text(json.dumps(result))
 if os.environ['RMX_TEST_MODE']!='missing-child':
  Path(evidence,'cleanup-results.json').write_text(json.dumps(dict(status='failed' if os.environ['RMX_TEST_MODE']=='cleanup-fail' else 'passed',errors=[],host_exits=[0])))
  Path(evidence,'source-integrity.json').write_text(json.dumps(dict(status='passed',unchanged=True,files=1)))
  Path(evidence,'reference-code-integrity.json').write_text(json.dumps(dict(unchanged=True,checked_files=1)))
  Path(evidence,'native-test-results').mkdir()
  Path(evidence,'native-test-results/milestone3-fixtures.json').write_text(json.dumps(dict(counts=dict(passed=48,unresolved_reference_characterization=9))))
  Path(evidence,'native-test-results/execution.json').write_text(json.dumps(dict(status='passed',kind='debug',suites=['milestone3-model', 'milestone3-dynamics', 'milestone3-process', 'milestone2-fixtures', 'milestone2-edges', 'milestone2-pty'],counts=dict(passed=48,unresolved_reference_characterization=9))))
  Path(evidence,'execution-input.json').write_text(json.dumps(dict(mode='source-build',sha256='test-hash')))
  Path(evidence,'executable-hashes.jsonl').write_text(''.join(json.dumps(dict(phase=p,sha256='test-hash'))+'\\n' for p in ['restart-1','restart-2','restart-3','after-integration']))
 if os.environ['RMX_TEST_MODE']=='run-fail':sys.exit(7)
if args[0]=='ps' and os.environ['RMX_TEST_MODE']=='cleanup-remains':print('only-this-test-container')
if args[0]=='ps' and os.environ['RMX_TEST_MODE']=='cleanup-unavailable':sys.exit(8)
''')
        fake.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def launch(self,evidence,mode='ok'):
        env=dict({k:v for k,v in os.environ.items() if k not in {'RMX_EXECUTION_MODE','RMX_PAYLOAD_ROOT','RMX_PAYLOAD_MANIFEST','RMX_CANDIDATE_COMMIT'}},PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
                 RMX_TEST_CALLS=str(self.calls),RMX_TEST_MODE=mode)
        return subprocess.run(['bash',str(LAUNCHER),str(self.root),str(self.root),str(evidence)],
                              env=env,capture_output=True,timeout=10)

    def test_reused_directory_preserves_existing_evidence(self):
        evidence=self.root/'old';evidence.mkdir()
        previous=b'{"status":"passed","sentinel":"old"}\n'
        (evidence/'integration-results.json').write_bytes(previous)
        result=self.launch(evidence)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((evidence/'integration-results.json').read_bytes(),previous)
        self.assertFalse(self.calls.exists())

    def test_build_failure_has_failed_report(self):
        evidence=self.root/'build'
        result=self.launch(evidence,'build-fail')
        self.assertEqual(result.returncode,9)
        self.assertEqual(json.loads((evidence/'integration-results.json').read_text())['status'],'failed')
        self.assertEqual(json.loads((evidence/'launcher-results.json').read_text())['exit_code'],9)

    def test_failed_launcher_invalidates_apparent_pass_and_cleans_owned_id(self):
        evidence=self.root/'run'
        result=self.launch(evidence,'run-fail')
        self.assertEqual(result.returncode,7)
        self.assertEqual(json.loads((evidence/'integration-results.json').read_text())['status'],'failed')
        self.assertEqual(json.loads((evidence/'integration-before-launcher-failure.json').read_text())['status'],'passed')
        calls=[json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertIn(['stop','--time','15','only-this-test-container'],calls)
        self.assertIn(['rm','-f','only-this-test-container'],calls)
        args=next(call for call in calls if call[0]=='run')
        self.assertEqual(args[args.index('--network')+1],'none')
        self.assertIn('--init',args)
        self.assertNotIn('--privileged',args)
        self.assertNotIn('-p',args)
        self.assertIn('900',args)
        self.assertEqual(sum(arg.endswith(':ro') for arg in args),3)

    def test_zero_exit_requires_complete_child_evidence(self):
        for mode in ['missing-child','cleanup-fail']:
            with self.subTest(mode=mode):
                evidence=self.root/mode
                self.assertNotEqual(self.launch(evidence,mode).returncode,0)
                self.assertEqual(json.loads((evidence/'integration-results.json').read_text())['status'],'failed')

    def test_container_removal_must_be_verified(self):
        for mode in ['cleanup-remains','cleanup-unavailable']:
            with self.subTest(mode=mode):
                evidence=self.root/mode
                self.assertNotEqual(self.launch(evidence,mode).returncode,0)
                self.assertFalse(json.loads((evidence/'launcher-results.json').read_text())['cleanup_verified'])
                self.assertEqual(json.loads((evidence/'integration-results.json').read_text())['status'],'failed')

    def test_success_uses_resolved_image_and_verified_cleanup(self):
        evidence=self.root/'success'
        result=self.launch(evidence)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        calls=[json.loads(row) for row in self.calls.read_text().splitlines()]
        args=next(call for call in calls if call[0]=='run')
        self.assertIn('sha256:review-image',args)
        self.assertTrue(json.loads((evidence/'launcher-results.json').read_text())['cleanup_verified'])

    def test_complete_trace_records_and_session_scoping(self):
        path=self.root/'trace.jsonl'
        def row(session,data):
            return json.dumps(dict(session=session,direction='controller',hex=data.hex()))+'\n'
        path.write_text(row(1,b'T:{"State":3}\r\n')+row(2,b'T:{"State":4}\r\nT:')+'{"partial":')
        self.assertEqual(relay_trace.frames(path,'T',1),[dict(State=3)])
        self.assertEqual(relay_trace.frames(path,'T',2),[dict(State=4)])
        path.write_text(path.read_text().split('{"partial":')[0]+row(2,b'{"State":0}\r\n'))
        self.assertEqual(relay_trace.frames(path,'T',2),[dict(State=4),dict(State=0)])
        with path.open('a') as output:output.write('not JSON\n')
        with self.assertRaises(ValueError):relay_trace.records(path)

    def test_reference_assets_are_audited(self):
        asset=self.root/'panel.png';asset.write_bytes(b'original external asset')
        instance=lab.Lab()
        instance.code_hashes={str(asset):hashlib.sha256(asset.read_bytes()).hexdigest()}
        with patch.object(lab,'EVIDENCE',self.root):
            instance.audit_references()
            asset.write_bytes(b'changed')
            with self.assertRaises(AssertionError):instance.audit_references()
        report=json.loads((self.root/'reference-code-integrity.json').read_text())
        self.assertFalse(report['unchanged'])

    def test_original_source_changes_are_audited(self):
        for name in ['CMakeLists.txt','LICENSE.md','THIRD_PARTY_NOTICES.md','AGENTS.md','CONTRACT.md','CONTRIBUTING.md','README.md']:
            (self.root/name).write_text('original test input')
        instance=lab.Lab();instance.source_root=self.root
        instance.source_hashes=lab.inventory(self.root)
        with patch.object(lab,'EVIDENCE',self.root):
            instance.audit_source()
            (self.root/'CMakeLists.txt').write_text('changed test input')
            with self.assertRaises(AssertionError):instance.audit_source()
        self.assertFalse(json.loads((self.root/'source-integrity.json').read_text())['unchanged'])

    def test_relay_failure_still_stops_processes_and_audits(self):
        instance=lab.Lab()
        calls=[]
        instance.host_exits=[0]
        instance.php=object()
        class Emulator:
            returncode=0
        instance.emulator=Emulator()
        class BadRelay:
            def close(self):raise RuntimeError('deliberate relay fault')
        instance.tap=BadRelay()
        instance.stop_host=lambda:calls.append('host')
        instance.stop_process=lambda proc:calls.append('process')
        instance.audit_references=lambda:calls.append('audit')
        instance.audit_source=lambda:calls.append('source-audit')
        with patch.object(lab,'LAB',self.root/'absent'),patch.object(lab,'EVIDENCE',self.root):
            with self.assertRaises(AssertionError):instance.close()
            instance.close() # Idempotent; no second attempt to close descriptors.
        self.assertEqual(calls,['host','process','process','audit','source-audit'])
        self.assertEqual(json.loads((self.root/'cleanup-results.json').read_text())['status'],'failed')

    def test_termination_cannot_leave_an_apparent_pass(self):
        # Import only our coordinator; stub an unused browser import so this
        # negative regression needs no external package or browser process.
        program = r'''import json,os,signal,sys,types
from pathlib import Path
sys.path.insert(0,sys.argv[1])
sys.modules['playwright']=types.ModuleType('playwright')
module=types.ModuleType('playwright.sync_api');module.sync_playwright=None
sys.modules['playwright.sync_api']=module
import run as workflow
out=Path(sys.argv[2])
class Cleanup:
 def close(self):
  with (out/'closed').open('a') as target:target.write('closed\n')
class InterruptedRun:
 def __init__(self):self.lab=Cleanup()
 def execute(self):os.kill(os.getpid(),signal.SIGTERM)
 def save(self,status,error=None):(out/'interrupted.json').write_text(json.dumps(dict(status=status,error=error)))
workflow.Run=InterruptedRun
try:workflow.main()
except RuntimeError:pass
else:raise AssertionError('interrupted run returned successfully')
assert (out/'closed').read_text()=='closed\n'
assert json.loads((out/'interrupted.json').read_text())['status']=='failed'
'''
        result=subprocess.run([os.sys.executable,'-c',program,str(LAUNCHER.parent),str(self.root)],
                              capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_device_count_does_not_substitute_for_identity_and_pin(self):
        expected=[dict(i=0,f=9,h=2,p=18,a='28A10100000001E6')]
        devices=dict(available=[],installed=[dict(expected[0])])
        validate_devices(devices,expected)
        devices['installed'][0]['p']=5
        with self.assertRaises(AssertionError):validate_devices(devices,expected)


if __name__=='__main__':
    unittest.main()
