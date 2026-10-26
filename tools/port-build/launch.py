#!/usr/bin/env python3
"""Prepare a private game-data installation and launch the port. Work: djultra64."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tempfile
import uuid

PORT_RESTART_EXIT_CODE = 42


def user_paths():
    home = Path.home()
    if platform.system() == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', home / 'AppData/Local')) / 'fnr3'
        return base / 'user', base / 'cache'
    return (Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'fnr3',
            Path(os.environ.get('XDG_CACHE_HOME', home / '.cache')) / 'fnr3')


def verify_original(package, data):
    manifest = json.loads((package / 'support/input-manifest.json').read_text())
    digest = hashlib.sha256()
    with (data / 'default.xex').open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != manifest['xex']['sha256']:
        raise ValueError('Unsupported game edition: original XEX hash differs')


def preparation_fingerprint(package, script):
    digest = hashlib.sha256()
    for source in (script, package / 'tools/port-input/original-glyph-hashes.json',
                   package / 'support/input-manifest.json'):
        digest.update(source.relative_to(package).as_posix().encode('utf-8') + b'\0')
        digest.update(source.read_bytes() + b'\0')
    return digest.hexdigest()


def prepare(package, data, user, regenerate=False):
    verify_original(package, data)
    frontend, glyphs = user / 'port-overrides', user / 'input-glyphs'
    scripts = ((package / 'tools/frontend_overrides.py', frontend),
               (package / 'tools/port-input/build_glyph_overrides.py', glyphs))
    for script, destination in scripts:
        fingerprint = preparation_fingerprint(package, script)
        stamp = destination / '.preparation-sha256'
        try:
            previous = stamp.read_text(encoding='ascii').strip()
        except (OSError, UnicodeError):
            previous = None
        if regenerate or not (destination / 'manifest.json').is_file() or previous != fingerprint:
            subprocess.run([sys.executable, str(script), '--game-data-root', str(data),
                            '--output', str(destination)], check=True)
            # A failed generator must retain the old stamp and retry next time.
            destination.mkdir(parents=True, exist_ok=True)
            stamp.write_text(fingerprint + '\n', encoding='ascii')
    return frontend, glyphs


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def save_attempt(directory, record):
    if directory is None:
        return
    try:
        temporary = directory / 'attempt.json.tmp'
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(directory / 'attempt.json')
    except OSError as error:
        print(f'Could not save launch diagnostics: {error}', file=sys.stderr)


def attempt_paths(user, session, attempt):
    directory = user / 'logs' / session / f'attempt-{attempt:02d}'
    try:
        directory.mkdir(parents=True, exist_ok=False)
        log_file = directory / 'runtime.log'
        # The runtime opens its sink without recovering from permission errors.
        # Verify a writable file before passing it to the child.
        with log_file.open('x', encoding='utf-8'):
            pass
        return directory, log_file
    except OSError as error:
        print(f'Could not create launch diagnostics: {error}', file=sys.stderr)
    try:
        directory = Path(tempfile.mkdtemp(prefix=f'fnr3-{session}-{attempt:02d}-'))
        log_file = directory / 'runtime.log'
        with log_file.open('x', encoding='utf-8'):
            pass
        print(f'Launch diagnostics saved in temporary directory: {directory}', file=sys.stderr)
        return directory, log_file
    except OSError as error:
        # The SDK's explicit no-file destination also suppresses implicit
        # logging beside the executable, which may be equally unwritable.
        print(f'File diagnostics unavailable; continuing without them: {error}', file=sys.stderr)
        return None, Path('-')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data-root', type=Path)
    parser.add_argument('--iso', type=Path, help='Import your local supported Xbox 360 ISO')
    parser.add_argument('--user-data-root', type=Path)
    parser.add_argument('--cache-root', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--regenerate-assets', action='store_true')
    parser.add_argument('--diagnostics', action='store_true',
                        help='Record startup details and enable Windows crash dumps for this run')
    args, extra = parser.parse_known_args()
    package = Path(__file__).resolve().parent
    default_user, default_cache = user_paths()
    user = (args.user_data_root or default_user).resolve()
    cache = (args.cache_root or default_cache).resolve()
    user.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    if args.iso or args.game_data_root is None:
        spec = importlib.util.spec_from_file_location('fnr3_installer', package / 'install.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        data = installer.ensure_game_data(package, user, iso=args.iso,
                                          game_data_root=args.game_data_root,
                                          interactive=not args.prepare_only)
    else:
        data = args.game_data_root.resolve()
    frontend, glyphs = prepare(package, data, user, args.regenerate_assets)
    if args.prepare_only:
        print('Verified local game data and prepared private frontend/glyph overrides.')
        return 0
    executable = package / ('fnr3.exe' if platform.system() == 'Windows' else 'fnr3')
    if extra and extra[0] == '--':
        extra = extra[1:]
    # Paths generated above are authoritative; avoid accidental loss of private
    # save/config locations through a conflicting duplicate passthrough flag.
    reserved = ('--game_data_root', '--user_data_root', '--cache_root',
                '--fnr3_frontend_root', '--fnr3_glyph_root', '--log_file')
    if any(arg.split('=', 1)[0] in reserved for arg in extra):
        parser.error('Use launcher path arguments instead of duplicate game path flags')
    default_level = 'info' if args.diagnostics else 'error'
    log_flags = [] if any(arg.split('=', 1)[0] == '--log_level' for arg in extra) else ['--log_level=' + default_level]
    base_command = [str(executable), '--game_data_root=' + str(data),
                    '--user_data_root=' + str(user), '--cache_root=' + str(cache),
                    '--fnr3_frontend_root=' + str(frontend), '--fnr3_glyph_root=' + str(glyphs)]
    session = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:12]
    attempt = 0
    while True:
        attempt += 1
        directory, log_file = attempt_paths(user, session, attempt)
        command = [*base_command, '--log_file=' + str(log_file), *log_flags, *extra]
        environment = os.environ.copy()
        environment.pop('FNR3_DIAGNOSTICS_DIR', None)
        if args.diagnostics and directory is not None:
            environment['FNR3_DIAGNOSTICS_DIR'] = str(directory)
        record = {'schema': 1, 'session': session, 'attempt': attempt,
                  'started_utc': utc_now(), 'status': 'launching',
                  'launcher_pid': os.getpid(), 'platform': f'{platform.system()} {platform.release()} {platform.machine()}',
                  'executable': str(executable), 'runtime_log': str(log_file),
                  'diagnostics': args.diagnostics}
        save_attempt(directory, record)
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=package, env=environment).returncode
        except OSError as error:
            record.update(status='launch_failed', error=str(error), finished_utc=utc_now())
            save_attempt(directory, record)
            raise
        record.update(returncode=result, finished_utc=utc_now(),
                      elapsed_ms=round((time.monotonic() - started) * 1000),
                      status='restart_requested' if result == PORT_RESTART_EXIT_CODE else 'finished')
        save_attempt(directory, record)
        if result != PORT_RESTART_EXIT_CODE:
            return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
