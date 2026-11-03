#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Verified offline snapshots. Restore only into a new, private destination."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile

ROOTS = ('data', 'file', 'thumb', 'temp')
FORMAT = 'mod_uploader-backup-1'

def syncdir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)

def directory(path):
    path = Path(os.path.abspath(path))
    # Canonicalize administrator-provided ancestors (FreeBSD /home can be a link),
    # but never follow a snapshot entry or dataset root that is itself a link.
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError('Not a real directory: ' + str(path))
    return path.resolve(strict=True)

def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Links and special files are not supported: ' + str(path))
    return info

def digest(path):
    before = regular(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        current = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
            raise ValueError('File changed during open')
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''): value.update(block)
    after = regular(path)
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('File changed while hashing')
    return value.hexdigest()

def inventory(root):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(base) / name
            info = path.lstat()
            rel = path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                result[rel] = {'kind': 'dir', 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
            else:
                regular(path)
                result[rel] = {'kind': 'file', 'size': info.st_size, 'sha256': digest(path), 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
    return result

def content(inventory):
    return {name: {key: value for key, value in row.items() if key in ('kind', 'size', 'sha256')} for name, row in inventory.items()}

def safe_name(name):
    path = PurePosixPath(name)
    if not isinstance(name, str) or not name or path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')) or '\\' in name or '\0' in name:
        raise ValueError('Unsafe snapshot path')
    return path

@contextlib.contextmanager
def stopped_lock(root):
    fd = os.open(root / '.format-lock', os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Unsafe storage lock')
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Stop all Apache processes using this storage first')
        yield
    finally: os.close(fd)

def copy_tree(source, target):
    # FreeBSD cp preserves ACLs, flags, modes and ownership where permitted.
    subprocess.run(['/bin/cp', '-a', str(source), str(target)], check=True)
    for base, _, files in os.walk(target):
        for name in files:
            fd = os.open(Path(base) / name, os.O_RDONLY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
        syncdir(base)

def create(args, already_locked=False):
    if not args.server_stopped:
        raise ValueError('Stop every Apache using this storage and pass --server-stopped')
    roots = {name: directory(getattr(args, name + '_dir')) for name in ROOTS}
    for extra in args.extra:
        name, separator, path = extra.partition('=')
        if not separator or not name.isascii() or not name.replace('-', '').replace('_', '').isalnum() or name in roots:
            raise ValueError('--extra requires a unique simple NAME=DIRECTORY')
        roots[name] = directory(path)
    destination = Path(os.path.abspath(args.output))
    parent = directory(destination.parent)
    destination = parent / destination.name
    if destination.exists() or destination.is_symlink(): raise ValueError('Snapshot destination already exists')
    all_paths = [*roots.values(), destination]
    for i, a in enumerate(all_paths):
        for b in all_paths[i + 1:]:
            if a == b or a in b.parents or b in a.parents: raise ValueError('Source and destination roots must be disjoint')
    with contextlib.nullcontext() if already_locked else stopped_lock(roots['data']):
        if not getattr(args, 'allow_incomplete', False) and any((roots['data'] / marker).exists() for marker in ('.migration-in-progress', '.storage-transaction')):
            raise ValueError('Recover interrupted storage work before creating a regular backup')
        before = {name: inventory(path) for name, path in roots.items()}
        temporary = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.incomplete-', dir=parent))
        # Incomplete snapshots are retained for diagnosis; only a verified one is published.
        snapshot = temporary / 'snapshot'; snapshot.mkdir(mode=0o700)
        for name, source in roots.items():
            copy_tree(source, snapshot / name)
            if content(inventory(snapshot / name)) != content(before[name]): raise ValueError('Backup content verification failed')
        if any(inventory(path) != before[name] for name, path in roots.items()): raise ValueError('Source changed during backup')
        manifest = {'format': FORMAT, 'recovery_snapshot': getattr(args, 'allow_incomplete', False), 'roots': before, 'source_paths': {name: str(path) for name, path in roots.items()}}
        with (temporary / 'manifest.json').open('x', encoding='utf8') as stream:
            json.dump(manifest, stream, ensure_ascii=True, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        syncdir(snapshot); syncdir(temporary)
        # Rename is within the same parent filesystem; destination is new and private.
        if destination.exists(): raise ValueError('Snapshot destination appeared during backup')
        os.rename(temporary, destination); syncdir(parent)
    verify(destination)
    print('Backup created and verified: ' + str(destination))

def verify(path):
    path = directory(path)
    regular(path / 'manifest.json')
    if (path / 'manifest.json').stat().st_size > 64 * 1024 * 1024: raise ValueError('Manifest exceeds safety limit')
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf8'))
    if manifest.get('format') != FORMAT or not isinstance(manifest.get('roots'), dict): raise ValueError('Unsupported backup manifest')
    if not set(ROOTS).issubset(manifest['roots']): raise ValueError('Required storage roots missing')
    snapshot = directory(path / 'snapshot')
    if {p.name for p in snapshot.iterdir()} != set(manifest['roots']): raise ValueError('Unexpected snapshot roots')
    for name, expected in manifest['roots'].items():
        if len(safe_name(name).parts) != 1 or not isinstance(expected, dict): raise ValueError('Invalid snapshot root')
        for rel, row in expected.items():
            safe_name(rel)
            if row.get('kind') not in ('dir', 'file'): raise ValueError('Invalid inventory record')
            if any(type(row.get(k)) is not int or row[k] < 0 for k in ('mode', 'uid', 'gid')) or row['mode'] > 0o7777:
                raise ValueError('Invalid ownership or mode')
        if content(inventory(directory(snapshot / name))) != content(expected): raise ValueError('Snapshot content mismatch: ' + name)
    return manifest

def restore(args):
    backup = directory(args.backup)
    manifest = verify(backup)
    destination = Path(os.path.abspath(args.destination))
    parent = directory(destination.parent)
    destination = parent / destination.name
    if destination.exists() or destination.is_symlink(): raise ValueError('Restore destination must not exist; live storage is never overwritten')
    if backup == destination or backup in destination.parents or destination in backup.parents: raise ValueError('Restore and backup paths overlap')
    for value in manifest.get('source_paths', {}).values():
        source = Path(value)
        if destination == source or source in destination.parents or destination in source.parents:
            raise ValueError('Restore destination overlaps original live storage')
    if args.preserve_owner and os.geteuid() != 0: raise ValueError('--preserve-owner requires root')
    temporary = Path(tempfile.mkdtemp(prefix='.' + destination.name + '.incomplete-', dir=parent))
    for name, expected in manifest['roots'].items():
        target = temporary / name
        copy_tree(backup / 'snapshot' / name, target)
        if content(inventory(target)) != content(expected): raise ValueError('Restored content mismatch')
        # Dataset roots stay private. Root can restore original per-file owners on request.
        os.chmod(target, 0o700)
        for rel, row in sorted(expected.items(), key=lambda item: len(PurePosixPath(item[0]).parts), reverse=True):
            path = target / rel
            if args.preserve_owner: os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
            os.chmod(path, row['mode'] & 0o777, follow_symlinks=False)
        if args.preserve_owner:
            source = backup / 'snapshot' / name
            info = source.stat(); os.chown(target, info.st_uid, info.st_gid)
    verify(backup)
    syncdir(temporary)
    if destination.exists(): raise ValueError('Restore destination appeared')
    os.rename(temporary, destination); syncdir(parent)
    print('Restored and verified into NEW destination: ' + str(destination))
    print('Keep Apache stopped during the administrator-controlled switch; confirm owners and config before startup.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('create')
    for name in ROOTS: p.add_argument('--' + name + '-dir', required=True)
    p.add_argument('--extra', action='append', default=[], metavar='NAME=DIRECTORY')
    p.add_argument('--output', required=True); p.add_argument('--server-stopped', action='store_true')
    p = sub.add_parser('verify'); p.add_argument('backup')
    p = sub.add_parser('restore'); p.add_argument('backup'); p.add_argument('--destination', required=True)
    p.add_argument('--preserve-owner', action='store_true')
    args = parser.parse_args(); os.umask(0o077)
    try:
        if args.command == 'create': create(args)
        elif args.command == 'restore': restore(args)
        else: verify(args.backup); print('Backup content verified')
    except Exception as exc:
        print('Backup operation failed: ' + str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())
