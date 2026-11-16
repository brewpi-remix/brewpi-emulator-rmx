# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative tests for the native package isolation boundary."""
import json
import sys
import hashlib
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import native_package
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ci'))
from version import application_version
CURRENT_VERSION=application_version(Path(__file__).resolve().parents[2])


class NativeBoundary(unittest.TestCase):
    def inputs(self, base):
        (base/'source').mkdir()
        (base/'source/cmake').mkdir()
        (base/'source/cmake/version.cmake').write_bytes((Path(__file__).resolve().parents[2]/'cmake/version.cmake').read_bytes())
        manifest=dict(schema=2,candidate_version=CURRENT_VERSION,architecture='amd64',base_commit='a'*40,source_snapshot_sha256='b'*64)
        (base/'candidate.json').write_text(json.dumps(manifest))
        (base/'source/SOURCE.json').write_text(json.dumps(dict(version=CURRENT_VERSION,base_commit='a'*40,source_snapshot_sha256='b'*64)))
        request=dict(candidate_version=CURRENT_VERSION,purpose='native packaged qualification',architecture='amd64',source_commit='a'*40,source_snapshot_sha256='b'*64,
            manifest_sha256=hashlib.sha256((base/'candidate.json').read_bytes()).hexdigest(),
            native_wrapper_sha256=hashlib.sha256(Path(native_package.__file__).read_bytes()).hexdigest())
        (base/'request.json').write_text(json.dumps(request));return request

    def test_request_is_bound_to_manifest_source_and_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);request=self.inputs(base)
            native_package.validate_request(base,Path(native_package.__file__),'qualification')
            for key in ['source_snapshot_sha256','manifest_sha256','native_wrapper_sha256']:
                bad=dict(request);bad[key]='c'*len(bad[key]);(base/'request.json').write_text(json.dumps(bad))
                with self.subTest(key=key),self.assertRaises(ValueError):native_package.validate_request(base,Path(native_package.__file__),'qualification')
            # A baseline and a later reviewed commit are distinct roles. The
            # offline Git association verifies this claim, not this preflight.
            (base/'request.json').write_text(json.dumps(dict(request,source_commit='c'*40)))
            native_package.validate_request(base,Path(native_package.__file__),'qualification')
            (base/'request.json').write_text(json.dumps(request))
            (base/'source/SOURCE.json').write_text(json.dumps(dict(base_commit='a'*40,source_snapshot_sha256='c'*64)))
            with self.assertRaises(ValueError):native_package.validate_request(base,Path(native_package.__file__),'qualification')

    def test_sanitizer_request_is_boolean_and_role_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);request=self.inputs(base)
            for flag,role in [('false','qualification'),(True,'runtime'),(True,'integration')]:
                (base/'request.json').write_text(json.dumps(dict(request,sanitizer_process_no_aslr=flag)))
                with self.subTest(flag=flag,role=role),self.assertRaises(ValueError):native_package.validate_request(base,Path(native_package.__file__),role)

    def test_request_version_must_match_all_staged_inputs(self):
        for target in ['request','record','cmake','manifest','expectation']:
            with self.subTest(target=target),tempfile.TemporaryDirectory() as temporary:
                base=Path(temporary);request=self.inputs(base)
                other='9.8.7'
                if target=='request':request['candidate_version']=other
                elif target=='record':
                    path=base/'source/SOURCE.json';record=json.loads(path.read_text());record['version']=other;path.write_text(json.dumps(record))
                elif target=='cmake':
                    (base/'source/cmake/version.cmake').write_text('set(RMX_VERSION_MAJOR 9)\nset(RMX_VERSION_MINOR 8)\nset(RMX_VERSION_PATCH 7)\nset(RMX_VERSION_PRERELEASE "")\n')
                elif target=='manifest':
                    path=base/'candidate.json';record=json.loads(path.read_text());record['candidate_version']=other;path.write_text(json.dumps(record))
                    request['manifest_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                (base/'request.json').write_text(json.dumps(request))
                with self.assertRaises(ValueError):native_package.validate_request(base,Path(native_package.__file__),'qualification',other if target=='expectation' else None)
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);request=self.inputs(base);request.pop('candidate_version')
            (base/'request.json').write_text(json.dumps(request))
            with self.assertRaises(ValueError):native_package.validate_request(base,Path(native_package.__file__),'qualification')

    def test_ctest_shim_module_imports_without_source_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);(base/'native_package.py').write_bytes(Path(native_package.__file__).read_bytes())
            result=subprocess.run([sys.executable,'-I','-c','import sys;sys.path.insert(0,sys.argv[1]);from native_package import ctest_command;assert ctest_command("/lab",[])==["/usr/bin/ctest"]',str(base)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_aslr_workaround_is_only_for_exact_sanitizer_tree(self):
        arguments=['-T','Test','--output-on-failure']
        self.assertEqual(native_package.ctest_command('/qualification/build-sanitize',arguments),
            ['/usr/bin/setarch','x86_64','-R','/usr/bin/ctest',*arguments])
        for directory in ['/qualification/build-release','/lab/build','/qualification/build-sanitize-other']:
            self.assertEqual(native_package.ctest_command(directory,arguments),['/usr/bin/ctest',*arguments])

    def test_inside_requires_private_root_pid_one_before_mounting(self):
        for uid,pid in [(501,1),(0,23)]:
            with self.subTest(uid=uid,pid=pid),patch('native_package.os.geteuid',return_value=uid),patch('native_package.os.getpid',return_value=pid),patch('native_package.command') as command:
                with self.assertRaisesRegex(RuntimeError,'private root-provisioned'):
                    native_package.inside(Path('/unused'),'integration')
                command.assert_not_called()

    def test_non_native_request_cannot_provision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'request.json').write_text(json.dumps(dict(purpose='native packaged qualification',architecture='amd64')))
            if os.geteuid()==0:os.chown(root,1000,1000)
            with patch('native_package.os.geteuid',return_value=0),patch('native_package.platform.machine',return_value='aarch64'),patch('native_package.command') as command:
                with self.assertRaises(RuntimeError):native_package.launch(root,'integration')
                command.assert_not_called();self.assertFalse((root/'integration').exists())

    def test_tool_symlink_is_dereferenced_before_private_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent=Path(temporary);base=parent/'request';base.mkdir();tools=parent/'external-tools';tools.mkdir()
            (tools/'original').write_bytes(b'external original remains unchanged')
            (base/'tools').symlink_to(tools,target_is_directory=True)
            self.inputs(base)
            if os.geteuid()==0:os.chown(base,1000,1000)
            handlers={sig:native_package.signal.getsignal(sig) for sig in [native_package.signal.SIGTERM,native_package.signal.SIGINT]}
            with patch('native_package.os.geteuid',return_value=0),patch('native_package.platform.machine',return_value='x86_64'),patch('native_package.command',side_effect=RuntimeError('stop before copy')) as command:
                self.assertEqual(native_package.launch(base,'qualification'),1)
                command.assert_called_once_with('cp','-a','--reflink=auto',tools.resolve(),base/'qualification/rootfs')
                report=json.loads((base/'qualification/native-launcher.json').read_text())
                self.assertEqual(report['status'],'failed');self.assertTrue(report['cleanup_verified'])
                self.assertIn('stop before copy',report['error'])
            self.assertEqual(handlers,{sig:native_package.signal.getsignal(sig) for sig in handlers})
            self.assertEqual((tools/'original').read_bytes(),b'external original remains unchanged')


if __name__=='__main__':unittest.main()
