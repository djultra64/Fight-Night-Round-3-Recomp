"""App-local Windows CRT dependency closure. Work: djultra64."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('port_build_crt', Path(__file__).resolve().parents[1] / 'tools/port_build.py')
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)


class WindowsCrtTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / 'stage'
        self.stage.mkdir()
        (self.stage / 'fnr3.exe').write_bytes(b'host')
        self.redist = self.root / '14.44'
        self.crt = self.redist / 'x64/Microsoft.VC143.CRT'
        self.crt.mkdir(parents=True)
        for name in ('MSVCP140.dll', 'VCRUNTIME140.dll', 'MSVCP140_ATOMIC_WAIT.dll'):
            (self.crt / name).write_bytes(name.encode())

    def imports(self, stage, target):
        result = {'fnr3.exe': {'needed': ['MSVCP140.dll', 'KERNEL32.dll']}}
        if (stage / 'MSVCP140.dll').exists():
            result['MSVCP140.dll'] = {'needed': ['VCRUNTIME140.dll', 'MSVCP140_ATOMIC_WAIT.dll']}
        return result

    def test_transitive_release_crts_copied_and_hashed_without_system_dlls(self):
        with patch.object(pb, 'inspect_dependencies', side_effect=self.imports):
            record = pb.bundle_windows_crt(self.stage, self.redist)
        self.assertEqual(set(record['files']), {'MSVCP140.dll', 'VCRUNTIME140.dll', 'MSVCP140_ATOMIC_WAIT.dll'})
        self.assertEqual(record['version'], '14.44')
        for name, digest in record['files'].items():
            self.assertEqual(digest, pb.sha(self.stage / name))
        self.assertFalse((self.stage / 'KERNEL32.dll').exists())

    def test_missing_approved_file_never_falls_back_to_system(self):
        (self.crt / 'MSVCP140.dll').unlink()
        with patch.object(pb, 'inspect_dependencies', side_effect=self.imports):
            with self.assertRaisesRegex(ValueError, 'approved redist'):
                pb.bundle_windows_crt(self.stage, self.redist)

    def test_debug_runtime_rejected(self):
        with patch.object(pb, 'inspect_dependencies', return_value={'fnr3.exe': {'needed': ['VCRUNTIME140D.dll']}}):
            with self.assertRaisesRegex(ValueError, 'non-Release'):
                pb.bundle_windows_crt(self.stage, self.redist)

    def test_no_crt_imports_does_not_require_visual_studio(self):
        with patch.object(pb, 'inspect_dependencies', return_value={'fnr3.exe': {'needed': ['KERNEL32.dll']}}), patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pb.bundle_windows_crt(self.stage))


if __name__ == '__main__':
    unittest.main()
