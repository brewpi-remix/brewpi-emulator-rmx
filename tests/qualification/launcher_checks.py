# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Test qualification evidence/isolation gates without a Docker daemon."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
import tempfile
import unittest

LAUNCHER=Path(__file__).with_name('run-isolated.sh').resolve()
FAKE='''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['FAKE_CALLS'],'a') as log:log.write(json.dumps(args)+'\\n')
if args[:2]==['image','inspect']:
 if '--format' not in args:print('[]')
 elif '{{.Architecture}}' in args:print(os.environ.get('FAKE_ARCH','arm64'))
 else:print('sha256:agreed-image')
elif args[0]=='run':
 Path(args[args.index('--cidfile')+1]).write_text('owned-test-container')
 for index,arg in enumerate(args):
  if arg=='-v' and args[index+1].endswith(':/evidence'):
   evidence=Path(args[index+1][:-len(':/evidence')])
   mode=os.environ.get('FAKE_REPORT','passed')
   if mode!='missing':
    (evidence/'source-integrity.json').write_text('{"status":"passed","unchanged":true,"files":1}')
    runtime=dict(status='passed',checks=[dict(status='passed')]*9)
    for kind in ['release','sanitize']:
     folder=evidence/('native-'+kind);folder.mkdir()
     (folder/'milestone3-fixtures.json').write_text(json.dumps(dict(counts=dict(passed=48,unresolved_reference_characterization=9))))
    (evidence/'runtime-results').mkdir()
    (evidence/'runtime-results/runtime-results.json').write_text(json.dumps(runtime))
    (evidence/'service-results.json').write_text(json.dumps(dict(status='passed',unit_commands_executed=True)))
    (evidence/'qualification-results.json').write_text(json.dumps(dict(status=mode,runtime=runtime)))
 if os.environ.get('FAKE_PAUSE'):
  Path(os.environ['FAKE_STARTED']).touch();time.sleep(30)
 sys.exit(int(os.environ.get('FAKE_RUN_EXIT','0')))
elif args[0]=='stop' and os.environ.get('FAKE_PAUSE'):
 Path(os.environ['FAKE_STOPPING']).touch();time.sleep(.3)
elif args[0]=='ps':
 if os.environ.get('FAKE_CLEANUP')=='present':print('owned-test-container')
 if os.environ.get('FAKE_CLEANUP')=='unavailable':sys.exit(8)
'''


class LauncherChecks(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        fake=self.root/'docker';fake.write_text(FAKE);fake.chmod(0o755)
        self.calls=self.root/'calls.jsonl'
        self.evidence=self.root/'evidence'
        self.env=dict(os.environ,PATH=str(self.root)+os.pathsep+os.environ['PATH'],FAKE_CALLS=str(self.calls))

    def tearDown(self):
        self.temporary.cleanup()

    def launch(self,**variables):
        return subprocess.run(['bash',str(LAUNCHER),str(self.evidence)],env=dict(self.env,**variables),capture_output=True,text=True,timeout=10)

    def rows(self):
        return [json.loads(row) for row in self.calls.read_text().splitlines()]

    def test_existing_evidence_is_untouched(self):
        self.evidence.mkdir();sentinel=self.evidence/'qualification-results.json'
        sentinel.write_bytes(b'previous result')
        self.assertNotEqual(self.launch().returncode,0)
        self.assertEqual(sentinel.read_bytes(),b'previous result')
        self.assertFalse(self.calls.exists())

    def test_failed_launcher_invalidates_apparent_pass_and_cleans_owned_container(self):
        self.assertEqual(self.launch(FAKE_RUN_EXIT='7').returncode,7)
        report=json.loads((self.evidence/'qualification-results.json').read_text())
        self.assertEqual(report['status'],'failed')
        self.assertEqual(json.loads((self.evidence/'qualification-before-launcher-failure.json').read_text())['status'],'passed')
        self.assertEqual(self.rows()[-3:-1],[['stop','--time','15','owned-test-container'],['rm','-f','owned-test-container']])

    def test_zero_exit_cannot_pass_missing_or_failed_evidence(self):
        for mode in ['missing','failed']:
            with self.subTest(mode=mode):
                self.evidence=self.root/('evidence-'+mode)
                self.assertNotEqual(self.launch(FAKE_REPORT=mode).returncode,0)
                self.assertEqual(json.loads((self.evidence/'qualification-results.json').read_text())['status'],'failed')

    def test_cleanup_must_be_verified(self):
        for mode in ['present','unavailable']:
            with self.subTest(mode=mode):
                self.evidence=self.root/('evidence-'+mode)
                self.assertNotEqual(self.launch(FAKE_CLEANUP=mode).returncode,0)
                self.assertFalse(json.loads((self.evidence/'launcher-results.json').read_text())['cleanup_verified'])
                self.assertEqual(json.loads((self.evidence/'qualification-results.json').read_text())['status'],'failed')

    def test_termination_finishes_cleanup_and_invalidates_child_pass(self):
        started=self.root/'started';stopping=self.root/'stopping'
        env=dict(self.env,FAKE_PAUSE='yes',FAKE_STARTED=str(started),FAKE_STOPPING=str(stopping))
        process=subprocess.Popen(['bash',str(LAUNCHER),str(self.evidence)],env=env,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        def await_path(path):
            deadline=time.monotonic()+4
            while not path.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(path.exists(),str(path))
        try:
            await_path(started)
            os.killpg(process.pid,signal.SIGTERM)
            await_path(stopping)
            # A second interruption during finalization must not abandon evidence/cleanup.
            os.killpg(process.pid,signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertEqual(process.returncode,143)
            self.assertEqual(json.loads((self.evidence/'qualification-results.json').read_text())['status'],'failed')
            self.assertTrue(json.loads((self.evidence/'launcher-results.json').read_text())['cleanup_verified'])
        finally:
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL)
            process.communicate(timeout=3)

    def test_wrong_architecture_never_runs(self):
        self.assertNotEqual(self.launch(FAKE_ARCH='amd64').returncode,0)
        self.assertFalse(any(row[0]=='run' for row in self.rows()))
        self.assertEqual(json.loads((self.evidence/'launcher-results.json').read_text())['status'],'failed')

    def test_success_uses_resolved_image_and_isolation(self):
        self.assertEqual(self.launch().returncode,0)
        args=next(row for row in self.rows() if row[0]=='run')
        self.assertEqual(args[args.index('--network')+1],'none')
        self.assertIn('--init',args);self.assertIn('--rm',args)
        self.assertIn('sha256:agreed-image',args)
        mounts=[args[i+1] for i,arg in enumerate(args) if arg=='-v']
        self.assertEqual(len(mounts),2)
        self.assertTrue(any(value.endswith(':/work:ro') for value in mounts))
        self.assertFalse(any(arg in args for arg in ['--privileged','--device','-p','--publish','--network=host']))
        self.assertEqual(json.loads((self.evidence/'launcher-results.json').read_text())['status'],'passed')


if __name__=='__main__':
    unittest.main()
