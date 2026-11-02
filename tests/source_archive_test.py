#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Check the deliverable ZIP, including executable modes and Unix line endings."""
import argparse
import stat
import zipfile
from pathlib import PurePosixPath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')
    args = parser.parse_args()
    checks = 0
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None, 'ZIP CRC failure'
        checks += 1
        roots = {PurePosixPath(name).parts[0] for name in archive.namelist()}
        assert len(roots) == 1, 'Expected a single source root'
        root = roots.pop() + '/'
        for name in ['configure', 'build/config.guess', 'build/config.sub', 'util/unpack_literal.pl']:
            info = archive.getinfo(root + name)
            data = archive.read(info)
            assert data.startswith(b'#!') and b'\r' not in data.split(b'\n', 1)[0], name + ': invalid interpreter line'
            assert info.external_attr >> 16 & stat.S_IXUSR, name + ': not executable'
            checks += 2
        checked_files = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename[len(root):])
            if (path.name == 'configure' or path.name.startswith('GNUmakefile') or
                path.suffix in ('.sh', '.pl', '.py', '.m4') or
                path.parts[0] in ('build', 'ports')):
                assert b'\r\n' not in archive.read(info), str(path) + ': CRLF in Unix build input'
                checks += 1
                checked_files += 1
        assert checked_files > 30, 'Unexpectedly small source archive'
        checks += 1
    print('source-archive: ' + str(checks) + ' checks passed; ' + str(checked_files) + ' Unix build inputs checked')

if __name__ == '__main__':
    main()
