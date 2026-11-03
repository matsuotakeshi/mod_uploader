#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Inspect/recover an interrupted storage transaction, with Apache stopped."""
import argparse
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import storage_backup as backup

def remove(path):
    if path.exists() or path.is_symlink():
        backup.regular(path); path.unlink(); backup.syncdir(path.parent)

def plan(roots):
    journal = roots['data'] / '.storage-transaction'
    if not journal.exists(): return journal, [], False
    backup.directory(journal)
    allowed = {'plan', 'commit-ready', 'COMMITTED'}
    if any(p.name not in allowed for p in journal.iterdir()): raise ValueError('Unexpected journal entry')
    for p in journal.iterdir(): backup.regular(p)
    committed = (journal / 'COMMITTED').exists()
    if not (journal / 'plan').exists(): return journal, [], committed
    if (journal / 'plan').stat().st_size > 64 * 1024 * 1024: raise ValueError('Journal too large')
    raw = (journal / 'plan').read_bytes()
    magic = b'UPLOADER-TXN-1\n'
    if not raw.startswith(magic):
        if magic.startswith(raw): return journal, [], committed
        raise ValueError('Unknown journal format')
    operations = []
    seen = set()
    # A final partial row cannot have mutated a file: C++ fsyncs the row first.
    for row in raw[len(magic):].split(b'\n')[:-1]:
        kind, encoded = row.split(b' ', 1)
        if kind not in (b'C', b'D', b'P') or not re.fullmatch(b'[0-9a-f]+', encoded):
            raise ValueError('Invalid journal operation')
        name = os.fsdecode(bytes.fromhex(encoded.decode('ascii')))
        path = Path(name)
        if '\x00' in name or '..' in path.parts or str(path) != name or not path.is_absolute():
            raise ValueError('Unsafe journal path')
        canonical_parent = backup.directory(path.parent)
        matches = [(label, root) for label, root in roots.items() if root == canonical_parent.parent]
        if len(matches) != 1: raise ValueError('Journal path outside supplied storage roots: ' + name)
        label, root = matches[0]
        if label == 'temp' or not re.fullmatch(r'[0-9a-f]{2}', path.parent.name): raise ValueError('Invalid storage bucket')
        path = canonical_parent / path.name
        filename = path.name
        if kind == b'P':
            if label != 'thumb' or not filename.endswith('.uploader-preview'): raise ValueError('Invalid preview entry')
            filename = filename.removesuffix('.uploader-preview')
        pattern = r'[1-9][0-9]*' if label == 'data' else r'''[1-9][0-9]*\.[^./\\\x00-\x1f\x7f<>"'&]+'''
        if not re.fullmatch(pattern, filename): raise ValueError('Invalid storage filename')
        number = int(filename.split('.')[0])
        if path.parent.name != f'{number & 255:02x}': raise ValueError('Incorrect storage bucket')
        if name in seen: raise ValueError('Duplicate journal target')
        seen.add(name)
        for p in (path, Path(name + '.uploader-new'), Path(name + '.uploader-old')):
            if p.exists() or p.is_symlink(): backup.regular(p)
        operations.append((kind, path))
    return journal, operations, committed

def run(args):
    if not args.server_stopped: raise ValueError('Stop every Apache using this storage and pass --server-stopped')
    roots = {name: backup.directory(getattr(args, name + '_dir')) for name in backup.ROOTS}
    for a in roots.values():
        for b in roots.values():
            if a != b and (a in b.parents or b in a.parents): raise ValueError('Storage roots overlap')
    if len(set(roots.values())) != 4: raise ValueError('Storage roots overlap')
    with backup.stopped_lock(roots['data']):
        journal, operations, committed = plan(roots)
        if not journal.exists(): print('No pending storage transaction'); return
        print(('Finish committed transaction' if committed else 'Roll back interrupted transaction') + f': {len(operations)} operations')
        if not args.apply:
            print('Inspection only; use --apply --rescue-backup NEW_DIRECTORY after reviewing'); return
        if not args.rescue_backup: raise ValueError('--apply requires --rescue-backup NEW_DIRECTORY')
        snapshot_args = SimpleNamespace(**{name + '_dir': str(root) for name, root in roots.items()},
            output=args.rescue_backup, extra=[], server_stopped=True, allow_incomplete=True)
        backup.create(snapshot_args, already_locked=True)
        for kind, path in reversed(operations):
            old = Path(str(path) + '.uploader-old')
            stage = Path(str(path) + '.uploader-new')
            if kind == b'P': remove(path)
            elif not committed:
                if kind == b'C': remove(path)
                elif old.exists():
                    if path.exists(): raise ValueError('Both original and rollback file exist; manual review needed')
                    old.rename(path); backup.syncdir(path.parent)
            remove(stage)
            if committed: remove(old)
        for name in ('commit-ready', 'plan', 'COMMITTED'): remove(journal / name)
        journal.rmdir(); backup.syncdir(journal.parent)
        print('Storage recovery complete; restart Apache to reconstruct shared state')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in backup.ROOTS: parser.add_argument('--' + name + '-dir', required=True)
    parser.add_argument('--server-stopped', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rescue-backup')
    args = parser.parse_args(); os.umask(0o077)
    try: run(args)
    except Exception as exc: print('Recovery stopped: ' + str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())
