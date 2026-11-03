#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Actual POSIX journal, process death and offline backup/restore tests."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
DRIVER = r'''
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <cerrno>
#include <cstdio>
static int stop_at, calls; static bool crash, io_failure;
static bool fail_io() { return io_failure && ++calls == stop_at; }
static ssize_t test_write(int fd, const void *p, size_t n) {
    if(fail_io()){errno=ENOSPC;return -1;} return ::write(fd,p,n);
}
static int test_fsync(int fd) { if(fail_io()){errno=EIO;return -1;}return ::fsync(fd); }
static int test_rename(const char *a,const char *b) { if(fail_io()){errno=EIO;return -1;}return ::rename(a,b); }
static void point(const char *name) {
    if (io_failure) return;
    if (++calls != stop_at) return;
    if (crash) _exit(std::strcmp(name,"committed")==0 ? 86 : 85);
    throw "injected failure";
}
#define UPLOADER_TXN_POINT(name) point(name)
#define write test_write
#define fsync test_fsync
#define rename test_rename
#include "StorageTransaction.h"
int main(int argc, char **argv) {
    if (argc!=4) return 2;
    stop_at=std::atoi(argv[2]); crash=std::strcmp(argv[3],"crash")==0;
    io_failure=std::strcmp(argv[3],"io")==0;
    const std::string root=argv[1];
    try {
        StorageTransaction tx((root+"/data").c_str());
        tx.create_bytes((root+"/data/02/2").c_str(), "new metadata", 12);
        tx.create_bytes((root+"/file/02/2.txt").c_str(), "new payload", 11);
        tx.temporary_file((root+"/thumb/02/2.gif.uploader-preview").c_str());
        tx.remove_file((root+"/data/01/1").c_str());
        tx.remove_file((root+"/file/01/1.txt").c_str());
        tx.commit();
    } catch (...) {return 1;}
    return 0;
}
'''

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--workdir',type=Path,required=True); args=parser.parse_args()
    root=Path(tempfile.mkdtemp(prefix='storage-test-',dir=args.workdir)).resolve()
    cpp=root/'driver.cpp'; cpp.write_text(DRIVER); executable=root/'driver'
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(SOURCE/'include'),str(cpp),'-o',str(executable)],check=True)
    checks=0
    def check(value):
        nonlocal checks
        assert value; checks+=1
    def run(*args, ok=True):
        result=subprocess.run([str(x) for x in args],capture_output=True)
        if ok and result.returncode: raise AssertionError(result.stderr.decode(errors='replace'))
        return result
    def dataset(name):
        d=root/name
        for folder in ['data','file','thumb','temp']:
            (d/folder/'01').mkdir(parents=True); (d/folder/'02').mkdir()
        (d/'data/01/1').write_bytes(b'old metadata'); (d/'file/01/1.txt').write_bytes(b'old payload')
        (d/'data/.csrf-key').write_bytes(bytes(range(32))); os.chmod(d/'data/.csrf-key',0o600)
        return d
    def options(d): return sum((['--'+x+'-dir',str(d/x)] for x in ['data','file','thumb','temp']),[])
    btool=SOURCE/'util/storage_backup.py'; rtool=SOURCE/'util/storage_recover.py'
    for mode in ['throw','crash','io']:
        for index in range(1,81 if mode=='io' else 14):
            d=dataset(mode+str(index)); result=run(executable,d,index,mode,ok=False)
            committed=(d/'data/.storage-transaction/COMMITTED').exists()
            check(result.returncode in (0,1,85,86))
            recovery=[sys.executable,rtool,*options(d),'--server-stopped']
            run(*recovery)
            run(*recovery,'--apply','--rescue-backup',root/(d.name+'-rescue'))
            # After rollback the exact original content survives; after commit new survives.
            new=committed or result.returncode==0
            check((d/'data/02/2').exists()==new and (d/'data/01/1').exists()!=new)
            check((d/'file/02/2.txt').exists()==new and (d/'file/01/1.txt').exists()!=new)
            check((d/('file/02/2.txt' if new else 'file/01/1.txt')).read_bytes()==(b'new payload' if new else b'old payload'))
            check(not (d/'data/.storage-transaction').exists())
            check(not [p for p in d.rglob('*') if '.uploader-' in p.name])
    d=dataset('backup'); snapshot=root/'snapshot'; restore=root/'restored'
    create=[sys.executable,btool,'create',*options(d),'--output',snapshot]
    check(run(*create,ok=False).returncode!=0)
    lock=(d/'data/.format-lock').open('a'); fcntl.flock(lock,fcntl.LOCK_SH)
    check(run(*create,'--server-stopped',ok=False).returncode!=0); lock.close()
    run(*create,'--server-stopped'); checks+=1
    run(sys.executable,btool,'verify',snapshot); checks+=1
    run(sys.executable,btool,'restore',snapshot,'--destination',restore); checks+=1
    check((restore/'data/.csrf-key').read_bytes()==bytes(range(32)))
    check((restore/'data/.csrf-key').stat().st_mode & 0o777 == 0o600)
    check((restore/'file/01/1.txt').read_bytes()==b'old payload')
    check(run(sys.executable,btool,'restore',snapshot,'--destination',d/'file',ok=False).returncode!=0)
    check(run(*create,'--server-stopped',ok=False).returncode!=0)
    (snapshot/'snapshot/file/01/1.txt').write_bytes(b'tampered')
    check(run(sys.executable,btool,'verify',snapshot,ok=False).returncode!=0)
    check(run(sys.executable,btool,'restore',snapshot,'--destination',root/'must-not-exist',ok=False).returncode!=0)
    check(not (root/'must-not-exist').exists())
    (d/'file/01/link').symlink_to(d/'data/.csrf-key')
    check(run(sys.executable,btool,'create',*options(d),'--output',root/'unsafe','--server-stopped',ok=False).returncode!=0)
    # An untrusted journal cannot remove any file outside the selected dataset.
    evil=dataset('evil'); j=evil/'data/.storage-transaction';j.mkdir()
    protected=root/'protected'; protected.write_bytes(b'keep')
    (j/'plan').write_bytes(b'UPLOADER-TXN-1\nC '+str(protected).encode().hex().encode()+b'\n')
    check(run(sys.executable,rtool,*options(evil),'--server-stopped','--apply','--rescue-backup',root/'evil-rescue',ok=False).returncode!=0)
    check(protected.read_bytes()==b'keep')
    health=[sys.executable,SOURCE/'util/storage_health.py',*options(d)]
    check(run(*health,ok=False).returncode==0)
    check(run(*health,'--min-free-percent','100',ok=False).returncode==1)
    check(run(sys.executable,SOURCE/'util/storage_health.py',*options(evil),ok=False).returncode==1)
    print(f'storage: {checks} checks passed; fixtures retained: {root}')

if __name__=='__main__': main()
