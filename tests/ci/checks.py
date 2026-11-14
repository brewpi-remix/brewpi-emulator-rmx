# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original R2 negative gates. Synthetic inputs are not release artifacts."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from gate import LANES, validate, HELPERS, emit_receipt
from native import SUITES
from payload import FILES, Payload, preflight, sha

IDENTITY=dict(source_inputs_sha256='c'*64,source_commit='a'*40,event='push',pr_head=None,pr_base=None,pr_merge=None,
              workflow_ref='owner/repo/.github/workflows/regression.yml@refs/heads/main',
              workflow_sha='a'*40,run_id='17',run_attempt='2')


def proof(lane):
    if lane.startswith('linux-') or lane=='macos-arm64-development':
        kinds=['debug','sanitize'] if lane.startswith('macos') else ['sanitize' if lane.endswith('sanitizers') else 'release']
        rows=[dict(status='passed',kind=k,machine=('arm64' if lane.startswith('macos') else ('aarch64' if 'arm64' in lane else 'x86_64')),system=('Darwin' if lane.startswith('macos') else 'Linux'),suites=sorted(SUITES),counts=dict(passed=48,unresolved_reference_characterization=9)) for k in kinds]
        if lane.endswith('-release'):
            rows.append(dict(status='passed',source_git=False,reference_checkouts=False,build=dict(rows[0],cmake='cmake version 3.16.9',python='3.9.25')))
        return rows+(HELPERS if lane.startswith('macos') else [])
    return {'specification':['specification','original-source-SPDX'],'helper-regressions':HELPERS,
            'host-panel-arm64':['17 host/panel workflows','reference/source integrity','owned container removal']}[lane]


def passing():
    return {lane:dict(result='success',outputs=dict(receipt=base64.b64encode(json.dumps(dict(
        lane=lane,status='passed',producer='github-actions',identity=IDENTITY,started=1,finished=2,
        checks=proof(lane))).encode()).decode())) for lane in LANES}


def mutate(needs, field, value):
    lane=LANES[0]
    row=json.loads(base64.b64decode(needs[lane]['outputs']['receipt']))
    if field in row['identity']:row['identity'][field]=value
    else:row[field]=value
    needs[lane]['outputs']['receipt']=base64.b64encode(json.dumps(row).encode()).decode()


class Completion(unittest.TestCase):
    def test_complete_run(self):self.assertEqual(validate(passing(),IDENTITY)['status'],'passed')

    def test_nonexecuted_or_failed(self):
        for status in ['skipped','neutral','cancelled','failure','timed_out',None]:
            with self.subTest(status=status):
                needs=passing();needs[LANES[0]]['result']=status
                with self.assertRaises(ValueError):validate(needs,IDENTITY)

    def test_missing_receipts(self):
        for action in ['job','output','empty','bad_encoding']:
            needs=passing()
            if action=='job':del needs[LANES[0]]
            elif action=='output':needs[LANES[0]]['outputs']={}
            else:needs[LANES[0]]['outputs']['receipt']='' if action=='empty' else '!'
            with self.assertRaises((ValueError,KeyError)):validate(needs,IDENTITY)

    def test_stale_or_substituted_receipts(self):
        for field,value in [('source_commit','b'*40),('source_inputs_sha256','d'*64),('workflow_sha','b'*40),('run_id','18'),('run_attempt','1'),
                            ('workflow_ref','another-workflow'),('lane','wrong'),('producer','external'),
                            ('status','failed'),('checks',[]),('finished',0),('finished',float('nan')),('finished',float('inf'))]:
            with self.subTest(field=field):
                needs=passing();mutate(needs,field,value)
                with self.assertRaises(ValueError):validate(needs,IDENTITY)

    def test_candidate_merge_or_wrong_commit(self):
        with self.assertRaises(ValueError):validate(passing(),IDENTITY,'b'*40)
        expected=dict(IDENTITY,event='pull_request');needs=passing()
        for lane in LANES:
            row=json.loads(base64.b64decode(needs[lane]['outputs']['receipt']));row['identity']=expected
            needs[lane]['outputs']['receipt']=base64.b64encode(json.dumps(row).encode()).decode()
        with self.assertRaises(ValueError):validate(needs,expected,'a'*40)

    def test_omitted_named_proof(self):
        for lane in LANES:
            needs=passing();row=json.loads(base64.b64decode(needs[lane]['outputs']['receipt']))
            row['checks']=row['checks'][:-1]
            needs[lane]['outputs']['receipt']=base64.b64encode(json.dumps(row).encode()).decode()
            with self.subTest(lane=lane),self.assertRaises(ValueError):validate(needs,IDENTITY)

    def test_owned_cleanup_gates(self):
        from linux import remove_container
        with tempfile.TemporaryDirectory() as tmp:
            cid=Path(tmp)/'id';cid.write_text('owned-only')
            for result in ['remaining','',subprocess.CalledProcessError(7,['docker','ps'])]:
                with patch('linux.subprocess.run') as run,patch('linux.subprocess.check_output') as query:
                    if isinstance(result,Exception):query.side_effect=result
                    else:query.return_value=result
                    if result:
                        with self.assertRaises((RuntimeError,subprocess.CalledProcessError)):remove_container(cid)
                    else:remove_container(cid)
                    self.assertEqual(run.call_args.args[0],['docker','rm','-f','owned-only'])

    def test_assertions_disabled(self):
        with patch.dict(os.environ,PYTHONOPTIMIZE='1'):
            with self.assertRaises(RuntimeError):preflight()
        result=subprocess.run([sys.executable,'-O','-c','from payload import preflight; preflight()'],cwd=Path(__file__).parent,capture_output=True)
        self.assertNotEqual(result.returncode,0)

    def test_bad_build_is_failure(self):
        from native import run
        with tempfile.TemporaryDirectory() as tmp:
            fake=Path(tmp)/'cmake';fake.write_text('#!/bin/sh\nexit 7\n');fake.chmod(0o755)
            with self.assertRaises(subprocess.CalledProcessError):run(Path(tmp),Path(tmp)/'build','release',str(fake))
            self.assertFalse((Path(tmp)/'build/execution.json').exists())


class Packaged(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'payload';self.root.mkdir()
        for name in FILES:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'original fixture\n')
        (self.root/'share/doc/brewpi-emulator-rmx/LICENSE.md').write_bytes((Path(__file__).resolve().parents[2]/'LICENSE.md').read_bytes())
        binary=self.root/'bin/brewpi-emulator-rmx'
        header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';header[18:20]=(183).to_bytes(2,'little');binary.write_bytes(header)
        self.manifest=dict(schema=1,install_prefix='/opt/brewpi-emulator-rmx',candidate_version='0.0.1-rc.1',architecture='arm64',source_commit='a'*40,
                           application_version_output='fixture-only',files={name:sha(self.root/name) for name in FILES})
        self.path=Path(self.tmp.name)/'manifest.json';self.save()

    def save(self):self.path.write_text(json.dumps(self.manifest))

    def load(self):
        with patch('payload.subprocess.check_output',return_value='fixture-only\n'):
            return Payload(self.root,self.path,'arm64')

    def test_original_fixture(self):self.assertEqual(self.load().verify('end')['mode'],'packaged-input')

    def test_missing_extra_symlink_changed(self):
        payload=self.load()
        for kind in ['missing','extra','symlink','changed']:
            path=self.root/'share/doc/brewpi-emulator-rmx/operation.txt';original=path.read_bytes()
            if kind=='missing':path.unlink()
            elif kind=='extra':(self.root/'extra').write_text('extra')
            elif kind=='symlink':path.unlink();path.symlink_to(self.root/'share/doc/brewpi-emulator-rmx/LICENSE.md')
            else:path.write_text('substituted')
            with self.subTest(kind=kind),self.assertRaises(ValueError):payload.verify('restart')
            if path.is_symlink():path.unlink()
            path.write_bytes(original)
            if (self.root/'extra').exists():(self.root/'extra').unlink()

    def test_wrong_architecture_hash_version_inventory(self):
        for key,value in [('architecture','amd64'),('candidate_version','0.1.0'),
                          ('application_version_output','stale'),('schema',True),('source_commit','main'),('files',{})]:
            old=copy.deepcopy(self.manifest);self.manifest[key]=value;self.save()
            with self.subTest(key=key),self.assertRaises(ValueError):self.load()
            self.manifest=old
        self.save();binary=self.root/'bin/brewpi-emulator-rmx';data=bytearray(binary.read_bytes());data[18:20]=(62).to_bytes(2,'little');binary.write_bytes(data)
        self.manifest['files']['bin/brewpi-emulator-rmx']=sha(binary);self.save()
        with self.assertRaises(ValueError):self.load()

    def test_no_source_fallback(self):
        from payload import selected
        for env in [dict(RMX_EXECUTION_MODE='unknown'),dict(RMX_EXECUTION_MODE='packaged-input'),
                    dict(RMX_EXECUTION_MODE='source-build',RMX_PAYLOAD_ROOT=str(self.root))]:
            with patch.dict(os.environ,env,clear=True),self.assertRaises((ValueError,KeyError)):selected()


class ReviewGates(unittest.TestCase):
    def test_receipt_budget_and_process_environment(self):
        needs=passing()
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'outputs'
            for lane in LANES:
                row=json.loads(base64.b64decode(needs[lane]['outputs']['receipt']))
                emit_receipt(row,output)
            self.assertLess(len(json.dumps(needs)),65536)
            subprocess.run([sys.executable,'-c','import os,json; assert len(json.loads(os.environ["RMX_NEEDS"]))==8'],
                           env=dict(os.environ,RMX_NEEDS=json.dumps(needs)),check=True)
            with self.assertRaises(ValueError):emit_receipt(dict(raw='x'*8192),output)
            self.assertEqual(len(output.read_text().splitlines()),8)

    def test_native_architecture_proof(self):
        for lane in ['linux-arm64-release','linux-amd64-sanitizers','macos-arm64-development']:
            needs=passing();row=json.loads(base64.b64decode(needs[lane]['outputs']['receipt']))
            row['checks'][0]['machine']='wrong-machine'
            needs[lane]['outputs']['receipt']=base64.b64encode(json.dumps(row).encode()).decode()
            with self.assertRaises(ValueError):validate(needs,IDENTITY)

    def test_native_report_requires_every_named_suite(self):
        from native import validate_build
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'Testing/run';folder.mkdir(parents=True)
            results=root/'test-results';results.mkdir()
            (results/'milestone3-fixtures.json').write_text(json.dumps(dict(counts=dict(passed=48,unresolved_reference_characterization=9))))
            xml=folder/'Test.xml'
            for names,status in [(list(SUITES),'passed'),(list(SUITES)[:-1],'passed'),(list(SUITES),'notrun'),(['wrong']*6,'passed')]:
                xml.write_text('<Site><Testing>'+''.join('<Test Status="'+status+'"><Name>'+name+'</Name></Test>' for name in names)+'</Testing></Site>')
                if len(names)==6 and set(names)==SUITES and status=='passed':validate_build(root)
                else:
                    with self.assertRaises(ValueError):validate_build(root)

    def test_ctest_dashboard_log_collection(self):
        from native import copy_test_log
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'Testing/Temporary';folder.mkdir(parents=True)
            with self.assertRaises(ValueError):copy_test_log(root,root/'collected.log')
            log=folder/'LastTest_20261114-1200.log';log.write_text('original test log')
            copy_test_log(root,root/'collected.log')
            self.assertEqual((root/'collected.log').read_text(),'original test log')
            (folder/'LastTest.log').write_text('stale second attempt')
            with self.assertRaises(ValueError):copy_test_log(root,root/'collected.log')

    def test_host_panel_guest_architecture_guard(self):
        from gate import execute
        with patch('gate.platform.machine',return_value='aarch64'),patch('gate.subprocess.check_output',return_value='amd64\n'),patch('gate.command') as command:
            with self.assertRaises(ValueError):execute('host-panel-arm64',Path('/unused'))
            command.assert_not_called()

    def test_guest_guard(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qualification'))
        from prepare import require_guest
        require_guest('tmpfs /qualification tmpfs rw 0 0','1')
        for marker,mount in [('0','tmpfs /qualification tmpfs rw 0 0'),('1','root / ext4 rw 0 0'),('1','root /qualification ext4 rw 0 0')]:
            with self.assertRaises(RuntimeError):require_guest(mount,marker)

    def test_wrapper_does_not_emit_before_verified_cleanup(self):
        import linux
        for fail in [False,True,'build']:
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);output=root/'outputs';lane='linux-arm64-sanitizers'
                def run(args,**kwargs):
                    if fail=='build' and args[:2]==['docker','build']:raise subprocess.CalledProcessError(7,args)
                    if args[:2]==['docker','run']:
                        Path(args[args.index('--cidfile')+1]).write_text('owned-ci')
                        folder=root/'runs/ci'/lane;folder.mkdir()
                        row=json.loads(base64.b64decode(passing()[lane]['outputs']['receipt']))
                        (folder/'receipt.json').write_text(json.dumps(row))
                        self.assertFalse(output.exists())
                        self.assertNotIn(str(output),str(args))
                        self.assertIn('RMX_DEFER_RECEIPT=1',args)
                        self.assertEqual(args[args.index('--user')+1],str(os.getuid())+':'+str(os.getgid()))
                    return subprocess.CompletedProcess(args,0)
                def query(args,**kwargs):
                    if args[:3]==['docker','image','inspect']:return 'sha256:'+'a'*64+'\n'
                    if fail:raise subprocess.CalledProcessError(7,args)
                    return ''
                env=dict(GITHUB_EVENT_PATH=str(root/'event.json'),GITHUB_OUTPUT=str(output),GITHUB_SHA='a'*40,
                         GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF='workflow',GITHUB_WORKFLOW_SHA='a'*40,
                         GITHUB_RUN_ID='17',GITHUB_RUN_ATTEMPT='2')
                with patch.object(linux,'ROOT',root),patch.object(sys,'argv',['linux.py',lane]),patch('linux.platform.machine',return_value='aarch64'),patch.dict(os.environ,env),patch('linux.subprocess.run',side_effect=run),patch('linux.subprocess.check_output',side_effect=query):
                    if fail:
                        with self.assertRaises(subprocess.CalledProcessError):linux.entry()
                        self.assertFalse(output.exists())
                        self.assertEqual(json.loads((root/'runs/ci'/lane/'receipt.json').read_text())['status'],'failed')
                    else:
                        linux.entry();self.assertEqual(len(output.read_text().splitlines()),1)


class SavedEvidence(unittest.TestCase):
    def test_manifest_identity_and_missing_hash_reports(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qualification'))
        from evidence import input_evidence
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest.json'
            files={name:'a'*64 for name in FILES}
            manifest.write_text(json.dumps(dict(source_commit='a'*40,candidate_version='0.0.1-rc.1',architecture='arm64',files=files)))
            record=dict(mode='packaged-input',manifest_sha256=sha(manifest),source_commit='a'*40,candidate_version='0.0.1-rc.1',architecture='arm64',files=files)
            phases=['before-integration','restart-1','restart-2','restart-3','after-integration']
            (root/'execution-input.json').write_text(json.dumps(dict(mode='packaged-input',executable='/payload/bin/brewpi-emulator-rmx',sha256='a'*64)))
            (root/'executable-hashes.jsonl').write_text(''.join(json.dumps(dict(phase=p,sha256='a'*64))+'\n' for p in phases[1:]))
            def save(rows):
                (root/'payload-execution.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with patch.dict(os.environ,RMX_EXECUTION_MODE='packaged-input',RMX_PAYLOAD_MANIFEST=str(manifest),RMX_CANDIDATE_COMMIT='a'*40):
                rows=[dict(record,phase=p) for p in phases];save(rows);input_evidence(root,'integration')
                for field,value in [('source_commit','b'*40),('candidate_version','0.0.2'),('architecture','amd64'),('files',{'unrelated':'hash'})]:
                    save([dict(r,**{field:value}) for r in rows])
                    with self.subTest(field=field),self.assertRaises(ValueError):input_evidence(root,'integration')
                save(rows[:-1])
                with self.assertRaises(ValueError):input_evidence(root,'integration')
                save(rows)
                original_manifest=manifest.read_text()
                data=json.loads(original_manifest);data['application_version_output']='changed after execution';manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError):input_evidence(root,'integration')
                manifest.write_text(original_manifest)
                (root/'executable-hashes.jsonl').unlink()
                with self.assertRaises(FileNotFoundError):input_evidence(root,'integration')

    def test_consistently_rehashed_nonmit_license_is_rejected(self):
        case=Packaged();case.setUp()
        try:
            path=case.root/'share/doc/brewpi-emulator-rmx/LICENSE.md';path.write_text('different terms')
            case.manifest['files'][str(path.relative_to(case.root))]=sha(path);case.save()
            with self.assertRaises(ValueError):case.load()
        finally:case.doCleanups()


if __name__=='__main__':
    preflight()
    unittest.main()
