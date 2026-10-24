#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Offline migration. Back up and verify all roots before replacing any metadata."""
import argparse, fcntl, hashlib, json, os, shutil, stat, subprocess, tempfile
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def scan(root):
    result={}
    for base, dirs, files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name;s=p.lstat()
            if stat.S_ISLNK(s.st_mode) or not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)):
                raise RuntimeError('Symlinks and special files are not supported: '+str(p))
            if stat.S_ISREG(s.st_mode):
                if s.st_nlink!=1: raise RuntimeError('Hard-linked files are not supported: '+str(p))
                result[str(p.relative_to(root))]={'sha256':digest(p),'size':s.st_size,'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}
    return result

def syncdir(path):
    fd=os.open(path,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def journal(backup,state):
    p=backup/'journal.json';tmp=backup/'journal.tmp'
    with tmp.open('w',encoding='utf8') as f:
        json.dump(state,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p);syncdir(backup)

def tool_run(tool,*args):
    return subprocess.run([str(tool),*map(str,args)],check=True,capture_output=True)

def migrate_locked(args):
    if not args.server_stopped: raise RuntimeError('Stop every server using these directories and pass --server-stopped')
    tool=Path(args.tool).resolve(strict=True)
    roots={name:Path(getattr(args,name+'_dir')).resolve(strict=True) for name in ['data','file','thumb']}
    if args.temp_dir:roots['temp']=Path(args.temp_dir).resolve(strict=True)
    backup=Path(args.backup_dir).absolute()
    if backup.exists() or backup.is_symlink():raise RuntimeError('Backup destination must not exist')
    parent=backup.parent.resolve(strict=True);backup=parent/backup.name
    for a in roots.values():
        if not a.is_dir():raise RuntimeError('Every source must be a directory')
        if backup==a or a in backup.parents or backup in a.parents:raise RuntimeError('Backup and source roots must be disjoint')
    paths=list(roots.values())
    for i,a in enumerate(paths):
        for b in paths[i+1:]:
            if a==b or a in b.parents or b in a.parents:raise RuntimeError('Source roots must be disjoint')
    inventory={name:scan(path) for name,path in roots.items()}
    sentinel=roots['data']/'.migration-in-progress'
    if sentinel.exists():raise RuntimeError('Previous migration is incomplete: restore its backup first')
    backup.mkdir(mode=0o700);os.chmod(backup,0o700)
    state={'state':'backup-in-progress','format':1,'inventory':inventory,'converted':[]}
    journal(backup,state)
    # No source changes before this entire backup is complete and verified.
    for name,root in roots.items():
        target=backup/'snapshot'/name
        target.parent.mkdir(mode=0o700,exist_ok=True)
        # FreeBSD cp -a preserves ACLs, flags, ownership, modes and timestamps.
        subprocess.run(['/bin/cp','-a',str(root),str(target)],check=True,capture_output=True)
        copied=scan(target)
        if any(n not in copied or copied[n]['sha256']!=meta['sha256'] for n,meta in inventory[name].items()) or set(copied)!=set(inventory[name]):
            raise RuntimeError('Backup verification failed; no metadata was changed')
        for base,dirs,files in os.walk(target):
            for file in files:
                with (Path(base)/file).open('rb') as f:os.fsync(f.fileno())
            syncdir(base)
    syncdir(backup/'snapshot');syncdir(backup)
    state['state']='backup-verified';journal(backup,state)
    prepared=backup/'prepared';prepared.mkdir(mode=0o700)
    candidates=[]
    for rel in sorted(inventory['data']):
        # This is the exact two-hex-digit / decimal filename layout used by UploadItemIO.
        parts=Path(rel).parts
        if len(parts)!=2 or len(parts[0])!=2 or any(c not in '0123456789abcdef' for c in parts[0]) or not parts[1].isascii() or not parts[1].isdigit():continue
        source=roots['data']/rel
        info=json.loads(tool_run(tool,'--inspect',source).stdout)
        if info['id']!=int(parts[1]) or parts[0]!=format(info['id']&255,'02x'):raise RuntimeError('Metadata id/path mismatch: '+rel)
        dest=prepared/rel;dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        tool_run(tool,'--convert',source,dest)
        if json.loads(tool_run(tool,'--inspect',dest).stdout)['version']!=4:raise RuntimeError('Prepared metadata was not v4')
        candidates.append(rel)
    # Reject any concurrent source modification, including payload/thumbnail changes.
    if any(scan(root)!=inventory[name] for name,root in roots.items()):raise RuntimeError('Source changed during backup/preparation; no metadata was changed')
    state['state']='prepared';state['candidates']=candidates;journal(backup,state)
    # The new module refuses startup while this marker exists. Old processes must be stopped.
    fd=os.open(sentinel,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.write(fd,b'Offline password migration in progress. Restore backup if interrupted.\n');os.fsync(fd);os.close(fd);syncdir(roots['data'])
    try:
        state['state']='converting';journal(backup,state)
        for rel in candidates:
            source=roots['data']/rel;meta=inventory['data'][rel]
            if digest(source)!=meta['sha256']:raise RuntimeError('Metadata changed before replacement')
            fd,name=tempfile.mkstemp(prefix='.password-migration-',dir=source.parent)
            try:
                with os.fdopen(fd,'wb') as f:
                    f.write((prepared/rel).read_bytes());f.flush();os.fsync(f.fileno())
                if os.geteuid()==0:os.chown(name,meta['uid'],meta['gid'])
                elif source.stat().st_uid!=os.geteuid():raise RuntimeError('Run as the file owner or root')
                os.chmod(name,0o600);os.replace(name,source);syncdir(source.parent)
            finally:
                if os.path.exists(name):os.unlink(name)
            state['converted'].append(rel);journal(backup,state)
        state['state']='complete';journal(backup,state)
        sentinel.unlink();syncdir(roots['data'])
    except BaseException:
        state['state']='interrupted-restore-backup';journal(backup,state)
        raise
    print('Migration complete: '+str(len(candidates))+' metadata files. Verified backup: '+str(backup))
    print('Rollback: stop Apache, restore the entire snapshot (data/file/thumb and optional temp), then reinstall the old module and templates.')

def migrate(args):
    if not args.server_stopped:raise RuntimeError('Stop every old server and pass --server-stopped')
    root=Path(args.data_dir).resolve(strict=True)
    fd=os.open(root/'.format-lock',os.O_RDONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise RuntimeError('Unsafe lock file')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('The new server or another migration is using this data directory')
        return migrate_locked(args)
    finally:os.close(fd)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['data','file','thumb']:p.add_argument('--'+name+'-dir',required=True)
    p.add_argument('--temp-dir');p.add_argument('--backup-dir',required=True)
    p.add_argument('--tool',required=True);p.add_argument('--server-stopped',action='store_true')
    args=p.parse_args()
    try:migrate(args)
    except Exception as e:
        # Converter errors never include password bytes. Do not print its captured input.
        print('Migration failed: '+str(e));raise SystemExit(1)
if __name__=='__main__':main()
