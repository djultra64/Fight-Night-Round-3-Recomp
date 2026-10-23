"""Production package boundary and provenance regressions. Work: djultra64."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('port_build', Path(__file__).resolve().parents[1] / 'tools/port_build.py')
pb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pb)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stage = self.root / 'stage'
        self.stage.mkdir()

    def record(self, target='linux-amd64'):
        names = ('fnr3.exe', 'rexruntime.dll', 'rexgpu-xenos.dll') if target == 'win-amd64' else ('fnr3', 'librexruntime.so', 'librexgpu-xenos.so')
        for name in names:
            (self.stage / name).write_bytes(b'compiled fixture')
        return {'owner': 'djultra64', 'target': target,
                'sdk': {'sdk_commit': pb.PIN, 'patch_application': 'explicit-directory-v1', 'patches': {p: 'hash' for p in pb.PATCHES}},
                'configuration': 'Release', 'clock': 'native60-phase-preserved',
                'artifacts': pb.files_manifest(self.stage)}

    def test_linux_and_windows_required_sets(self):
        for target in ('linux-amd64', 'win-amd64'):
            with self.subTest(target=target):
                for p in self.stage.iterdir():
                    p.unlink()
                record = self.record(target)
                self.assertEqual(pb.validate_stage(self.stage, record), record['artifacts'])

    def test_changed_or_added_artifact_rejected(self):
        record = self.record()
        (self.stage / 'fnr3').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            pb.validate_stage(self.stage, record)

    def test_original_assets_cannot_enter_recorded_package(self):
        record = self.record()
        (self.stage / 'default.xex').write_bytes(b'proprietary')
        record['artifacts'] = pb.files_manifest(self.stage)
        with self.assertRaisesRegex(ValueError, 'Forbidden'):
            pb.validate_stage(self.stage, record)

    def test_nested_assets_rejected(self):
        record = self.record()
        (self.stage / 'assets').mkdir()
        (self.stage / 'assets/original.so').write_bytes(b'original')
        record['artifacts'] = pb.files_manifest(self.stage)
        with self.assertRaisesRegex(ValueError, 'Forbidden'):
            pb.validate_stage(self.stage, record)

    def test_symlink_artifact_rejected(self):
        self.record()
        try:
            (self.stage / 'linked.so').symlink_to(self.stage / 'librexruntime.so')
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            pb.files_manifest(self.stage)

    def test_embedded_workspace_loader_path_rejected(self):
        record = self.record()
        record['loader_dependencies'] = {'librexgpu-xenos.so': {
            'search_paths': ['$ORIGIN:/private/workspace/sdk/out']}}
        with self.assertRaisesRegex(ValueError, 'Nonportable'):
            pb.validate_stage(self.stage, record)

    def test_missing_patch_or_wrong_identity_rejected(self):
        record = self.record()
        record['sdk']['patches'].pop(pb.PATCHES[0])
        with self.assertRaisesRegex(ValueError, 'patchset'):
            pb.validate_stage(self.stage, record)
        record = self.record()
        record['owner'] = 'someone else'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            pb.validate_stage(self.stage, record)

    def test_missing_runtime_rejected_even_if_recorded(self):
        record = self.record()
        (self.stage / 'librexruntime.so').unlink()
        record['artifacts'] = pb.files_manifest(self.stage)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            pb.validate_stage(self.stage, record)

    def test_git_format_patch_modifies_nested_export_and_adds_files(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        sdk = self.root / 'nested/sdk'
        (sdk / 'src').mkdir(parents=True)
        (sdk / 'src/existing.txt').write_text('before\n')
        patches = self.root / 'patches'
        patches.mkdir()
        (patches / 'regression.patch').write_text(
            'diff --git a/src/existing.txt b/src/existing.txt\n'
            '--- a/src/existing.txt\n+++ b/src/existing.txt\n'
            '@@ -1 +1 @@\n-before\n+after\n'
            'diff --git a/src/added.txt b/src/added.txt\n'
            'new file mode 100644\n--- /dev/null\n+++ b/src/added.txt\n'
            '@@ -0,0 +1 @@\n+new\n')
        with patch.object(pb, 'ROOT', self.root), patch.object(pb, 'PATCHES', ('regression.patch',)), contextlib.redirect_stdout(io.StringIO()):
            pb.apply_sdk_patches(sdk)
            pb.apply_sdk_patches(sdk)  # Idempotent, with a real reverse-check.
        self.assertEqual((sdk / 'src/existing.txt').read_text(), 'after\n')
        self.assertEqual((sdk / 'src/added.txt').read_text(), 'new\n')
        self.assertFalse((self.root / 'src').exists())

    def test_clean_checkout_generates_guest_before_host_reconfigure(self):
        sdk, project, build = self.root / 'sdk', self.root / 'project', self.root / 'build'
        sdk.mkdir()
        (project / 'generated/default').mkdir(parents=True)
        build.mkdir()
        pb.write_json(self.root / 'sdk-prepared.json', {'sdk_commit': pb.PIN})
        pb.write_json(self.root / 'sdk-inputs.json', {'files': {}})
        phases = []
        def fake_run(command, flatpak=False, cwd=None):
            if '-S' in command:
                phases.append('configure')
                self.assertEqual((project / 'generated/default/sources.cmake').exists(), phases.count('configure') == 2)
                (build / 'CMakeCache.txt').write_text('fixture cache')
            elif 'fnr3_codegen' in command:
                phases.append('codegen')
                (project / 'generated/default/sources.cmake').write_text('fixture source list')
            elif 'fnr3_stage_gpu' in command:
                phases.append('host')
                self.assertEqual(phases, ['configure', 'codegen', 'configure', 'host'])
                (build / 'fnr3').write_bytes(b'compiled host fixture')
                output = sdk / 'out/linux-amd64'
                output.mkdir(parents=True)
                for name in ('librexruntime.so', 'librexgpu-xenos.so'):
                    (output / name).write_bytes(b'compiled SDK fixture')
        with patch.object(pb, 'prepare', return_value=(sdk, project, build)), patch.object(pb, 'run', side_effect=fake_run), patch.object(pb, 'inspect_dependencies', return_value={}), contextlib.redirect_stdout(io.StringIO()):
            pb.build_port('linux-amd64', 2)
        self.assertEqual(phases, ['configure', 'codegen', 'configure', 'host'])
        self.assertTrue((build / 'build-record.json').is_file())

    def test_launcher_prepares_only_from_verified_original_and_explicit_paths(self):
        launcher_spec = importlib.util.spec_from_file_location('port_launcher', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(launcher_spec)
        launcher_spec.loader.exec_module(launcher)
        package = self.root / 'package'
        data = self.root / 'my extracted game'
        data.mkdir()
        (data / 'default.xex').write_bytes(b'original fixture')
        (package / 'support').mkdir(parents=True)
        pb.write_json(package / 'support/input-manifest.json', {'xex': {'sha256': pb.sha(data / 'default.xex')}})
        for name in ('tools/frontend_overrides.py', 'tools/port-input/build_glyph_overrides.py', 'tools/port-input/original-glyph-hashes.json'):
            source = package / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('fixture source')
        user = self.root / 'private user'
        with patch.object(launcher.subprocess, 'run') as run:
            frontend, glyphs = launcher.prepare(package, data, user)
        self.assertEqual(frontend, user / 'port-overrides')
        self.assertEqual(glyphs, user / 'input-glyphs')
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertIn('--game-data-root', call.args[0])
            self.assertIn(str(data), call.args[0])
            self.assertNotIn('fnr3', [Path(str(arg)).name for arg in call.args[0]])
        (data / 'default.xex').write_bytes(b'different edition')
        with patch.object(launcher.subprocess, 'run') as run, self.assertRaisesRegex(ValueError, 'Unsupported'):
            launcher.prepare(package, data, user)
        run.assert_not_called()

    def test_launcher_upgrade_fingerprints_regenerate_only_after_success(self):
        spec = importlib.util.spec_from_file_location('port_launcher_upgrade', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        package, data, user = self.root / 'package', self.root / 'game', self.root / 'user'
        data.mkdir()
        (data / 'default.xex').write_bytes(b'original')
        (package / 'support').mkdir(parents=True)
        pb.write_json(package / 'support/input-manifest.json', {'xex': {'sha256': pb.sha(data / 'default.xex')}})
        for name in ('tools/frontend_overrides.py', 'tools/port-input/build_glyph_overrides.py', 'tools/port-input/original-glyph-hashes.json'):
            source = package / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('version one')
        for name in ('port-overrides', 'input-glyphs'):
            destination = user / name
            destination.mkdir(parents=True)
            (destination / 'manifest.json').write_text('{}')  # Old cache has no fingerprint.
        def generate(command, **kwargs):
            destination = Path(command[command.index('--output') + 1])
            (destination / 'manifest.json').write_text('{}')
            return subprocess.CompletedProcess(command, 0)
        with patch.object(launcher.subprocess, 'run', side_effect=generate) as run:
            launcher.prepare(package, data, user)
            self.assertEqual(run.call_count, 2)
            run.reset_mock()
            launcher.prepare(package, data, user)
            run.assert_not_called()
            (package / 'tools/frontend_overrides.py').write_text('version two with preserved siblings')
            launcher.prepare(package, data, user)
            self.assertEqual(run.call_count, 1)
            self.assertIn(str(package / 'tools/frontend_overrides.py'), run.call_args.args[0])
            run.reset_mock()
            launcher.prepare(package, data, user, regenerate=True)
            self.assertEqual(run.call_count, 2)
        stamp = user / 'port-overrides/.preparation-sha256'
        successful = stamp.read_text()
        (package / 'tools/frontend_overrides.py').write_text('version three')
        with patch.object(launcher.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['generator'])), self.assertRaises(subprocess.CalledProcessError):
            launcher.prepare(package, data, user)
        self.assertEqual(stamp.read_text(), successful)

    def test_launcher_defaults_to_error_and_preserves_explicit_diagnostics(self):
        spec = importlib.util.spec_from_file_location('port_launcher_logging', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        user, cache = self.root / 'user', self.root / 'cache'
        for extra in ([], ['--log_level=info'], ['--log_level', 'info']):
            with self.subTest(extra=extra):
                argv = ['launch.py', '--game-data-root', str(self.root / 'data'), *extra]
                with patch.object(launcher.sys, 'argv', argv), patch.object(launcher, 'user_paths', return_value=(user, cache)), patch.object(launcher, 'prepare', return_value=(user / 'frontend', user / 'glyphs')), patch.object(launcher.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                    self.assertEqual(launcher.main(), 0)
                command = run.call_args.args[0]
                logging_flags = [arg for arg in command if arg.split('=', 1)[0] == '--log_level']
                self.assertEqual(len(logging_flags), 1)
                if extra:
                    self.assertNotIn('--log_level=error', command)
                    self.assertEqual(command[-len(extra):], extra)
                else:
                    self.assertEqual(logging_flags, ['--log_level=error'])

    def test_launcher_reserved_restart_reuses_command_and_propagates_result(self):
        spec = importlib.util.spec_from_file_location('port_launcher_restart', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        self.assertEqual(launcher.PORT_RESTART_EXIT_CODE, 42)
        user, cache = self.root / 'user with spaces', self.root / 'cache with spaces'
        for statuses in ([42, 0], [42, 9], [0], [7], [-11], [42, 42, 0]):
            with self.subTest(statuses=statuses):
                argv = ['launch.py', '--game-data-root', str(self.root / 'game data'), '--log_level=info']
                outcomes = [subprocess.CompletedProcess([], status) for status in statuses]
                with patch.object(launcher.sys, 'argv', argv), patch.object(launcher, 'user_paths', return_value=(user, cache)), patch.object(launcher, 'prepare', return_value=(user / 'frontend', user / 'glyphs')) as prepare, patch.object(launcher.subprocess, 'run', side_effect=outcomes) as run:
                    self.assertEqual(launcher.main(), statuses[-1])
                self.assertEqual(run.call_count, len(statuses))
                prepare.assert_called_once()
                first = run.call_args_list[0]
                for call in run.call_args_list:
                    self.assertEqual(call.args, first.args)
                    self.assertEqual(call.kwargs, first.kwargs)
                command = first.args[0]
                self.assertIn('--user_data_root=' + str(user), command)
                self.assertIn('--cache_root=' + str(cache), command)
                self.assertIn('--log_level=info', command)

    def test_launcher_prepare_only_never_launches_child(self):
        spec = importlib.util.spec_from_file_location('port_launcher_prepare_only', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        user, cache = self.root / 'user', self.root / 'cache'
        argv = ['launch.py', '--game-data-root', str(self.root / 'game'), '--prepare-only']
        with patch.object(launcher.sys, 'argv', argv), patch.object(launcher, 'user_paths', return_value=(user, cache)), patch.object(launcher, 'prepare', return_value=(user / 'frontend', user / 'glyphs')) as prepare, patch.object(launcher.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.main(), 0)
        prepare.assert_called_once()
        run.assert_not_called()

    def test_launcher_first_run_prepare_only_is_noninteractive(self):
        spec = importlib.util.spec_from_file_location('port_launcher_install', Path(pb.__file__).parent / 'port-build/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        package = self.root / 'installed'
        package.mkdir()
        (package / 'install.py').write_text(
            'def ensure_game_data(package, user, iso=None, game_data_root=None, interactive=True):\n'
            '    assert interactive is False\n'
            '    raise ValueError("No installation; supply --iso or --game-data-root")\n')
        with patch.object(launcher, '__file__', str(package / 'launch.py')), patch.object(launcher.sys, 'argv', ['launch.py', '--prepare-only']), patch.object(launcher, 'user_paths', return_value=(self.root / 'user', self.root / 'cache')), patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'No installation'):
                launcher.main()
        run.assert_not_called()

    def test_release_archive_preserves_modes_and_rejects_unrecorded_files(self):
        spec = importlib.util.spec_from_file_location('release_archive', Path(pb.__file__).parent / 'release_archive.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        import tarfile
        package = self.root / 'beta'
        package.mkdir()
        executable = package / 'launch.sh'
        executable.write_text('#!/bin/sh\n')
        executable.chmod(0o755)
        pb.write_json(package / 'package-manifest.json', {'owner': 'djultra64', 'game_assets_included': False, 'files': pb.files_manifest(package)})
        output = self.root / 'beta.tar.gz'
        digest = release.archive_package(package, output)
        self.assertEqual(digest, pb.sha(output))
        with tarfile.open(output) as archive:
            if os.name != 'nt':
                self.assertEqual(archive.getmember('beta/launch.sh').mode, 0o755)
            else:
                self.assertEqual(archive.getmember('beta/launch.sh').mode, 0o644)
            self.assertTrue(all(member.uid == 0 and not member.uname for member in archive.getmembers()))
        nested = package / 'private'
        nested.mkdir()
        (nested / 'package-manifest.json').write_text('unrecorded private data')
        with self.assertRaisesRegex(ValueError, 'differ'):
            release.archive_package(package, self.root / 'invalid.tar.gz')
        self.assertFalse((self.root / 'invalid.tar.gz').exists())

    def test_windows_release_is_real_zip_and_rejects_unknown_formats(self):
        import zipfile
        spec = importlib.util.spec_from_file_location('release_archive', Path(pb.__file__).parent / 'release_archive.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        package = self.root / 'windows-beta'
        package.mkdir()
        (package / 'launch.cmd').write_bytes(b'@echo off\r\n')
        pb.write_json(package / 'package-manifest.json', {'owner': 'djultra64', 'game_assets_included': False, 'files': pb.files_manifest(package)})
        output = self.root / 'windows-beta.zip'
        self.assertEqual(release.archive_package(package, output), pb.sha(output))
        self.assertTrue(zipfile.is_zipfile(output))
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('windows-beta/launch.cmd'), b'@echo off\r\n')
            self.assertEqual(archive.getinfo('windows-beta/launch.cmd').date_time, (1980, 1, 1, 0, 0, 0))
        invalid = self.root / 'windows-beta.exe'
        with self.assertRaisesRegex(ValueError, 'format'):
            release.archive_package(package, invalid)
        self.assertFalse(invalid.exists())

    def test_package_dry_run_does_not_write_or_launch(self):
        target = 'linux-amd64'
        home, sdk, project, build = pb.layout(target, self.root)
        build.mkdir(parents=True)
        home.mkdir(parents=True)
        self.stage.rename(build / 'stage')
        self.stage = build / 'stage'
        record = self.record()
        record['compiler_detection'] = {'private': '/private/developer'}
        record['project_inputs'] = {'generated/proprietary.cpp': 'hash'}
        (self.root / 'patches').mkdir()
        with patch.object(pb, 'ROOT', self.root):
            for name in pb.PATCHES:
                destination = pb.patch_file(name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(name)
            record['sdk']['patches'] = {name: pb.sha(pb.patch_file(name)) for name in pb.PATCHES}
        pb.write_json(home / 'sdk-inputs.json', {'files': {}})
        record['sdk_inputs_sha256'] = pb.sha(home / 'sdk-inputs.json')
        pb.write_json(build / 'build-record.json', record)
        output = self.root / 'package with spaces'
        with patch.object(pb, 'ROOT', self.root), patch.object(pb, 'layout', return_value=(home, sdk, project, build)), patch.object(pb.subprocess, 'run') as run:
            with contextlib.redirect_stdout(io.StringIO()):
                pb.package_port(target, output, dry_run=True)
        self.assertFalse(output.exists())
        run.assert_not_called()
        # Exercise an actual destination with spaces and preserve upstream notices.
        for name in ('tools/frontend_overrides.py', 'tools/port-input/build_glyph_overrides.py', 'tools/port-build/launch.py', 'tools/port-input/original-glyph-hashes.json', 'config/input-manifest.json', 'tools/port-build/install.py', 'tools/port-build/install.sh', 'tools/port-build/install.cmd', '.cache/extract-xiso/LICENSE.TXT', 'build/iso-extractor/linux-amd64/extract-xiso', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'docs/beta/release-notes-1.0.md', 'docs/beta/installation.md'):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text('fixture source')
        (self.root / 'tools/port-build/launch.py').write_text(
            'import json, os, pathlib, sys\n'
            'pathlib.Path(os.environ["FNR3_TEST_ARGS"]).write_text(json.dumps(sys.argv[1:]))\n')
        (self.root / 'patches/ReXGlue-LICENSE').write_text('upstream license')
        dependency = sdk / 'thirdparty/dependency'
        dependency.mkdir(parents=True)
        (dependency / 'LICENSE.txt').write_text('dependency license')
        with patch.object(pb, 'ROOT', self.root), patch.object(pb, 'layout', return_value=(home, sdk, project, build)), contextlib.redirect_stdout(io.StringIO()):
            pb.package_port(target, output)
        manifest = json.loads((output / 'package-manifest.json').read_text())
        self.assertFalse(manifest['game_assets_included'])
        self.assertEqual(manifest['version'], '1.0.0')
        self.assertEqual(manifest['product'], 'Fight Night Round 3 Recomp')
        self.assertEqual(manifest['channel'], 'release')
        self.assertEqual(json.loads((output / 'build-record.json').read_text())['simulation_hz'], 60)
        public = (output / 'build-record.json').read_text()
        self.assertNotIn('/private/developer', public)
        self.assertNotIn('generated/proprietary', public)
        self.assertFalse((output / 'sdk-inputs.json').exists())
        self.assertTrue((output / 'support/extract-xiso').is_file())
        self.assertIn('This product includes software developed by in <in@fishtank.com>.', (output / 'README.txt').read_text())
        self.assertTrue((output / 'LICENSE').is_file())
        self.assertTrue((output / 'THIRD_PARTY_NOTICES.md').is_file())
        self.assertEqual((output / 'licenses/dependency/LICENSE.txt').read_text(), 'dependency license')
        self.assertEqual((output / 'fnr3').read_bytes(), b'compiled fixture')
        expected_files = pb.files_manifest(output)
        expected_files.pop('package-manifest.json')
        self.assertEqual(manifest['files'], expected_files)
        self.assertNotIn('assets', manifest['files'])
        if os.name != 'nt':
            arguments = self.root / 'wrapper arguments.json'
            env = os.environ.copy()
            env['FNR3_TEST_ARGS'] = str(arguments)
            expected_args = ['--game-data-root', str(self.root / 'my game data'), '--prepare-only']
            subprocess.run([str(output / 'launch.sh'), *expected_args], cwd=self.root, env=env, check=True)
            self.assertEqual(json.loads(arguments.read_text()), expected_args)


if __name__ == '__main__':
    unittest.main()
