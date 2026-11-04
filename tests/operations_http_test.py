#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Loopback tests for failure statuses, write failure, backups and bounded decoding."""
import argparse
import os
from pathlib import Path
import re
import socket
import struct
import sys
import tempfile
import time
import zlib
from security_http_test import Server, Client, setup, run
from root_http_test import png
from apache_paths import program

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--workdir',type=Path,required=True);p.add_argument('--thumbnail',action='store_true');p.add_argument('--tools-root',type=Path);a=p.parse_args()
    build=a.build_root.resolve(); source=Path(__file__).resolve().parents[1]
    utilities=a.tools_root.resolve() if a.tools_root else source/'util'
    root=Path(tempfile.mkdtemp(prefix='operations-http-',dir=a.workdir));setup(root,build/'src/password_tool')
    def paths(d):return sum((['--'+n+'-dir',str(d/n)] for n in ['data','file','thumb','temp']),[])
    run(sys.executable,utilities/'migrate_passwords.py','--tool',build/'src/password_tool','--backup-dir',root/'migration-backup','--server-stopped',*paths(root))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    s=Server(root,build,port);s.conf.write_text('Define UPLOADER_DEBUG\n'+s.conf.read_text().replace('UploaderTotalFileNumberLimit 100','UploaderTotalFileNumberLimit 1'))
    checks=0
    def check(ok,why):
        nonlocal checks
        assert ok,(why,root);checks+=1
    def upload(c,name,data,code_pat=''):
        return c.request('/up/upload/',[('file',(name,data)),('comment','operations test'),('remove_pass',''),('download_pass',''),('code_pat',code_pat),('csrf_token',c.token)])
    try:
        s.start();c=Client(port);c.index()
        check(c.request('/up/unknown')[0]==404,'unknown command status')
        check(c.request('/up/download/999.txt')[0]==404,'missing item status')
        check(c.request('/up/download/1.txt',[('download_pass','wrong'),('csrf_token',c.token)])[0]==403,'wrong password status')
        check(upload(c,'bad<name>.txt',b'bad')[0]==400,'invalid name status')
        check(upload(c,'large.bin',b'x'*1048577)[0]==413,'size status (1 MiB limit = 1024 KiB)')
        backup=[sys.executable,utilities/'storage_backup.py','create',*paths(root),'--output',root/'live-backup','--server-stopped']
        run(*backup,code=1);check(not (root/'live-backup').exists(),'live backup refused')
        original=(root/'data/01/1').read_bytes()
        directories=[root/'file',*(p for p in (root/'file').iterdir() if p.is_dir())]
        for d in directories:os.chmod(d,0o500)
        try:status,_,_=upload(c,'write-fails.txt',b'new file')
        finally:
            for d in directories:os.chmod(d,0o700)
        check(status>=500,'write failure status')
        check((root/'data/01/1').read_bytes()==original and (root/'file/01/1.txt').read_bytes()==b'fixture-content\n','existing upload retained on real permission failure')
        check(not (root/'data/.storage-transaction').exists(),'failed upload rolled back')
        check(c.request('/up/')[0]==200,'server remains responsive')
        cases=[('valid.png',png(),True),('svg.png',b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"/>',False),
            ('pdf.png',b'%PDF-1.5\n',False),('mvg.png',b'push graphic-context\nviewbox 0 0 20 20\npop graphic-context',False),
            ('bad.png',b'\x89PNG\r\n\x1a\ninvalid',False)]
        oversized=bytearray(png());oversized[16:24]=struct.pack('>II',100000,100000);oversized[29:33]=struct.pack('>I',zlib.crc32(oversized[12:29])&0xffffffff)
        cases.append(('huge.png',bytes(oversized),False))
        if a.thumbnail:
            # Generate real JPEG/GIF/WebP fixtures with the configured ImageMagick command.
            binary=program('MAGICK_CONVERT','magick','convert')
            for fmt in ['jpg','gif','webp']:
                image=root/('fixture.'+fmt);run(binary,'-size','24x18','xc:#2277aa',image)
                cases.append(('valid.'+fmt,image.read_bytes(),True))
        last=None
        for name,data,thumbnail in cases:
            started=time.monotonic();status,_,body=upload(c,name,data)
            m=re.search(rb'/info/(\d+)',body);check(status==200 and m is not None,'upload '+name)
            item=m[1].decode();ext=name.rsplit('.',1)[1];last=(item,ext,data)
            check(c.request('/up/download/'+item+'.'+ext)[2]==data,'original preserved '+name)
            thumb=[p for p in (root/'thumb').glob('*/*.gif') if p.name==item+'.gif']
            check(bool(thumb)==(a.thumbnail and thumbnail),'thumbnail policy '+name)
            if thumb:check(thumb[0].read_bytes()[:6] in (b'GIF87a',b'GIF89a'),'real GIF output')
            check(time.monotonic()-started<15,'bounded processing '+name)
            check(not (root/'data/.storage-transaction').exists(),'journal cleanup '+name)
        check(not list((root/'temp').iterdir()),'temporary upload cleanup')
        status,_,body=upload(c,'画像.png',png(),b'\xe4')
        found=re.search(rb'/info/(\d+)',body);check(status==200 and found is not None,'UTF-8 filename accepted')
        item=found[1].decode();last=(item,'png',png())
        check('画像.png'.encode('euc_jp') in c.request('/up/')[2],'iconv converts Japanese filename to page encoding')
        check(c.request('/up/download/'+item+'.png')[2]==png(),'Japanese filename payload retained')
        s.stop()
        run(sys.executable,utilities/'storage_backup.py','create',*paths(root),'--output',root/'verified-backup','--server-stopped');checks+=1
        run(sys.executable,utilities/'storage_backup.py','restore',root/'verified-backup','--destination',root/'restored');checks+=1
        restored=Server(root/'restored',build,port)
        try:
            restored.start();r=Client(port);r.index();check(r.request('/up/download/'+last[0]+'.'+last[1])[2]==last[2],'restored data served by Apache')
        finally:restored.stop()
        journal=root/'data/.storage-transaction';journal.mkdir();(journal/'plan').write_bytes(b'UPLOADER-TXN-1\n')
        s.start(success=False);s.stop();checks+=1
        run(sys.executable,utilities/'storage_recover.py',*paths(root),'--server-stopped','--apply','--rescue-backup',root/'recovery-backup');checks+=1
        s.start();check(c.request('/up/')[0]==200,'restart after journal recovery')
        s.stop(); configuration=s.conf.read_text()
        for invalid in ['-1','0','9007199254740992','1024KiB']:
            s.conf.write_text(configuration.replace('UploaderFileSizeLimit 1024','UploaderFileSizeLimit '+invalid))
            s.start(success=False);s.stop();checks+=1
        s.conf.write_text(configuration)
    finally:s.stop()
    print(f'operations-http: {checks} checks passed; thumbnail={a.thumbnail}; fixtures retained: {root}')

if __name__=='__main__':main()
