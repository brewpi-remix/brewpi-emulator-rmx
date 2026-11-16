# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative tests for final R4 evidence/source reconciliation."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from r4_review import capture, native_launch, packet_files, runtime_receipts, source_association
from evidence import RUNTIME_NAMES


class R4ReviewChecks(unittest.TestCase):
    def test_source_association_checks_git_bytes_and_modes(self):
        body=b'original MIT source fixture\n';commit='a'*40
        record=dict(source_snapshot_sha256='b'*64,files={'original.txt':dict(sha256=hashlib.sha256(body).hexdigest(),mode=0o644)})
        association=dict(status='passed',source_commit=commit,source_snapshot_sha256='b'*64,source_archive_sha256='c'*64,original_file_count=1)
        def git(args):return b'100644 blob fixture\toriginal.txt\0' if 'ls-tree' in args else body
        with patch('r4_review.subprocess.check_output',side_effect=git):
            source_association(record,association,Path('/unused'),commit,'c'*64)
            for key,value in [('sha256','d'*64),('mode',0o755)]:
                original=record['files']['original.txt'][key];record['files']['original.txt'][key]=value
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'differs from Git'):
                    source_association(record,association,Path('/unused'),commit,'c'*64)
                record['files']['original.txt'][key]=original
            with self.assertRaises(ValueError):source_association(record,association,Path('/unused'),'d'*40,'c'*64)

    def test_raw_capture_must_equal_extracted_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);directory=root/'reports';directory.mkdir();data=b'{"original":"report fixture"}\n';(directory/'report.json').write_bytes(data)
            archive=root/'capture.tar.gz'
            with tarfile.open(archive,'w:gz') as stream:
                member=tarfile.TarInfo('report.json');member.size=len(data);stream.addfile(member,io.BytesIO(data))
            capture(archive,directory)
            (directory/'report.json').write_bytes(b'edited passing summary')
            with self.assertRaises(ValueError):capture(archive,directory)
            (directory/'report.json').write_bytes(data);(directory/'extra.json').write_bytes(data)
            with self.assertRaises(ValueError):capture(archive,directory)

    def test_unsafe_and_duplicate_capture_members_fail(self):
        for name,kind,count in [('../escape',tarfile.REGTYPE,1),('link',tarfile.SYMTYPE,1),('report',tarfile.REGTYPE,2)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);directory=root/'reports';directory.mkdir();(directory/'report').write_bytes(b'x')
                archive=root/'capture.tar.gz'
                with tarfile.open(archive,'w:gz') as stream:
                    for _ in range(count):
                        member=tarfile.TarInfo(name);member.type=kind;member.size=1 if kind==tarfile.REGTYPE else 0
                        if kind==tarfile.SYMTYPE:member.linkname='/outside'
                        stream.addfile(member,io.BytesIO(b'x') if member.size else None)
                with self.assertRaises(ValueError):capture(archive,directory)

    def native(self):
        manifest=dict(source_snapshot_sha256='a'*64)
        launch=dict(status='passed',exit_code=0,error=None,architecture='amd64',native_machine='x86_64',role='qualification',cleanup_verified=True,remaining_owned_pids=[],source_snapshot_sha256='a'*64,started_utc=1,finished_utc=2,sanitizer_process_no_aslr=True)
        namespace=dict(host_machine='x86_64',private_mounts=True,private_network=True,private_tool_filesystem=True,source_payload_references_readonly=True,physical_devices=False,systemd_activation=False,sanitizer_process_no_aslr=True)
        return manifest,launch,namespace

    def test_native_proof_rejects_emulation_stale_inputs_and_unclean_exit(self):
        manifest,launch,namespace=self.native();native_launch(launch,namespace,manifest,'qualification',True)
        for key,value in [('native_machine','aarch64'),('source_snapshot_sha256','b'*64),('exit_code',1),('remaining_owned_pids',[123]),('finished_utc',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):native_launch(dict(launch,**{key:value}),namespace,manifest,'qualification',True)

    def test_sanitizer_condition_and_isolation_cannot_be_relabelled(self):
        manifest,launch,namespace=self.native()
        with self.assertRaises(ValueError):native_launch(launch,namespace,manifest,'qualification',False)
        with self.assertRaises(ValueError):native_launch(launch,dict(namespace,private_network=False),manifest,'qualification',True)

    def test_runtime_receipts_bind_full_source_identity_and_account(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=dict(base_commit='a'*40,source_snapshot_sha256='b'*64,files={'original-file':'c'*64})
            report=dict(status='passed',checks=[dict(name=n,status='passed',details={'uid':2001,'gid':2001}) for n in RUNTIME_NAMES])
            (root/'runtime-results.json').write_text(json.dumps(report));(root/'clean-environment.json').write_text(json.dumps(dict(status='passed',compiler_linker_build_tools_absent=True)))
            row=dict(mode='packaged-input',phase='runtime-process-start',manifest_sha256='d'*64,source_commit=None,base_commit='a'*40,source_snapshot_sha256='b'*64,candidate_version='0.0.1-rc.1',architecture='amd64',files=manifest['files'])
            receipt=root/'payload-execution.jsonl';receipt.write_text(json.dumps(row)+'\n');runtime_receipts(root,manifest,'d'*64)
            for key,value in [('source_commit','a'*40),('base_commit','e'*40),('candidate_version','0.0.1'),('phase','after-runtime')]:
                receipt.write_text(json.dumps(dict(row,**{key:value}))+'\n')
                with self.subTest(key=key),self.assertRaises(ValueError):runtime_receipts(root,manifest,'d'*64)
            receipt.write_text(json.dumps(row)+'\n');report['checks'][0]['details']['uid']=0;(root/'runtime-results.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError):runtime_receipts(root,manifest,'d'*64)

    def test_packet_inventory_and_checksums_are_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            names=['acceptance.json','source-association.json','minimum-tools.json','sanitizer-environment.json','hosted-ci-verification.json']
            for name in names:(root/name).write_bytes(b'original fixture')
            (root/'SHA256SUMS').write_text(''.join(hashlib.sha256(b'original fixture').hexdigest()+'  '+n+'\n' for n in names))
            packet_files(root);(root/'acceptance.json').write_bytes(b'changed')
            with self.assertRaises(ValueError):packet_files(root)
            (root/'acceptance.json').write_bytes(b'original fixture');(root/'unexpected').write_bytes(b'x')
            with self.assertRaises(ValueError):packet_files(root)


if __name__=='__main__':unittest.main()
