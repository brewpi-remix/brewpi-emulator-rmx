# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative tests of provenance classification and distribution integrity."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import r5_audit as audit
from artifacts import STEM, archive


class Classification(unittest.TestCase):
    def test_only_selected_members_count(self):
        text='librmx_protocol.a(engine.cpp.o)\nAs-needed library included\nLOAD /unselected/libc_nonshared.a\n'
        self.assertEqual(len(audit.members(text)),1)
        self.assertEqual(audit.members(text)[0]['classification'],'original-MIT')

    def test_unknown_archive_or_runtime_member_fails(self):
        for value in ['foreign.a(x.o)','/usr/lib/gcc/other/12/libgcc.a(ldadd_4_4.o)',
                      '/usr/lib/gcc/aarch64-linux-gnu/12/libgcc.a(unreviewed.o)']:
            with self.subTest(value=value),self.assertRaises(ValueError):audit.members(value)
        with self.assertRaises(ValueError):audit.members('LOAD /unselected/libc_nonshared.a')

    def test_outline_atomics_have_separate_terms(self):
        self.assertEqual(audit.members('/usr/lib/gcc/aarch64-linux-gnu/12/libgcc.a(lse-init.o)')[0]['classification'],'GCC-runtime-exception-3.1')

    def test_header_providers_complete_and_unique(self):
        self.assertEqual(audit.owners('libc6-dev:arm64: /usr/include/a.h',{'/usr/include/a.h':'x'}),{'/usr/include/a.h':'libc6-dev:arm64'})
        for text in ['', 'foreign: /usr/include/a.h','libc6-dev:arm64: /unexpected',
                     'libc6-dev:arm64: /usr/include/a.h\nlibc6-dev:arm64: /usr/include/a.h']:
            with self.subTest(text=text),self.assertRaises(ValueError):audit.owners(text,{'/usr/include/a.h':'x'})

    def test_wrong_binary_identity_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'audit.json').write_text('{"status":"passed","architecture":"wrong"}')
            with self.assertRaises(ValueError):audit.binary_components(root,{'architecture':'arm64'})

    def test_wrong_or_unsafe_source_package_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dsc=root/'glibc_2.36-9+deb12u14.dsc'
            dsc.write_text('\nSource: other\nVersion: 2.36-9+deb12u14\n')
            with self.assertRaises(ValueError):audit.glibc_source(root)
            dsc.write_text('\nSource: glibc\nVersion: 2.36-9+deb12u14\nChecksums-Sha256:\n '+'0'*64+' 1 ../escape\nFiles:\n')
            with self.assertRaisesRegex(ValueError,'unsafe'):audit.glibc_source(root)
            dsc.write_text(dsc.read_text().replace('../escape','missing.tar.xz'))
            with self.assertRaisesRegex(ValueError,'checksum'):audit.glibc_source(root)


class Distribution(unittest.TestCase):
    def fixture(self,root):
        candidate=root/'candidate';candidate.mkdir();output=root/'output';output.mkdir()
        for kind in ['source','linux-arm64','linux-amd64']:(candidate/(STEM+'-'+kind+'.tar.gz')).write_bytes(b'original fixture')
        def build(_candidate,_evidence,destination):
            destination.mkdir()
            for path in candidate.iterdir():(destination/path.name).write_bytes(path.read_bytes())
            members={}
            for kind in ['NOTICES','glibc-source']:
                entries={'original-fixture.txt':(b'original test fixture',0o644)}
                archive(destination/(STEM+'-'+kind+'.tar.gz'),STEM+'-'+kind,entries,1)
                members[kind]={n:dict(sha256=hashlib.sha256(d).hexdigest(),mode=m) for n,(d,m) in entries.items()}
            for name in ['R5-AUDIT.json','SHA256SUMS']:(destination/name).write_bytes(b'original fixture metadata')
            return dict(version='0.0.1-rc.1',qualified_source_commit='a'*40,artifacts={},supplement_members=members)
        staging=root/'fixture';build(candidate,None,staging)
        for path in staging.iterdir():(output/path.name).write_bytes(path.read_bytes())
        return candidate,output,build

    def test_complete_distribution_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidate,output,build=self.fixture(Path(tmp))
            with patch.object(audit,'build',build):self.assertEqual(audit.verify(candidate,None,output)['status'],'passed')

    def test_missing_extra_symlink_or_changed_file_fails(self):
        for mutation in ['missing','extra','symlink','changed']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);candidate,output,build=self.fixture(root);target=output/'R5-AUDIT.json'
                if mutation=='missing':target.unlink()
                elif mutation=='extra':(output/'unreviewed').write_text('extra')
                elif mutation=='symlink':target.unlink();target.symlink_to(candidate/(STEM+'-source.tar.gz'))
                else:target.write_text('changed')
                with patch.object(audit,'build',build),self.assertRaises(ValueError):audit.verify(candidate,None,output)


if __name__=='__main__':unittest.main()
