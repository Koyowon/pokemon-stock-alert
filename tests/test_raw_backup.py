import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cu_emart24_raw_backup as backup

class RawBackupAcceptance(unittest.TestCase):
    def setUp(self):
        self.commit="a"*40
        self.raw={p:("bytes:"+p+"\n").encode() for p in backup.PATHS}
        self.blobs={p:hashlib.sha1(b"blob "+str(len(v)).encode()+b"\0"+v).hexdigest()
                    for p,v in self.raw.items()}
    def git(self,repo,*args):
        ref=args[-1]
        if ref.startswith(self.commit+":"):
            path=ref.split(":",1)[1]
            if args[0]=="show":return self.raw[path]
            if args[0]=="rev-parse":return (self.blobs[path]+"\n").encode()
        raise AssertionError("unexpected git invocation: "+repr(args))
    def test_backup_restore_byte_identity(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backup,"git",side_effect=self.git):
            out=Path(temp)/"immutable"
            manifest=backup.backup(Path(temp),self.commit,out)
            self.assertTrue(backup.verify(Path(temp),out))
            self.assertEqual(set(manifest["files"]),set(backup.PATHS))
            for name in backup.PATHS:
                self.assertEqual((out/name).read_bytes(),self.raw[name])
    def test_corruption_detected(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backup,"git",side_effect=self.git):
            out=Path(temp)/"immutable"
            backup.backup(Path(temp),self.commit,out)
            (out/backup.PATHS[0]).write_bytes(b"corrupt")
            with self.assertRaises(ValueError):backup.verify(Path(temp),out)
    def test_refuses_overwrite_and_short_commit(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(backup,"git",side_effect=self.git):
            out=Path(temp)/"immutable"
            with self.assertRaises(ValueError):backup.backup(Path(temp),"short",out)
            backup.backup(Path(temp),self.commit,out)
            with self.assertRaises(ValueError):backup.backup(Path(temp),self.commit,out)
if __name__=="__main__":unittest.main()
