#!/usr/bin/env python3
"""Check the public source tree for private/proprietary inputs. Work: djultra64."""
import argparse
from pathlib import Path
import re

FORBIDDEN_DIRECTORIES = {'.cache', '.codex', '.codex-attachments', '.agents', '.release',
                         'assets', 'runtime', 'logs', 'build', 'dist', '__pycache__'}
FORBIDDEN_EXTENSIONS = {'.iso', '.xex', '.xbe', '.big', '.rdc', '.dmp', '.core', '.pyc'}
PRIVATE_TEXT = re.compile('alfredo' + r'lvera|Alfredo' + r' Olvera|/(?:var/)?home/[^/\s]+/|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[opusr]_[A-Za-z0-9]{30,}', re.I)


def audit(root):
    errors = []
    count = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts:
            continue
        if path.is_symlink():
            errors.append(str(relative) + ': unexpected symlink')
            continue
        if not path.is_file():
            continue
        count += 1
        if any(part in FORBIDDEN_DIRECTORIES for part in relative.parts):
            errors.append(str(relative) + ': private/generated directory')
        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            errors.append(str(relative) + ': original/private binary content')
        if relative.parts[0] == 'generated' and str(relative) != 'generated/rexglue.cmake':
            errors.append(str(relative) + ': generated guest content')
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(str(relative) + ': non-text source file')
            continue
        if PRIVATE_TEXT.search(text):
            errors.append(str(relative) + ': private identity/path/credential pattern')
    if errors:
        raise ValueError('\n'.join(errors))
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    try:
        print('Public source boundary audit passed: ' + str(audit(args.root)) + ' text files.')
    except ValueError as error:
        raise SystemExit(str(error))
