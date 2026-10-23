"""Independent public package boundary regressions. Work: djultra64."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('release_archive', Path(__file__).resolve().parents[1] / 'tools/release_archive.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'beta'
        self.package.mkdir()

    def record(self, names):
        files = {}
        for name in names:
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
            files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.package / 'package-manifest.json').write_text(json.dumps({
            'owner': 'djultra64', 'game_assets_included': False, 'files': files}))

    def test_recorded_private_paths_are_rejected_before_writing(self):
        for name in ('.research/notes.txt', '.superpowers/notes.txt', 'shadercache.xsh',
                     'shadercache.fxo', 'shadercache.xpso', 'shadercache.spv',
                     'assets/default.xex', 'disc.iso', 'generated/default.cpp',
                     'core', 'runtime/game.bin', 'tools/secret.py',
                     'support/default.xex', 'docs/beta/disc.ISO',
                     'licenses/vendor/shader.SPV',
                     'licenses/vendor/.research/notes.txt', 'licenses/vendor/private.bin'):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(dir=self.root) as directory:
                    self.package = Path(directory) / 'beta'
                    self.package.mkdir()
                    self.record([name])
                    destination = Path(directory) / 'bad.zip'
                    with self.assertRaisesRegex(ValueError, 'boundary|forbidden'):
                        release.archive_package(self.package, destination)
                    self.assertFalse(destination.exists())
                    self.assertFalse((destination.parent / 'SHA256SUMS').exists())

    def test_shipped_runtime_tools_and_nested_licenses_are_allowed(self):
        self.record(['launch.sh', 'fnr3', 'librexruntime.so', 'rexgpu-xenos.dll',
                     'msvcp140.dll', 'support/extract-xiso.exe', 'support/extractor-build.json',
                     'support/input-manifest.json', 'tools/frontend_overrides.py',
                     'tools/port-input/original-glyph-hashes.json',
                     'licenses/vendor/nested/LICENSE.md', 'licenses/FFmpeg/COPYING.GPLv2',
                     'licenses/glslang/license-checker.cfg',
                     'licenses/extract-xiso-win32-dirent.c', 'docs/beta/installation.md',
                     'docs/beta/release-notes-0.7.md'])
        release.archive_package(self.package, self.root / 'valid.zip')
        self.assertTrue((self.root / 'valid.zip').exists())

    def test_unsafe_portable_names_are_rejected(self):
        # Test archive names independently of host filesystem normalization,
        # forbidden Windows characters, and NTFS alternate data stream syntax.
        for name in ('launch.sh:private', 'tools\\private.py', 'README.txt\nprivate', 'README.txt '):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'boundary|forbidden'):
                    release.validate_package_path(PurePosixPath(name))

    def test_forbidden_empty_directory_cannot_enter_tar(self):
        self.record(['launch.sh'])
        (self.package / '.research').mkdir()
        with self.assertRaisesRegex(ValueError, 'boundary|forbidden'):
            release.archive_package(self.package, self.root / 'bad.tar.gz')

    def test_archive_root_name_is_portable(self):
        # Root names use the same component contract on every host, including
        # hosts which normalize trailing spaces or treat backslashes as separators.
        for name in ('beta\\..\\private', 'beta ', 'beta.', 'beta:private', 'beta\nprivate'):
            with self.subTest(name=name):
                self.assertFalse(release.portable_component(name))
        self.assertTrue(release.portable_component('Fight-Night-Round-3-v1.0'))

    def test_source_audit_rejects_private_directories_and_shader_artifacts(self):
        spec = importlib.util.spec_from_file_location('release_audit', Path(__file__).resolve().parents[1] / 'tools/release_audit.py')
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        for name in ('.research/notes.txt', '.superpowers/notes.txt',
                     'cache.xsh', 'cache.xpso', 'cache.fxo', 'cache.spv'):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(dir=self.root) as directory:
                    source = Path(directory)
                    path = source / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('private fixture')
                    with self.assertRaises(ValueError):
                        audit.audit(source)


if __name__ == '__main__':
    unittest.main()
