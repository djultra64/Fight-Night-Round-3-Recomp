#!/usr/bin/env python3
"""Install private game data from your own Fight Night Round 3 (USA) ISO.

Work: djultra64. No game files are downloaded or distributed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

REQUIRED_FREE_BYTES = 4 * 1024 ** 3


def user_data_path():
    home = Path.home()
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', home / 'AppData/Local')) / 'fnr3/user'
    return Path(os.environ.get('XDG_DATA_HOME', home / '.local/share')) / 'fnr3'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_data(data, manifest):
    xex = data / 'default.xex'
    expected = manifest['xex']
    if (not xex.is_file() or xex.stat().st_size != expected['size']
            or sha256(xex) != expected['sha256']):
        raise ValueError('Unsupported game edition: original default.xex differs. Use the supported USA disc.')


def choose_iso():
    print('Fight Night Round 3 Recomp requires your own supported USA Xbox 360 disc ISO.', flush=True)
    print('Select your ISO. It will remain unchanged; extracted data stays in your user folder.', flush=True)
    desktop = platform.system() == 'Windows' or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    if desktop:
        for program, args in (
            ('zenity', ['--file-selection', '--title=Select your Fight Night Round 3 (USA) ISO', '--file-filter=ISO files | *.iso *.ISO']),
            ('kdialog', ['--getopenfilename', str(Path.home()), '*.iso *.ISO|ISO files', '--title', 'Select your Fight Night Round 3 (USA) ISO']),
        ):
            executable = shutil.which(program)
            if executable:
                result = subprocess.run([executable, *args], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return Path(result.stdout.strip())
                if result.returncode == 1:
                    raise ValueError('ISO selection cancelled. Run the installer again when ready.')
        try:
            import tkinter
            from tkinter import filedialog
            window = tkinter.Tk()
            window.withdraw()
            try:
                selected = filedialog.askopenfilename(title='Select your Fight Night Round 3 (USA) ISO',
                                                     filetypes=[('ISO disc image', '*.iso *.ISO'), ('All files', '*')])
            finally:
                window.destroy()
            if not selected:
                raise ValueError('ISO selection cancelled. Run the installer again when ready.')
            return Path(selected)
        except (ImportError, RuntimeError):
            pass
        except Exception as error:
            # Tk may be installed without an available desktop/display.
            if error.__class__.__name__ != 'TclError':
                raise
    if not sys.stdin.isatty():
        raise ValueError('No file picker available. Run install.py --iso "/path/to/your/game.iso" or --game-data-root "/path/to/extracted/game".')
    try:
        selected = input('Path to your Fight Night Round 3 (USA) ISO: ').strip()
    except EOFError:
        selected = ''
    if not selected:
        raise ValueError('No ISO selected. Run the installer again when ready.')
    # Support the quotes commonly pasted around paths containing spaces.
    return Path(selected.strip('"').strip("'"))


def remember(user, data):
    descriptor, name = tempfile.mkstemp(prefix='.installation-', suffix='.json', dir=user)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'schema': 1, 'game_data_root': str(data)}, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(user / 'installation.json')
    finally:
        temporary.unlink(missing_ok=True)


def ensure_game_data(package, user, iso=None, game_data_root=None, interactive=True):
    """Verify/register existing data or transactionally import a supported ISO.

    The package manifest pins both the complete ISO and default.xex. Unknown
    archives are rejected BEFORE the bundled extractor runs, so untrusted archive
    names, traversal entries, and unsupported editions never reach extraction.
    """
    package, user = Path(package).resolve(), Path(user).resolve()
    manifest = json.loads((package / 'support/input-manifest.json').read_text(encoding='utf-8'))
    if iso is not None and game_data_root is not None:
        raise ValueError('Choose either --iso or --game-data-root, not both.')
    if game_data_root is not None:
        data = Path(game_data_root).expanduser().resolve()
        verify_data(data, manifest)
        user.mkdir(parents=True, exist_ok=True)
        remember(user, data)
        return data
    state = user / 'installation.json'
    if iso is None and state.is_file():
        try:
            installation = json.loads(state.read_text(encoding='utf-8'))
            data = Path(installation['game_data_root'])
            if installation.get('schema') != 1 or not data.is_absolute():
                raise ValueError('Invalid installation state')
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError('Installation record is invalid. Run install.py --game-data-root with your extracted game folder.') from error
        verify_data(data, manifest)
        return data
    if iso is None:
        if not interactive:
            raise ValueError('Game data is not installed. Run install.py --iso "/path/to/your/game.iso" or provide --game-data-root.')
        iso = choose_iso()
    iso = Path(iso).expanduser().resolve()
    if not iso.is_file() or iso.stat().st_size != manifest['iso']['size']:
        raise ValueError('Unsupported ISO size. Select the supported complete Fight Night Round 3 (USA) Xbox 360 disc ISO.')
    user.mkdir(parents=True, exist_ok=True)
    destination = user / 'game-data'
    if destination.exists() or destination.is_symlink():
        # Never replace an existing directory, even if it looks incomplete.
        raise ValueError('Game-data destination already exists. Use --game-data-root to register verified data, or choose another --user-data-root.')
    if shutil.disk_usage(user).free < REQUIRED_FREE_BYTES:
        raise ValueError('At least 4 GiB of free space is required in the user data folder.')
    print('Verifying your ISO (SHA-256). This may take a few minutes...', flush=True)
    if sha256(iso) != manifest['iso']['sha256']:
        raise ValueError('Unsupported ISO SHA-256. The disc image is damaged or a different edition.')
    extractor = package / 'support' / ('extract-xiso.exe' if platform.system() == 'Windows' else 'extract-xiso')
    if not extractor.is_file():
        raise ValueError('The bundled ISO extractor is missing. Extract the complete release package again.')
    lock = user / '.install.lock'
    try:
        lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError('Another installation may be running. If it was interrupted, remove .install.lock from your user data folder and retry.') from error
    try:
        with os.fdopen(lock_fd, 'w') as stream:
            stream.write(str(os.getpid()) + '\n')
        with tempfile.TemporaryDirectory(prefix='.import-', dir=user) as temporary:
            stage = Path(temporary) / 'game-data'
            print('Extracting verified ISO to your private game-data folder...', flush=True)
            result = subprocess.run([str(extractor), '-x', '-q', '-d', str(stage), str(iso)], cwd=temporary)
            if result.returncode:
                raise ValueError('Extraction failed (exit code %d). Check available space and retry; your ISO is unchanged.' % result.returncode)
            verify_data(stage, manifest)
            if any(path.is_symlink() for path in stage.rglob('*')):
                raise ValueError('Unsupported extracted symbolic link.')
            if destination.exists() or destination.is_symlink():
                raise ValueError('Game-data destination already exists; installation stopped without replacing it.')
            stage.rename(destination)
        # If state writing is interrupted, verified data remains intact and can
        # be registered with --game-data-root on the next run.
        remember(user, destination)
    finally:
        lock.unlink(missing_ok=True)
    print('Private game data installed successfully. Your ISO is unchanged.', flush=True)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--iso', type=Path, help='Your own supported USA Xbox 360 disc ISO')
    sources.add_argument('--game-data-root', type=Path, help='Register an existing extracted game folder')
    parser.add_argument('--user-data-root', type=Path, default=user_data_path())
    args = parser.parse_args(argv)
    data = ensure_game_data(Path(__file__).resolve().parent, args.user_data_root,
                            iso=args.iso, game_data_root=args.game_data_root)
    print('Game data: ' + str(data))
    print('Start the game with launch.sh (Linux) or launch.cmd (Windows).')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        raise SystemExit('Installation stopped: ' + (str(error) or 'cancelled'))
