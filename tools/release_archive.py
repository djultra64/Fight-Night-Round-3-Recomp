#!/usr/bin/env python3
"""Archive a verified public beta package without adding private files. Work: djultra64."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import tarfile
import zipfile


# This boundary is independent of package-manifest.json: recording a hash does
# not authorize shipping a new file. Extend it when package_port ships new files.
PUBLIC_FILES = frozenset({
    'fnr3', 'fnr3.exe', 'librexruntime.so', 'librexgpu-xenos.so',
    'rexruntime.dll', 'rexgpu-xenos.dll',
    'concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll',
    'launch.sh', 'launch.cmd', 'launch.py', 'install.sh', 'install.cmd', 'install.py',
    'build-record.json', 'package-manifest.json',
    'README.txt', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
    'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md',
    'tools/frontend_overrides.py', 'tools/port-input/build_glyph_overrides.py',
    'tools/port-input/original-glyph-hashes.json',
    'support/extract-xiso', 'support/extract-xiso.exe',
    'support/extractor-build.json', 'support/input-manifest.json', 'support/release.json',
})
FORBIDDEN_PARTS = frozenset({
    '.research', '.superpowers', '.cache', '.codex', '.codex-attachments',
    '.agents', '.release', '.git', 'assets', 'runtime', 'generated', 'logs',
    'build', 'dist', '__pycache__',
})
FORBIDDEN_EXTENSIONS = frozenset({
    '.iso', '.xex', '.xbe', '.big', '.rdc', '.dmp', '.core', '.pyc',
    '.xsh', '.xpso', '.fxo', '.spv',
})


def portable_component(part):
    return (part not in {'.', '..'} and not part.endswith((' ', '.')) and
            not any(ord(char) < 32 or char in '\\:<>"|?*' for char in part))


def validate_package_path(relative, directory=False):
    """Reject private and nonportable names, even when their hashes match."""
    parts = relative.parts
    if (not parts or relative.is_absolute() or
            any(not portable_component(part) for part in parts) or
            any(part.lower() in FORBIDDEN_PARTS for part in parts) or
            relative.suffix.lower() in FORBIDDEN_EXTENSIONS):
        raise ValueError('Package boundary forbidden path: ' + relative.as_posix())
    name = relative.as_posix()
    if directory:
        allowed = (name in {'licenses', 'docs', 'docs/beta'} or
                   parts[0] == 'licenses' or
                   any(item.startswith(name + '/') for item in PUBLIC_FILES))
    else:
        allowed = name in PUBLIC_FILES
        if len(parts) == 3 and parts[:2] == ('docs', 'beta'):
            allowed = bool(re.fullmatch(r'[A-Za-z0-9_.-]+\.md', parts[-1]))
        if len(parts) >= 2 and parts[0] == 'licenses':
            # Dependency trees retain original license names and nested paths.
            allowed = (parts[-1].upper().startswith(('LICENSE', 'COPYING', 'NOTICE')) or
                       name in {'licenses/ReXGlue-LICENSE', 'licenses/extract-xiso-LICENSE.TXT',
                                'licenses/Microsoft-Visual-C-Runtime-NOTICE.txt',
                                'licenses/extract-xiso-win32-dirent.c',
                                'licenses/extract-xiso-win32-getopt.c'})
    if not allowed:
        raise ValueError('Package boundary forbidden path: ' + name)


def archive_package(package, destination):
    package = package.resolve()
    if not portable_component(package.name):
        raise ValueError('Package boundary forbidden archive root name')
    if not (destination.name.endswith('.tar.gz') or destination.suffix == '.zip'):
        raise ValueError('Unsupported archive format; use .tar.gz or .zip')
    manifest = json.loads((package / 'package-manifest.json').read_text())
    if manifest.get('owner') != 'djultra64' or manifest.get('game_assets_included') is not False:
        raise ValueError('Unrecognized public package')
    actual = {}
    for path in sorted(package.rglob('*')):
        if path.is_symlink():
            raise ValueError('Package symlinks are forbidden')
        if path.is_file() and path != package / 'package-manifest.json':
            actual[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != manifest['files']:
        raise ValueError('Package files differ from the recorded manifest')
    for path in sorted(package.rglob('*')):
        if not (stat.S_ISREG(path.lstat().st_mode) or path.is_dir()):
            raise ValueError('Package boundary forbidden special file')
        validate_package_path(path.relative_to(package), directory=path.is_dir())
    if destination.exists():
        raise ValueError('Archive already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == '.zip':
        with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(package.rglob('*')):
                if not path.is_file():
                    continue
                info = zipfile.ZipInfo((Path(package.name) / path.relative_to(package)).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100755 if path.stat().st_mode & 0o111 else 0o100644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    else:
        with tarfile.open(destination, 'w:gz') as archive:
            for path in [package, *sorted(package.rglob('*'))]:
                info = archive.gettarinfo(str(path), arcname=str(Path(package.name) / path.relative_to(package)))
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                info.mode = (0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
                if path.is_file():
                    with path.open('rb') as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    checksums = destination.parent / 'SHA256SUMS'
    entries = checksums.read_text().splitlines() if checksums.exists() else []
    entries = [entry for entry in entries if entry.split('  ', 1)[-1] != destination.name]
    entries.append(f'{digest}  {destination.name}')
    checksums.write_text('\n'.join(sorted(entries)) + '\n')
    return digest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(archive_package(args.package, args.output))
