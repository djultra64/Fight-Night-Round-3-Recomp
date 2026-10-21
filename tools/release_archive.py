#!/usr/bin/env python3
"""Archive a verified public beta package without adding private files. Work: djultra64."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def archive_package(package, destination):
    package = package.resolve()
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
    if destination.exists():
        raise ValueError('Archive already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
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
