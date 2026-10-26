"""Launcher attempt preservation and non-fatal diagnostics. Work: djultra64."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


class LaunchDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('diagnostic_launcher', Path(__file__).resolve().parents[1] / 'tools/port-build/launch.py')
        self.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launcher)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.user, self.cache = self.root / 'user', self.root / 'cache'

    def launch(self, statuses, extra=(), effect=None):
        commands = []
        def child(command, **kwargs):
            commands.append((command, kwargs))
            if effect:
                return effect(command, **kwargs)
            logfile = Path(next(a.split('=', 1)[1] for a in command if a.startswith('--log_file=')))
            logfile.write_text(f'attempt {len(commands)}')
            return subprocess.CompletedProcess(command, statuses[len(commands) - 1])
        argv = ['launch.py', '--game-data-root', str(self.root / 'game'), *extra]
        with patch.object(self.launcher.sys, 'argv', argv), patch.object(self.launcher, 'user_paths', return_value=(self.user, self.cache)), patch.object(self.launcher, 'prepare', return_value=(self.user / 'frontend', self.user / 'glyphs')), patch.object(self.launcher.subprocess, 'run', side_effect=child):
            result = self.launcher.main()
        return result, commands

    def test_restart_keeps_each_log_and_records_raw_exit(self):
        result, commands = self.launch([42, -11])
        self.assertEqual(result, -11)
        paths = [Path(next(a.split('=', 1)[1] for a in c if a.startswith('--log_file='))) for c, _ in commands]
        self.assertNotEqual(paths[0], paths[1])
        self.assertEqual([p.read_text() for p in paths], ['attempt 1', 'attempt 2'])
        records = [json.loads((p.parent / 'attempt.json').read_text()) for p in paths]
        self.assertEqual([r['returncode'] for r in records], [42, -11])
        self.assertEqual([r['status'] for r in records], ['restart_requested', 'finished'])
        self.assertEqual([r['attempt'] for r in records], [1, 2])
        self.assertTrue(all(r['finished_utc'] >= r['started_utc'] for r in records))
        # A new launcher invocation also keeps the preceding crash log.
        self.launch([0])
        self.assertEqual(len(list((self.user / 'logs').rglob('attempt.json'))), 3)

    def test_diagnostic_mode_sets_info_but_preserves_explicit_level(self):
        for extra, expected in ((['--diagnostics'], '--log_level=info'),
                                (['--diagnostics', '--log_level=warning'], '--log_level=warning')):
            with self.subTest(extra=extra):
                _, commands = self.launch([0], extra)
                command, kwargs = commands[0]
                self.assertIn(expected, command)
                self.assertNotIn('--diagnostics', command)
                self.assertTrue(Path(kwargs['env']['FNR3_DIAGNOSTICS_DIR']).is_dir())

    def test_start_failure_is_recorded_without_retry(self):
        calls = []
        def fail(command, **kwargs):
            calls.append(command)
            raise OSError('fixture launch denied')
        with self.assertRaisesRegex(OSError, 'fixture launch denied'):
            self.launch([], effect=fail)
        self.assertEqual(len(calls), 1)
        record = json.loads(next((self.user / 'logs').rglob('attempt.json')).read_text())
        self.assertEqual(record['status'], 'launch_failed')
        self.assertIn('fixture launch denied', record['error'])

    def test_unwritable_diagnostic_directory_does_not_prevent_launch(self):
        mkdir = Path.mkdir
        def selective(path, *args, **kwargs):
            if 'logs' in path.parts:
                raise PermissionError('fixture logs unavailable')
            return mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', selective):
            result, commands = self.launch([0])
        self.assertEqual(result, 0)
        self.assertEqual(len(commands), 1)

    def test_readonly_user_directory_uses_writable_temporary_logs(self):
        original_open = Path.open
        def selective(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get('mode', 'r')
            if self.user in path.parents and any(c in mode for c in 'wax'):
                raise PermissionError('fixture user directory readonly')
            return original_open(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as fallback:
            with patch.object(Path, 'open', selective), patch.object(self.launcher.tempfile, 'tempdir', fallback):
                result, commands = self.launch([0])
            self.assertEqual(result, 0)
            logfile = Path(next(a.split('=', 1)[1] for a in commands[0][0] if a.startswith('--log_file=')))
            self.assertTrue(logfile.is_relative_to(fallback))
            self.assertEqual(logfile.read_text(), 'attempt 1')

    def test_no_writable_destination_disables_file_sink(self):
        mkdir = Path.mkdir
        def deny_logs(path, *args, **kwargs):
            if 'logs' in path.parts:
                raise PermissionError('fixture logs unavailable')
            return mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', deny_logs), patch.object(self.launcher.tempfile, 'mkdtemp', side_effect=PermissionError('fixture temp unavailable')):
            result, commands = self.launch([0], effect=lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
        self.assertEqual(result, 0)
        self.assertIn('--log_file=-', commands[0][0])


if __name__ == '__main__':
    unittest.main()
