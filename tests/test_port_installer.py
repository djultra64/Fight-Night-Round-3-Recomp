"""Private ISO import transactions. Work: djultra64."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'tools/port-build/install.py'


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.windows_helper = None
        if os.name != 'nt':
            return
        compiler = shutil.which('clang') or shutil.which('clang-cl')
        if not compiler:
            raise unittest.SkipTest('Windows extractor fixture requires a native C compiler')
        cls.helper_temp = tempfile.TemporaryDirectory(prefix='fnr3 native extractor fixture ')
        cls.addClassCleanup(cls.helper_temp.cleanup)
        source = Path(cls.helper_temp.name) / 'fixture.c'
        source.write_text(r'''#include <windows.h>
#include <wchar.h>
#include <stdlib.h>
int wmain(void) {
  wchar_t script[32768], command[32768];
  if (!GetModuleFileNameW(NULL, script, 32760)) return 90;
  wcscat_s(script, 32768, L".py");
  const wchar_t *python = _wgetenv(L"FNR3_TEST_PYTHON");
  if (!python) return 91;
  wchar_t *tail = GetCommandLineW();
  if (*tail == L'"') { ++tail; while (*tail && *tail != L'"') ++tail; if (*tail) ++tail; }
  else { while (*tail && *tail != L' ' && *tail != L'\t') ++tail; }
  if (_snwprintf_s(command, 32768, _TRUNCATE, L"\"%ls\" \"%ls\" %ls", python, script, tail) < 0) return 92;
  STARTUPINFOW startup = {sizeof(startup)};
  PROCESS_INFORMATION process;
  if (!CreateProcessW(python, command, NULL, NULL, TRUE, 0, NULL, NULL, &startup, &process)) return 93;
  WaitForSingleObject(process.hProcess, INFINITE);
  DWORD result = 94;
  GetExitCodeProcess(process.hProcess, &result);
  CloseHandle(process.hThread); CloseHandle(process.hProcess);
  return (int)result;
}
''')
        cls.windows_helper = Path(cls.helper_temp.name) / 'extract-xiso.exe'
        args = [compiler, str(source)]
        if Path(compiler).stem == 'clang-cl':
            args += ['/nologo', '/O2', '/Fe:' + str(cls.windows_helper)]
        else:
            args += ['-O2', '-o', str(cls.windows_helper)]
        subprocess.run(args, check=True, cwd=cls.helper_temp.name, capture_output=True)

    def setUp(self):
        spec = importlib.util.spec_from_file_location('port_install', SOURCE)
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        self.temp = tempfile.TemporaryDirectory(prefix='fnr3 install test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'package with spaces'
        (self.package / 'support').mkdir(parents=True)
        self.user = self.root / 'user data'
        self.iso = self.root / 'my own game.iso'
        self.iso.write_bytes(b'fixture owned ISO')
        self.xex = b'fixture original XEX'
        manifest = {'iso': {'size': self.iso.stat().st_size, 'sha256': hashlib.sha256(self.iso.read_bytes()).hexdigest()},
                    'xex': {'size': len(self.xex), 'sha256': hashlib.sha256(self.xex).hexdigest()}}
        (self.package / 'support/input-manifest.json').write_text(json.dumps(manifest))
        # Executable fixture models the external extractor boundary and requires
        # precisely the read-only extraction flags used by the pinned tool.
        self.extractor = self.package / ('support/extract-xiso.exe' if os.name == 'nt' else 'support/extract-xiso')
        if self.windows_helper is not None:
            shutil.copyfile(self.windows_helper, self.extractor)
            environment = patch.dict(os.environ, {'FNR3_TEST_PYTHON': sys.executable})
            environment.start()
            self.addCleanup(environment.stop)
        self.write_extractor("(out / 'default.xex').write_bytes(b'fixture original XEX')\n(out / 'data.bin').write_bytes(b'content')")

    def write_extractor(self, body):
        script = Path(str(self.extractor) + '.py') if os.name == 'nt' else self.extractor
        script.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\nassert sys.argv[1:3] == ["-x", "-q"]\nassert sys.argv[3] == "-d"\nassert Path(sys.argv[5]).is_file()\nout = Path(sys.argv[4])\nout.mkdir(exist_ok=True)\n' + body + '\n')
        self.extractor.chmod(0o755)

    def install(self, **kwargs):
        return self.installer.ensure_game_data(self.package, self.user, **kwargs)

    def test_valid_iso_transaction_remembers_location_and_preserves_iso(self):
        result = self.install(iso=self.iso)
        self.assertEqual(result, self.user / 'game-data')
        self.assertEqual((result / 'data.bin').read_bytes(), b'content')
        self.assertEqual(self.iso.read_bytes(), b'fixture owned ISO')
        self.assertEqual(self.install(), result)
        self.assertEqual(list(self.user.glob('.import-*')), [])

    def test_corrupt_same_size_and_wrong_size_iso_rejected_before_extractor(self):
        for content in (b'wrong', b'x' * self.iso.stat().st_size):
            self.iso.write_bytes(content)
            with self.assertRaisesRegex(ValueError, 'Unsupported ISO'):
                self.install(iso=self.iso)
            self.assertFalse((self.user / 'game-data').exists())

    def test_malicious_archive_is_never_extracted(self):
        self.iso.write_bytes(b'PK archive ../../outside')
        with self.assertRaisesRegex(ValueError, 'Unsupported ISO'):
            self.install(iso=self.iso)
        self.assertFalse((self.root / 'outside').exists())

    def test_extraction_failure_cleans_only_owned_stage_and_allows_retry(self):
        self.user.mkdir()
        keep = self.user / '.import-unrelated'
        keep.mkdir()
        (keep / 'keep').write_text('mine')
        self.write_extractor("(out / 'partial').write_text('partial')\nsys.exit(3)")
        with self.assertRaisesRegex(ValueError, 'Extraction failed'):
            self.install(iso=self.iso)
        self.assertEqual((keep / 'keep').read_text(), 'mine')
        self.assertFalse((self.user / 'installation.json').exists())
        self.write_extractor("(out / 'default.xex').write_bytes(b'fixture original XEX')")
        self.assertTrue(self.install(iso=self.iso).is_dir())

    def test_wrong_extracted_edition_never_published(self):
        self.write_extractor("(out / 'default.xex').write_bytes(b'wrong edition')")
        with self.assertRaisesRegex(ValueError, 'Unsupported game edition'):
            self.install(iso=self.iso)
        self.assertFalse((self.user / 'game-data').exists())
        self.assertEqual(list(self.user.glob('.import-*')), [])

    def test_unrelated_destination_is_preserved(self):
        destination = self.user / 'game-data'
        destination.mkdir(parents=True)
        (destination / 'keep').write_text('mine')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.install(iso=self.iso)
        self.assertEqual((destination / 'keep').read_text(), 'mine')

    def test_external_data_registered_without_copy(self):
        data = self.root / 'existing extracted game'
        data.mkdir()
        (data / 'default.xex').write_bytes(self.xex)
        self.assertEqual(self.install(game_data_root=data), data)
        self.assertEqual(self.install(), data)
        self.assertFalse((self.user / 'game-data').exists())

    def test_insufficient_space_leaves_no_partial_install(self):
        with patch.object(shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100, 100, 0)):
            with self.assertRaisesRegex(ValueError, 'free space'):
                self.install(iso=self.iso)
        self.assertFalse((self.user / 'game-data').exists())

    def test_changed_remembered_xex_is_rejected(self):
        data = self.install(iso=self.iso)
        (data / 'default.xex').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Unsupported game edition'):
            self.install()

    def test_noninteractive_first_run_requires_source_without_prompt(self):
        with self.assertRaisesRegex(ValueError, 'Game data is not installed'):
            self.install(interactive=False)
        self.assertFalse(self.user.exists())

    def test_concurrent_install_is_refused_without_removing_other_lock(self):
        self.user.mkdir()
        lock = self.user / '.install.lock'
        lock.write_text('another installation')
        with self.assertRaisesRegex(ValueError, 'Another installation'):
            self.install(iso=self.iso)
        self.assertEqual(lock.read_text(), 'another installation')
        self.assertFalse((self.user / 'game-data').exists())

    def test_standalone_cli_installs_from_a_path_with_spaces(self):
        shutil.copyfile(SOURCE, self.package / 'install.py')
        result = subprocess.run([sys.executable, str(self.package / 'install.py'),
                                 '--iso', str(self.iso), '--user-data-root', str(self.user)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.user / 'game-data/default.xex').read_bytes(), self.xex)
        self.assertIn('Private game data installed successfully', result.stdout)

    def test_selected_and_explicit_sources_cannot_be_combined(self):
        with self.assertRaisesRegex(ValueError, 'either --iso or --game-data-root'):
            self.install(iso=self.iso, game_data_root=self.root)
        self.assertFalse(self.user.exists())


if __name__ == '__main__':
    unittest.main()
