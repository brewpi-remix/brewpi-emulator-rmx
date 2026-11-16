# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original retention negatives; synthetic evidence never represents a candidate."""
import json
from pathlib import Path
import tempfile
import unittest
from r6_handoff import relative, retain, select, verify, backup, verify_backup
from artifacts import sha


class Retention(unittest.TestCase):
    def inputs(self,root):
        source=root/'source';source.mkdir();(source/'receipt.json').write_text('original synthetic receipt\n')
        return dict(roots=['source'],exclude=[],anchors={'source/receipt.json':sha(source/'receipt.json')})

    def test_complete_copy_preserves_source_bytes_and_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);(root/'source/receipt.json').chmod(0o440)
            result=retain(root,root/'saved',config)
            self.assertEqual(result['status'],'passed');self.assertEqual(verify(root/'saved',root)['files'],1)
            self.assertEqual((root/'saved').stat().st_mode&0o777,0o700)

    def test_missing_changed_extra_mode_or_symlink_fails(self):
        for mutation in ['missing','changed','extra','mode','symlink']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();config=self.inputs(root);retain(root,root/'saved',config)
                path=root/'saved/retained/source/receipt.json'
                if mutation=='missing':path.unlink()
                elif mutation=='changed':path.write_text('substituted')
                elif mutation=='extra':(path.parent/'extra').write_text('unreviewed')
                elif mutation=='mode':path.chmod(0o755)
                else:path.unlink();path.symlink_to(root/'source/receipt.json')
                with self.assertRaises(ValueError):verify(root/'saved')

    def test_missing_anchor_is_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);config['anchors']['missing']='0'*64
            with self.assertRaises(ValueError):retain(root,root/'saved',config)
            self.assertEqual(json.loads((root/'saved/retention.json').read_text())['status'],'failed')

    def test_reuse_and_recursive_copy_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);retain(root,root/'saved',config)
            original=(root/'saved/inventory.json').read_bytes()
            with self.assertRaises(ValueError):retain(root,root/'saved',config)
            self.assertEqual(original,(root/'saved/inventory.json').read_bytes())
            with self.assertRaises(ValueError):retain(root,root/'source/nested',config)

    def test_unsafe_paths_and_symlink_parents_are_rejected(self):
        for name in ['.','../escape','/absolute','source/../escape','source//file','.git/config']:
            with self.subTest(name=name),self.assertRaises(ValueError):relative(name)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);(root/'alias').symlink_to(root/'source',target_is_directory=True)
            with self.assertRaises(ValueError):retain(root,root/'alias/saved',config)
            with self.assertRaises(ValueError):select(root,dict(config,roots=['alias']))

    def test_changed_original_is_not_conflated_with_retained_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);retain(root,root/'saved',config)
            (root/'source/receipt.json').write_text('later source')
            self.assertEqual(verify(root/'saved')['status'],'passed')
            with self.assertRaises(ValueError):verify(root/'saved',root)


    def test_backup_rejects_changed_archive_and_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);destination=root/'saved';retain(root,destination,config)
            (destination/'source-history.bundle').write_bytes(b'original synthetic bundle fixture')
            self.assertEqual(backup(destination)['status'],'passed')
            archive=destination/'retained-evidence.tar.gz';original=archive.read_bytes()
            archive.write_bytes(original[:-8]+b'corrupt!')
            with self.assertRaises(Exception):verify_backup(archive,destination)
            archive.write_bytes(original)
            (destination/'source-history.bundle').write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_backup(archive,destination)

    def test_empty_or_symlink_inventory_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);retain(root,root/'saved',config)
            inventory=root/'saved/inventory.json';original=inventory.read_bytes();outside=root/'outside';outside.write_bytes(original)
            inventory.unlink();inventory.symlink_to(outside)
            with self.assertRaises(ValueError):verify(root/'saved')
            with self.assertRaises(ValueError):retain(root,root/'empty',dict(roots=[],exclude=[],anchors={}))


    def test_backup_setup_failure_has_a_failed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();config=self.inputs(root);destination=root/'saved';retain(root,destination,config)
            with self.assertRaises(ValueError):backup(destination)
            receipt=json.loads((destination/'backup-verification.json').read_text())
            self.assertEqual(receipt['status'],'failed')
            self.assertFalse((destination/'retained-evidence.tar.gz').exists())


if __name__=='__main__':unittest.main()
