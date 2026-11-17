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
import struct
import stat
import subprocess
import zipfile
from unittest.mock import patch
from artifacts import archive, unpack, canonical, source_record, source_names, verify_original_files, safe_name, VERSION as CURRENT_VERSION, STEM
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/ci'))
from payload import source_identity
from payload import Payload, FILES, LOCAL_CONTROLS_FILES, payload_files
from local import compare_builds, verify_freeze
from macos import FILES as MACOS_FILES, inventory as macos_inventory, macho, pack as macos_pack, verify_archive as macos_verify_archive
from macos import verify as verify_macos, notarize


from windows import FILES as WINDOWS_FILES, pe as windows_pe, inventory as windows_inventory
from windows import archive as windows_archive, verify_zip as windows_verify_zip


class WindowsArchives(unittest.TestCase):
    def test_portable_archive_names_reject_windows_devices_drives_and_aliases(self):
        for path in ['candidate/C:/outside','candidate/file:stream','candidate/src/NUL.txt',
                     'candidate/src/com1','candidate/AUX .txt','candidate/CLOCK$.txt','candidate/LPT¹.log','candidate/trailing.',
                     'candidate/trailing ','candidate/line\nname']:
            with self.subTest(path=path),self.assertRaises(ValueError):safe_name(path)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive_path=root/'invalid.tar.gz'
            with tarfile.open(archive_path,'w:gz') as output:
                for name in ['candidate/ordinary.txt','candidate/C:/outside']:
                    item=tarfile.TarInfo(name);item.mode=0o644;item.size=1
                    output.addfile(item,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):unpack(archive_path,root/'output','candidate')
            self.assertEqual(list((root/'output').iterdir()),[])

    def test_source_archive_rejects_case_and_unicode_aliases_before_writes(self):
        for names in [['candidate/name','candidate/NAME'],
                      ['candidate/caf\u00e9','candidate/cafe\u0301'],
                      ['candidate/PARENT','candidate/parent/child']]:
            with self.subTest(names=names),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);path=root/'bad.tar.gz'
                with tarfile.open(path,'w:gz') as output:
                    for name in names:
                        item=tarfile.TarInfo(name);item.mode=0o644;item.size=1
                        output.addfile(item,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):unpack(path,root/'output','candidate')
                self.assertEqual(list((root/'output').iterdir()),[])

    def test_complete_windows_archives_reproduce_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tree=root/'payload'
            for name in WINDOWS_FILES:
                path=tree/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(('Original Windows package fixture '+name+'\n').encode())
            rows=windows_inventory(tree)
            for name in ['first.zip','second.zip']:
                windows_archive(tree,root/name,'candidate',rows,1234567890)
                windows_verify_zip(root/name,'candidate',rows)
            self.assertEqual((root/'first.zip').read_bytes(),(root/'second.zip').read_bytes())
            rows['bin/brewpi-emulator-rmx.exe']['sha256']='0'*64
            with self.assertRaises(ValueError):windows_verify_zip(root/'first.zip','candidate',rows)
            extra=tree/'unexpected.dll';extra.write_bytes(b'original invalid fixture')
            with self.assertRaises(ValueError):windows_inventory(tree)

    def test_pe_parser_checks_cpu_signature_and_bounded_imports(self):
        # Independently constructed PE metadata; no compiler/reference bytes.
        data=bytearray(2048);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80)
        data[0x80:0x84]=b'PE\0\0'
        struct.pack_into('<HH',data,0x84,0x8664,1)
        struct.pack_into('<HH',data,0x94,240,2)
        optional=0x98;struct.pack_into('<H',data,optional,0x20b)
        struct.pack_into('<H',data,optional+68,3)
        struct.pack_into('<I',data,optional+108,16)
        struct.pack_into('<II',data,optional+120,0x1000,40)
        section=optional+240
        struct.pack_into('<III',data,section+12,0x1000,1024,512)
        struct.pack_into('<I',data,512+12,0x1080)
        data[640:653]=b'KERNEL32.dll\0'
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'original-pe-fixture';binary.write_bytes(data)
            self.assertEqual(windows_pe(binary),['KERNEL32.DLL'])
            for offset,value,kind in [(0x84,0xaa64,'<H'),(optional+68,2,'<H'),
                                       (optional+144,1,'<I'),(optional+120,0xffffff00,'<I'),
                                       (optional+216,0x1000,'<I')]:
                changed=bytearray(data);struct.pack_into(kind,changed,offset,value);binary.write_bytes(changed)
                with self.assertRaises(ValueError):windows_pe(binary)
            changed=bytearray(data);changed[640:653]=b'UNKNOWNX.dll\0';binary.write_bytes(changed)
            with self.assertRaisesRegex(ValueError,'unreviewed imported'):windows_pe(binary)


class MacOSArchives(unittest.TestCase):
    def test_notarization_auth_failure_does_not_reserve_an_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            failure=subprocess.CalledProcessError(69,['original-credential-probe'])
            with patch('macos.verify',return_value={}),patch('macos.subprocess.run',side_effect=failure),patch('macos.subprocess.check_output') as upload:
                with self.assertRaises(subprocess.CalledProcessError):
                    notarize(root,'original-test-profile')
                upload.assert_not_called()
            self.assertFalse((root/'notarization-request.json').exists())

    def test_ambiguous_notarization_failure_keeps_request_and_prevents_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'macos-manifest.json').write_text('{}')
            manifest=dict(archive_sha256='a'*64,archive='original-test.zip')
            with patch('macos.verify',return_value=manifest),patch('macos.subprocess.run'),patch('macos.subprocess.check_output',side_effect=subprocess.TimeoutExpired('original-upload',120)) as upload:
                with self.assertRaises(subprocess.TimeoutExpired):
                    notarize(root,'original-test-profile')
                self.assertTrue((root/'notarization-request.json').exists())
                with self.assertRaisesRegex(ValueError,'submission already exists'):
                    notarize(root,'original-test-profile')
                self.assertEqual(upload.call_count,1)

    def test_source_expectation_is_required_before_native_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            manifest=dict(schema=4,producer='local-native-build',profile='macos-arm64-local-controls-v2',
                          os='macos',architecture='arm64',version=CURRENT_VERSION,source_commit=None,
                          identity_role='uncommitted-provisional-snapshot',base_commit='a'*40,
                          source_snapshot_sha256='b'*64,source_archive_sha256='c'*64)
            (root/'macos-manifest.json').write_text(json.dumps(manifest))
            with patch('macos.native'),patch('macos.subprocess.run',side_effect=AssertionError('native execution must remain gated')):
                for expected in [None,'d'*64]:
                    with self.assertRaisesRegex(ValueError,'expected source snapshot'):
                        verify_macos(root,expected_snapshot=expected)

    def payload(self, root):
        for name in MACOS_FILES:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(('Original test payload: '+name+'\n').encode())
            p.chmod(0o755 if name.startswith(('bin/','libexec/')) else 0o644)

    def test_native_archives_are_deterministic_and_bind_every_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tree=root/'payload';self.payload(tree)
            rows=macos_pack(tree,root/'first.zip','candidate',1234567890)
            macos_pack(tree,root/'second.zip','candidate',1234567890)
            self.assertEqual((root/'first.zip').read_bytes(),(root/'second.zip').read_bytes())
            macos_verify_archive(root/'first.zip','candidate',rows)
            rows['bin/brewpi-emulator-rmx']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'bytes differ'):
                macos_verify_archive(root/'first.zip','candidate',rows)

    def test_native_archives_reject_missing_duplicate_and_symlink_members(self):
        for mutation in ['missing','duplicate','symlink']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);tree=root/'payload';self.payload(tree)
                rows=macos_pack(tree,root/'base.zip','candidate',1234567890)
                with zipfile.ZipFile(root/'base.zip') as source,zipfile.ZipFile(root/'bad.zip','w') as bad:
                    for i,member in enumerate(source.infolist()):
                        if mutation=='missing' and i==0:continue
                        if mutation=='symlink' and i==0:member.external_attr=(stat.S_IFLNK|0o755)<<16
                        bad.writestr(member,source.read(member.filename))
                        if mutation=='duplicate' and i==0:
                            import warnings
                            with warnings.catch_warnings():
                                warnings.simplefilter('ignore',UserWarning)
                                bad.writestr(member,source.read(member.filename))
                with self.assertRaises(ValueError):macos_verify_archive(root/'bad.zip','candidate',rows)

    def test_native_payload_rejects_linux_service_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tree=root/'payload';self.payload(tree)
            extra=tree/'share/brewpi-emulator-rmx/systemd/service';extra.parent.mkdir(parents=True);extra.write_text('original test\n')
            with self.assertRaises(ValueError):macos_inventory(tree)
            extra.unlink();(tree/'link').symlink_to(tree/'bin/brewpi-emulator-rmx')
            with self.assertRaises(ValueError):macos_inventory(tree)

    def test_macho_rejects_wrong_cpu_platform_and_truncated_load_commands(self):
        header=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,1,24,0,0)
        build=struct.pack('<6I',0x32,24,1,27<<16,27<<16,0)
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'original-macho-fixture';binary.write_bytes(header+build)
            macho(binary)
            variants=[b'\x7fELF'+bytes(60),b'MZ'+bytes(62),header+build[:-1],
                      struct.pack('<8I',0xfeedfacf,0x1000007,0,2,1,24,0,0)+build,
                      header+struct.pack('<6I',0x32,24,2,15<<16,27<<16,0),
                      header+struct.pack('<6I',0x32,24,1,26<<16,27<<16,0)]
            for data in variants:
                binary.write_bytes(data)
                with self.assertRaises(ValueError):macho(binary)

    def test_zip_size_limits_apply_before_payload_decompression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tree=root/'payload';self.payload(tree)
            rows=macos_pack(tree,root/'base.zip','candidate',1234567890)
            with patch('macos.MAX_MEMBER_BYTES',1),patch.object(zipfile.ZipFile,'open',side_effect=AssertionError('member must not be decompressed')):
                with self.assertRaisesRegex(ValueError,'size limit'):
                    macos_verify_archive(root/'base.zip','candidate',rows)
            with patch('macos.MAX_ARCHIVE_BYTES',1),patch('macos.zipfile.ZipFile',side_effect=AssertionError('archive must not be opened')):
                with self.assertRaisesRegex(ValueError,'size limit'):
                    macos_verify_archive(root/'base.zip','candidate',rows)


class Archives(unittest.TestCase):
    def test_source_list_requires_install_documents_and_template(self):
        project=Path(__file__).resolve().parents[1]
        names=source_names(project)
        for missing in ['docs/operation.txt','LICENSE.md','systemd/brewpi-emulator@.service.in']:
            with self.subTest(missing=missing),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);(root/'release').mkdir()
                (root/'release/source-files.txt').write_text('\n'.join(n for n in names if n!=missing)+'\n')
                with self.assertRaisesRegex(ValueError,'omits install inputs'):
                    source_names(root)

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
    def test_external_legal_text_cannot_be_relabelled_as_original_mit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'cmake').mkdir();(root/'release/notices').mkdir(parents=True)
            (root/'cmake/version.cmake').write_bytes((Path(__file__).resolve().parents[1]/'cmake/version.cmake').read_bytes())
            legal='release/notices/LLVM-LICENSE.txt';(root/legal).write_text('Original synthetic legal-classification fixture\n')
            files={name:dict(sha256=hashlib.sha256((root/name).read_bytes()).hexdigest(),mode=0o644) for name in ['cmake/version.cmake',legal]}
            content=dict(schema=1,spdx_license_identifier='MIT',version=CURRENT_VERSION,base_commit='a'*40,source_commit=None,identity_role='uncommitted-provisional-snapshot',source_date_epoch=1,files=files)
            def save():
                (root/'SOURCE.json').write_bytes(canonical(dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())))
            save()
            with self.assertRaisesRegex(ValueError,'separate provenance'):source_record(root)
            content.update(license_scope='original-project-material-only',external_legal_texts={legal:dict(origin='https://llvm.org/LICENSE.txt',spdx_license_expression='Apache-2.0 WITH LLVM-exception',sha256=files[legal]['sha256'],purpose='verbatim external legal text; not original MIT prose')})
            save();source_record(root)
            content['external_legal_texts'][legal]['spdx_license_expression']='MIT';save()
            with self.assertRaisesRegex(ValueError,'separate provenance'):source_record(root)

    def test_archived_version_requires_explicit_expectation_and_matches_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'cmake').mkdir()
            name='cmake/version.cmake'
            text='set(RMX_VERSION_MAJOR 0)\nset(RMX_VERSION_MINOR 0)\nset(RMX_VERSION_PATCH 1)\nset(RMX_VERSION_PRERELEASE "rc.1")\n'
            (root/name).write_text(text)
            files={name:dict(sha256=hashlib.sha256(text.encode()).hexdigest(),mode=0o644)}
            content=dict(schema=1,spdx_license_identifier='MIT',version='0.0.1-rc.1',base_commit='a'*40,source_commit=None,identity_role='uncommitted-provisional-snapshot',source_date_epoch=1,files=files)
            def save():
                record=dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())
                (root/'SOURCE.json').write_bytes(canonical(record))
            save()
            with self.assertRaises(ValueError):source_record(root)
            self.assertEqual(source_record(root,expected_version='0.0.1-rc.1')['version'],'0.0.1-rc.1')
            content['version']=CURRENT_VERSION;save()
            with self.assertRaisesRegex(ValueError,'archived application metadata'):source_record(root)

    def test_snapshot_identity_and_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'original.txt').write_bytes(b'original snapshot\n')
            (root/'cmake').mkdir();(root/'cmake/version.cmake').write_bytes((Path(__file__).resolve().parents[1]/'cmake/version.cmake').read_bytes())
            files={name:dict(sha256=hashlib.sha256((root/name).read_bytes()).hexdigest(),mode=0o644) for name in ['original.txt','cmake/version.cmake']}
            content=dict(schema=1,spdx_license_identifier='MIT',version=CURRENT_VERSION,base_commit='a'*40,source_commit=None,identity_role='uncommitted-provisional-snapshot',source_date_epoch=1,files=files)
            record=dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())
            (root/'SOURCE.json').write_bytes(canonical(record));source_record(root)
            (root/'original.txt').write_bytes(b'changed')
            with self.assertRaises(ValueError):source_record(root)
            (root/'original.txt').write_bytes(b'original snapshot\n');(root/'unexpected').write_text('extra')
            with self.assertRaises(ValueError):source_record(root)

    def test_rehashed_snapshot_cannot_omit_version_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            content=dict(schema=1,spdx_license_identifier='MIT',version=CURRENT_VERSION,base_commit='a'*40,source_commit=None,identity_role='uncommitted-provisional-snapshot',source_date_epoch=1,files={})
            record=dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())
            (root/'SOURCE.json').write_bytes(canonical(record))
            with self.assertRaisesRegex(ValueError,'omits application version metadata'):source_record(root)

    def test_payload_verification_rejects_mode_changes_and_special_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();files={};modes={}
            for name in FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original fixture')
                modes[name]=0o755 if name.startswith(('bin/','libexec/')) else 0o644
                path.chmod(modes[name]);files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            payload=Payload.__new__(Payload);payload.tree=root;payload.architecture='arm64'
            payload.manifest=dict(schema=2,files=files,file_modes=modes,candidate_version=CURRENT_VERSION)
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

    def test_saved_verifier_preserves_unsigned_and_pending_acceptance(self):
        metadata=dict(schema=1,status='frozen-provisional-review-required',version=CURRENT_VERSION,source_commit=None,source_commit_role='pending-reviewed-commit-binding',unsigned=True,license_audit_accepted=False,sustained_testing_started=False)
        invalid=[dict(unsigned=value) for value in [False,'true',1]]
        invalid += [dict(license_audit_accepted=True),dict(sustained_testing_started=True),dict(r5_accepted=True),dict(r3_started=True),dict(r5_accepted=0),dict(r3_started='false')]
        for fields in invalid:
            with self.subTest(fields=fields),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'freeze.json').write_bytes(canonical(dict(metadata,**fields)))
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
            data=dict(schema=2,candidate_version=CURRENT_VERSION,architecture='arm64',source_commit=None,base_commit='a'*40,
                source_snapshot_sha256='b'*64,source_commit_role='pending-reviewed-commit-binding',application_version_output='brewpi-emulator-rmx '+CURRENT_VERSION,
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
                for name in [STEM+'-source.tar.gz',STEM+'-linux-arm64.tar.gz','payload-manifest.json','build-manifest.json','packages.tsv','debs.sha256','indices.sha256']:
                    (result/name).write_bytes(b'original comparison fixture')
                (result/'native-results').mkdir()
                (result/'native-results/fixtures.json').write_text(json.dumps(dict(counts=dict(passed=48,unresolved_reference_characterization=9))))
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


class PayloadProfiles(unittest.TestCase):
    def test_verbatim_project_files_must_match_archived_originals(self):
        originals={'scripts/wait-ready.py','scripts/lcd-viewer.py','LICENSE.md','THIRD_PARTY_NOTICES.md','docs/operation.txt'}
        for profile,files in [('core-v1',FILES),('local-controls-v1',LOCAL_CONTROLS_FILES)]:
            with self.subTest(profile=profile):
                manifest=dict(payload_profile=profile,files={n:'a'*64 for n in files})
                record=dict(files={n:dict(sha256='a'*64) for n in originals})
                verify_original_files(manifest,record)
                for original in originals-({'scripts/lcd-viewer.py'} if profile=='core-v1' else set()):
                    record['files'][original]['sha256']='b'*64
                    with self.assertRaisesRegex(ValueError,'installed original differs'):verify_original_files(manifest,record)
                    record['files'][original]['sha256']='a'*64
                del record['files']['scripts/wait-ready.py']
                with self.assertRaises(ValueError):verify_original_files(manifest,record)

    def test_profiles_preserve_original_inventory_and_require_explicit_controls(self):
        self.assertEqual(payload_files(dict(schema=2)),FILES)
        self.assertEqual(payload_files(dict(schema=2,payload_profile='local-controls-v1')),LOCAL_CONTROLS_FILES)
        for m in [dict(schema=1,payload_profile='local-controls-v1'),dict(schema=2,payload_profile='arbitrary')]:
            with self.assertRaises(ValueError):payload_files(m)

    def test_controls_inventory_requires_exact_helper_bytes_and_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();files={};modes={}
            for name in LOCAL_CONTROLS_FILES:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'original inventory test data')
                modes[name]=0o755 if name.startswith(('bin/','libexec/')) else 0o644;p.chmod(modes[name]);files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
            payload=Payload.__new__(Payload);payload.tree=root;payload.architecture='arm64';payload.source_identity={};payload.manifest_sha256='c'*64
            payload.manifest=dict(schema=2,payload_profile='local-controls-v1',candidate_version=CURRENT_VERSION,files=files,file_modes=modes)
            payload.verify('test')
            helper=root/'libexec/brewpi-emulator-rmx/lcd-viewer.py';original=helper.read_bytes()
            helper.write_bytes(b'changed')
            with self.assertRaises(ValueError):payload.verify('test')
            helper.write_bytes(original);helper.chmod(0o644)
            with self.assertRaises(ValueError):payload.verify('test')
            helper.chmod(0o755);payload.manifest.pop('payload_profile')
            with self.assertRaises(ValueError):payload.verify('test')


class ControlsQualificationEvidence(unittest.TestCase):
    def test_integration_requires_supported_profile_and_exact_inventory(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/qualification'))
        from evidence import input_evidence
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=root/'manifest.json'
            m=dict(schema=2,payload_profile='local-controls-v1',source_commit=None,base_commit='a'*40,
                source_snapshot_sha256='b'*64,candidate_version=CURRENT_VERSION,architecture='arm64',files={n:'a'*64 for n in LOCAL_CONTROLS_FILES})
            def save():
                manifest.write_text(json.dumps(m));identity=dict(mode='packaged-input',source_commit=None,base_commit='a'*40,
                    source_snapshot_sha256='b'*64,candidate_version=CURRENT_VERSION,architecture='arm64',files=m['files'],
                    manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
                (root/'execution-input.json').write_text(json.dumps(dict(mode='packaged-input',sha256='a'*64,executable='/payload/bin/brewpi-emulator-rmx')))
                (root/'executable-hashes.jsonl').write_text(''.join(json.dumps(dict(phase=p,sha256='a'*64))+'\n' for p in ['restart-1','restart-2','restart-3','after-integration']))
                (root/'payload-execution.jsonl').write_text(''.join(json.dumps(dict(identity,phase=p))+'\n' for p in ['before-integration','restart-1','restart-2','restart-3','after-integration']))
            with patch.dict(os.environ,RMX_EXECUTION_MODE='packaged-input',RMX_PAYLOAD_MANIFEST=str(manifest),RMX_CANDIDATE_SNAPSHOT='b'*64,RMX_CANDIDATE_COMMIT=''):
                save();input_evidence(root,'integration')
                m['payload_profile']='unknown';save()
                with self.assertRaisesRegex(ValueError,'unsupported payload profile'):input_evidence(root,'integration')
                m['payload_profile']='local-controls-v1';del m['files']['libexec/brewpi-emulator-rmx/lcd-viewer.py'];save()
                with self.assertRaisesRegex(ValueError,'declared payload inventory'):input_evidence(root,'integration')

    def test_seven_file_qualification_is_explicit_and_identity_bound(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/qualification'))
        from evidence import input_evidence
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=root/'manifest.json';files={n:'a'*64 for n in LOCAL_CONTROLS_FILES}
            m=dict(schema=2,payload_profile='local-controls-v1',source_commit=None,base_commit='a'*40,source_snapshot_sha256='b'*64,candidate_version=CURRENT_VERSION,architecture='arm64',files=files)
            manifest.write_text(json.dumps(m));digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
            identity=dict(mode='packaged-input',source_commit=None,base_commit='a'*40,source_snapshot_sha256='b'*64,candidate_version=CURRENT_VERSION,architecture='arm64',files=files,manifest_sha256=digest)
            (root/'execution-input.json').write_text(json.dumps(dict(mode='packaged-input',architecture='arm64',files=files)))
            (root/'installed-integrity.json').write_text(json.dumps(dict(status='passed',files=files)))
            (root/'payload-execution.jsonl').write_text(''.join(json.dumps(dict(identity,phase=p))+'\n' for p in ['before-runtime','service-start','service-end','after-runtime']))
            (root/'runtime-results').mkdir();(root/'runtime-results/payload-execution.jsonl').write_text(json.dumps(dict(identity,phase='runtime-process-start'))+'\n')
            with patch.dict(os.environ,RMX_EXECUTION_MODE='packaged-input',RMX_PAYLOAD_MANIFEST=str(manifest),RMX_CANDIDATE_SNAPSHOT='b'*64,RMX_CANDIDATE_COMMIT=''):
                input_evidence(root,'qualification')
                m.pop('payload_profile');manifest.write_text(json.dumps(m))
                with self.assertRaises(ValueError):input_evidence(root,'qualification')


def load_tests(loader, tests, pattern):
    # Include native package boundary checks in the helper suite.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests/qualification'))
    tests.addTests(loader.loadTestsFromName('native_package_checks'))
    return tests


if __name__=='__main__':unittest.main()
