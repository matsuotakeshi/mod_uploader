#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
import argparse, hashlib, importlib.util, json, os, re, shutil, subprocess, tempfile
from pathlib import Path

def run(*args,code=0,input=None):
    p=subprocess.run(list(map(str,args)),input=input,capture_output=True)
    assert p.returncode==code,(p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace'))
    return p

def setup(root,tool,version=3):
    for name in ['data','file','thumb','temp']:(root/name).mkdir(parents=True)
    (root/'data/01').mkdir();(root/'file/01').mkdir()
    run(tool,'--fixture'+str(version),root/'data/01/1')
    (root/'file/01/1.txt').write_bytes(b'fixture-content\n')
    return {name:root/name for name in ['data','file','thumb','temp']}

def command(driver,tool,roots,backup):
    args=[os.sys.executable,driver,'--tool',tool,'--backup-dir',backup,'--server-stopped']
    for n,p in roots.items():args+=['--'+n+'-dir',p]
    return args

def main():
    p=argparse.ArgumentParser();p.add_argument('--tool',type=Path,required=True);p.add_argument('--workdir',type=Path);args=p.parse_args()
    tool=args.tool.resolve();driver=Path(__file__).resolve().parents[1]/'util/migrate_passwords.py'
    base=Path(tempfile.mkdtemp(prefix='migration-tests-',dir=args.workdir))
    checks=0
    for version in [2,3]:
        root=base/('v'+str(version));root.mkdir();roots=setup(root,tool,version);original=(roots['data']/'01/1').read_bytes()
        backup=root/'backup';run(*command(driver,tool,roots,backup))
        converted=(roots['data']/'01/1').read_bytes();assert converted[16:17]==b'4';checks+=1
        assert b'remove123' not in converted and b'download123' not in converted;checks+=1
        encodings=re.findall(rb'pbkdf2-sha256\$600000\$[0-9a-f]{32}\$[0-9a-f]{64}',converted)
        assert len(encodings)==2
        for encoded,password in zip(encodings,[b'remove123',b'download123']):
            _,rounds,salt,value=encoded.split(b'$')
            assert hashlib.pbkdf2_hmac('sha256',password,bytes.fromhex(salt.decode()),int(rounds)).hex()==value.decode();checks+=1
        assert (backup/'snapshot/data/01/1').read_bytes()==original;checks+=1
        assert (backup/'snapshot/file/01/1.txt').read_bytes()==(roots['file']/'01/1.txt').read_bytes();checks+=1
        assert (backup.stat().st_mode&0o777)==0o700;checks+=1
        for kind,password in [('remove',b'remove123\n'),('download',b'download123\n')]:
            run(tool,'--verify-'+kind,roots['data']/'01/1',input=password);checks+=1
            run(tool,'--verify-'+kind,roots['data']/'01/1',input=password.rstrip()+b'wrong\n',code=3);checks+=1
        run(*command(driver,tool,roots,backup),code=1);assert (roots['data']/'01/1').read_bytes()==converted;checks+=1
        run(*command(driver,tool,roots,root/'backup-again'));assert (roots['data']/'01/1').read_bytes()==converted;checks+=1
        assert json.loads((backup/'journal.json').read_text())['state']=='complete';checks+=1
    root=base/'empty';root.mkdir();roots=setup(root,tool,'3-empty')
    run(*command(driver,tool,roots,root/'backup'))
    run(tool,'--verify-remove',roots['data']/'01/1',input=b'');checks+=1
    run(tool,'--verify-download',roots['data']/'01/1',input=b'');checks+=1
    assert b'pbkdf2-sha256' not in (roots['data']/'01/1').read_bytes();checks+=1
    root=base/'corrupt';root.mkdir();roots=setup(root,tool);bad=roots['data']/'01/1';bad.write_bytes(b'bad metadata'*4);before=bad.read_bytes()
    run(*command(driver,tool,roots,root/'backup'),code=1);assert bad.read_bytes()==before;checks+=1
    root=base/'symlink';root.mkdir();roots=setup(root,tool);(roots['data']/'evil').symlink_to(roots['file']/'01/1.txt')
    run(*command(driver,tool,roots,root/'backup'),code=1);assert not (root/'backup').exists();checks+=1
    root=base/'no-ack';root.mkdir();roots=setup(root,tool);cmd=command(driver,tool,roots,root/'backup');cmd.remove('--server-stopped')
    run(*cmd,code=1);assert not (root/'backup').exists();checks+=1
    # Inject an interruption after the first atomic replacement, then restore the verified backup into a new tree.
    root=base/'interrupted';root.mkdir();roots=setup(root,tool);before=(roots['data']/'01/1').read_bytes()
    spec=importlib.util.spec_from_file_location('migration_under_test',driver);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    original_journal=m.journal;fired=[False]
    def interrupt(backup,state):
        original_journal(backup,state)
        if len(state.get('converted',[]))==1 and not fired[0]:fired[0]=True;raise KeyboardInterrupt('test interruption')
    m.journal=interrupt
    ns=argparse.Namespace(tool=str(tool),backup_dir=str(root/'backup'),server_stopped=True,**{n+'_dir':str(v) for n,v in roots.items()})
    try:m.migrate(ns);raise AssertionError('injected interruption missing')
    except KeyboardInterrupt:pass
    assert (roots['data']/'.migration-in-progress').is_file();checks+=1
    assert json.loads((root/'backup/journal.json').read_text())['state']=='interrupted-restore-backup';checks+=1
    shutil.copytree(root/'backup/snapshot',root/'restored')
    assert (root/'restored/data/01/1').read_bytes()==before;checks+=1
    assert not (root/'restored/data/.migration-in-progress').exists();checks+=1
    print('migration: '+str(checks)+' checks passed (native v2/v3, backups, idempotency, corrupt/symlink rejection, interruption/restore)')
    print('Disposable fixture directory retained for review: '+str(base))
if __name__=='__main__':main()
