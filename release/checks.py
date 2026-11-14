# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original packaging regressions; no downloaded/reference implementation fixtures."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch
from artifacts import archive, unpack, canonical, source_record
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/ci'))
from payload import source_identity
from payload import Payload, FILES
from local import compare_builds, verify_freeze


class Archives(unittest.TestCase):
    def test_independent_roots_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entries={'bin/original':(b'original MIT fixture\n',0o755),'LICENSE.md':(b'original notice\n',0o644)}
            first=root/'one.tar.gz';second=root/'two.tar.gz'
            archive(first,'candidate',entries,1234567890);archive(second,'candidate',dict(reversed(list(entries.items()))),1234567890)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            expected={n:dict(sha256=hashlib.sha256(d).hexdigest(),mode=m) for n,(d,m) in entries.items()}
            tree=unpack(first,root/'extracted','candidate',expected)
            self.assertEqual((tree/'bin/original').stat().st_mode&0o777,0o755)
            with tarfile.open(first) as source:
                for member in source:
                    self.assertEqual((member.uid,member.gid,member.uname,member.gname,member.mtime),(0,0,'','',1234567890))

    def test_unsafe_members_are_rejected_before_writes(self):
        for name,kind,mode in [('/absolute',tarfile.REGTYPE,0o644),('candidate/../escape',tarfile.REGTYPE,0o644),
            ('candidate/link',tarfile.SYMTYPE,0o644),('candidate/hard',tarfile.LNKTYPE,0o644),
            ('candidate/privileged',tarfile.REGTYPE,0o4755),('other/file',tarfile.REGTYPE,0o644),
            ('candidate/.git/config',tarfile.REGTYPE,0o644),('candidate/folder//file',tarfile.REGTYPE,0o644),('candidate/file/',tarfile.REGTYPE,0o644)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);path=root/'input.tar.gz'
                with tarfile.open(path,'w:gz') as output:
                    member=tarfile.TarInfo(name);member.type=kind;member.mode=mode;member.size=1 if kind==tarfile.REGTYPE else 0
                    if kind in [tarfile.SYMTYPE,tarfile.LNKTYPE]:member.linkname='../escape'
                    output.addfile(member,io.BytesIO(b'x') if member.size else None)
                with self.assertRaises(ValueError):unpack(path,root/'out','candidate')
                self.assertFalse(list((root/'out').rglob('*')))

    def test_duplicates_missing_or_substituted_members_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'input.tar.gz'
            with tarfile.open(path,'w:gz') as output:
                for _ in range(2):
                    member=tarfile.TarInfo('candidate/file');member.mode=0o644;member.size=1;output.addfile(member,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):unpack(path,root/'duplicates','candidate')
            path=root/'original.tar.gz';archive(path,'candidate',{'file':(b'x',0o644)},1)
            for inventory in [{},{'file':dict(sha256='0'*64,mode=0o644)},{'missing':dict(sha256=hashlib.sha256(b'x').hexdigest(),mode=0o644)}]:
                with tempfile.TemporaryDirectory(dir=root) as dest:
                    with self.assertRaises(ValueError):unpack(path,Path(dest)/'out','candidate',inventory)

    def test_file_directory_conflicts_and_wrong_timestamps_fail_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'conflict.tar.gz'
            archive(path,'candidate',{'a':(b'x',0o644),'a/b':(b'y',0o644)},1)
            with self.assertRaises(ValueError):unpack(path,root/'conflict','candidate')
            self.assertFalse(list((root/'conflict').rglob('*')))
            path=root/'epoch.tar.gz';archive(path,'candidate',{'file':(b'x',0o644)},1)
            with self.assertRaises(ValueError):unpack(path,root/'epoch','candidate',epoch=2)
            self.assertFalse(list((root/'epoch').rglob('*')))


class Identity(unittest.TestCase):
    def test_snapshot_identity_and_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'original.txt').write_bytes(b'original snapshot\n')
            files={'original.txt':dict(sha256=hashlib.sha256((root/'original.txt').read_bytes()).hexdigest(),mode=0o644)}
            content=dict(schema=1,spdx_license_identifier='MIT',version='0.0.1-rc.1',base_commit='a'*40,source_commit=None,identity_role='uncommitted-provisional-snapshot',source_date_epoch=1,files=files)
            record=dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())
            (root/'SOURCE.json').write_bytes(canonical(record));source_record(root)
            (root/'original.txt').write_bytes(b'changed')
            with self.assertRaises(ValueError):source_record(root)
            (root/'original.txt').write_bytes(b'original snapshot\n');(root/'unexpected').write_text('extra')
            with self.assertRaises(ValueError):source_record(root)

    def test_payload_verification_rejects_mode_changes_and_special_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();files={};modes={}
            for name in FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original fixture')
                modes[name]=0o755 if name.startswith(('bin/','libexec/')) else 0o644
                path.chmod(modes[name]);files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            payload=Payload.__new__(Payload);payload.tree=root;payload.architecture='arm64'
            payload.manifest=dict(schema=2,files=files,file_modes=modes,candidate_version='0.0.1-rc.1')
            payload.source_identity=dict(source_commit=None,base_commit='a'*40,source_snapshot_sha256='b'*64);payload.manifest_sha256='c'*64
            payload.verify('test')
            path=root/'libexec/brewpi-emulator-rmx/wait-ready.py'
            for mode in [0o644,0o700]:
                path.chmod(mode)
                with self.assertRaises(ValueError):payload.verify('changed-mode')
            path.chmod(0o755);os.mkfifo(root/'unexpected-pipe')
            with self.assertRaises(ValueError):payload.verify('special-file')

    def test_saved_verifier_rejects_special_files_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);os.mkfifo(root/'freeze.json')
            with self.assertRaises(ValueError):verify_freeze(root)

    def test_assertion_disabled_release_verification_fails(self):
        with patch.dict(os.environ,{'PYTHONOPTIMIZE':'1'}):
            with self.assertRaises(RuntimeError):verify_freeze('unused')

    def test_provisional_snapshot_cannot_pretend_to_be_a_commit(self):
        manifest=dict(schema=2,source_commit=None,base_commit='a'*40,source_snapshot_sha256='b'*64)
        with patch.dict(os.environ,{'RMX_CANDIDATE_SNAPSHOT':'b'*64,'RMX_CANDIDATE_COMMIT':''}):
            self.assertIsNone(source_identity(manifest)['source_commit'])
            with self.assertRaises(ValueError):source_identity(dict(manifest,source_commit='a'*40))
            with self.assertRaises(ValueError):source_identity(dict(manifest,source_snapshot_sha256='c'*64))
        with patch.dict(os.environ,{'RMX_CANDIDATE_SNAPSHOT':'','RMX_CANDIDATE_COMMIT':'a'*40}):
            with self.assertRaises(ValueError):source_identity(manifest)

    def test_provisional_payload_rejects_wrong_source_base_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest.json'
            data=dict(schema=2,candidate_version='0.0.1-rc.1',architecture='arm64',source_commit=None,base_commit='a'*40,
                source_snapshot_sha256='b'*64,source_commit_role='pending-reviewed-commit-binding',application_version_output='brewpi-emulator-rmx 0.0.1-rc.1',
                files={name:'c'*64 for name in FILES},file_modes={name:(0o755 if name.startswith(('bin/','libexec/')) else 0o644) for name in FILES})
            manifest.write_text(json.dumps(data))
            with patch.dict(os.environ,{'RMX_CANDIDATE_SNAPSHOT':'b'*64,'RMX_CANDIDATE_COMMIT':''}),patch('artifacts.source_record',return_value=dict(source_snapshot_sha256='b'*64,base_commit='d'*40)):
                with self.assertRaisesRegex(ValueError,'provisional payload identity'):Payload(root/'tree',manifest,'arm64')

    def test_commit_identity_requires_commit_expectation_and_rejects_snapshot_mode(self):
        manifest=dict(schema=1,source_commit='a'*40)
        with patch.dict(os.environ,{'RMX_CANDIDATE_COMMIT':'a'*40,'RMX_CANDIDATE_SNAPSHOT':''}):
            self.assertEqual(source_identity(manifest),dict(source_commit='a'*40))
        for commit,snapshot in [('', ''),('', 'b'*64),('a'*40, 'b'*64),('c'*40, '')]:
            with self.subTest(commit=commit,snapshot=snapshot),patch.dict(os.environ,{'RMX_CANDIDATE_COMMIT':commit,'RMX_CANDIDATE_SNAPSHOT':snapshot}):
                with self.assertRaisesRegex(ValueError,'commit expectation'):source_identity(manifest)


class Reproducibility(unittest.TestCase):
    def test_missing_changed_or_failed_second_build_is_rejected(self):
        from native import SUITES
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);results=[]
            for label in ['first','second']:
                result=root/'builds/arm64'/label/'result';result.mkdir(parents=True);results.append(result)
                for name in ['brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz','brewpi-emulator-rmx-0.0.1-rc.1-linux-arm64.tar.gz','payload-manifest.json','build-manifest.json','packages.tsv','debs.sha256','indices.sha256']:
                    (result/name).write_bytes(b'original comparison fixture')
                (result/'native-results').mkdir()
                (result/'native-results/milestone3-fixtures.json').write_text(json.dumps(dict(counts=dict(passed=48,unresolved_reference_characterization=9))))
                (result/'build-results.json').write_text(json.dumps(dict(status='passed',native_suites=6,counts=dict(passed=48,unresolved_reference_characterization=9))))
                xml='<Site><Testing>'+''.join('<Test Status="passed"><Name>'+name+'</Name></Test>' for name in sorted(SUITES))+'</Testing></Site>'
                (result/'ctest.xml').write_text(xml)
                notices=result/'external-notices';notices.mkdir()
                for name in ['libc6','libc6-dev','libstdc++6','libgcc-s1','gcc-12-base']:(notices/(name+'-copyright.txt')).write_bytes(b'original notice-comparison fixture')
            compare_builds(root,'arm64')
            changed=results[1]/'packages.tsv';original=changed.read_bytes();changed.write_bytes(b'changed')
            with self.assertRaises(ValueError):compare_builds(root,'arm64')
            changed.unlink()
            with self.assertRaises(FileNotFoundError):compare_builds(root,'arm64')
            changed.write_bytes(original)
            xml=results[1]/'ctest.xml';xml.write_text(xml.read_text().replace('Status="passed"','Status="failed"',1))
            with self.assertRaises(ValueError):compare_builds(root,'arm64')


if __name__=='__main__':unittest.main()
