#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
import argparse, concurrent.futures, os, re, socket, tempfile
from pathlib import Path
from security_http_test import Server,Client,setup,run

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--workdir',type=Path);p.add_argument('--expect-vulnerable',action='store_true');args=p.parse_args()
    root=Path(tempfile.mkdtemp(prefix='audit-http-',dir=args.workdir));build=args.build_root.resolve();tool=build/'src/password_tool';setup(root,tool)
    driver=Path(__file__).resolve().parents[1]/'util/migrate_passwords.py'
    cmd=[os.sys.executable,driver,'--tool',tool,'--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:cmd+=['--'+name+'-dir',root/name]
    run(*cmd)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=Server(root,build,port);server.conf.write_text(server.conf.read_text().replace('UploaderTotalFileNumberLimit 100','UploaderTotalFileNumberLimit 1'))
    record=root/'data/01/1';payload=root/'file/01/1.txt';original=record.read_bytes();checks=0
    def upload(client,filename='invalid<name>.txt',comment='test',extra=None):
        fields=[('file',(filename,b'audit-data\n')),('comment',comment),('remove_pass',''),('download_pass',''),('code_pat',''),('csrf_token',client.token)]
        return client.request('/up/upload/',fields+(extra or []))
    try:
        server.start();a=Client(port);a.index()
        upload(a)
        if args.expect_vulnerable:
            assert not record.exists() and not payload.exists()
            print('baseline reproduced: invalid upload evicted existing protected fixture before validation')
            return
        assert record.read_bytes()==original and payload.read_bytes()==b'fixture-content\n';checks+=1
        # Invalid encodings must not silently become a different comment or remove old files.
        fields=[('file',('valid.txt',b'audit')),('comment',b'prefix\xffsuffix'),('remove_pass',''),('download_pass',''),('code_pat',b'\xe4'),('csrf_token',a.token)]
        a.request('/up/upload/',fields);assert record.read_bytes()==original;checks+=1
        for extra in [[('comment','second')],[('file',('extra.txt',b'other'))]]:
            upload(a,'valid.txt',extra=extra);assert record.read_bytes()==original;checks+=1
        # Password suffixes containing NUL must not authenticate as their C-string prefix.
        body=a.request('/up/download/1.txt',[('download_pass',b'download123\0suffix'),('csrf_token',a.token)])[2]
        assert body!=b'fixture-content\n';checks+=1
        upload(a,'valid.txt',comment=b'prefix\0suffix');assert record.read_bytes()==original;checks+=1
        (root/'thumb/01').mkdir();(root/'thumb/01/1.gif').write_bytes(b'GIF89a-test-only')
        assert a.request('/up/thumbnail/view/1.gif')[0]==403;checks+=1
        # Mail is also a privileged parser entry point even if Apache says Require local.
        assert a.request('/up/mail/',[('csrf_token',a.token)])[0]==403;checks+=1
        payload.unlink()
        assert a.request('/up/download/1.txt',[('download_pass','download123'),('csrf_token',a.token)])[2]!=b'fixture-content\n';checks+=1
        assert a.request('/up/')[0]==200;checks+=1
        payload.write_bytes(b'fixture-content\n')
        server.stop()
        # Corrupt on-disk text/path/id fields must fail startup before template or path use.
        for change in ['unterminated','html-name','id-mismatch']:
            data=bytearray(original);name=data.find(b'fixture.txt');mime=data.find(b'text/plain');assert name>0 and mime>name
            if change=='unterminated':data[name:mime]=b'A'*(mime-name)
            elif change=='html-name':data[name:name+11]=b'<script>.tx'
            else:data[24:32]=(999).to_bytes(8,'little')
            record.write_bytes(data);server.start(success=False);server.stop();checks+=1
        record.write_bytes(original)
        # A configuration reduced below the saved item count must fail safely.
        second=root/'data/02/2';second.parent.mkdir();data=bytearray(original);data[24:32]=(2).to_bytes(8,'little');second.write_bytes(data)
        server.start(success=False);server.stop();assert record.read_bytes()==original;checks+=1;second.unlink()
        # Isolated stress: bypass the old posting-interval rule only for this concurrency test.
        server.conf.write_text('Define UPLOADER_DEBUG\n'+server.conf.read_text().replace('UploaderTotalFileNumberLimit 1','UploaderTotalFileNumberLimit 2'))
        server.start()
        def post(i):
            c=Client(port);c.index();status,_,body=upload(c,'parallel'+str(i)+'.txt');m=re.search(rb'/info/([0-9]+)',body);assert m;return status,m[1]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:statuses=list(ex.map(post,range(16)))
        assert {x[0] for x in statuses}=={200},statuses;checks+=1
        assert len({x[1] for x in statuses})==16,statuses;checks+=1
        assert len([f for f in (root/'data').glob('*/*') if f.name.isdigit()])<=2;checks+=1
        assert a.request('/up/')[0]==200;checks+=1
        server.stop();server.start();assert a.request('/up/')[0]==200;checks+=1
        assert not list((root/'temp').glob('*'));checks+=1
    finally:server.stop()
    print('audit-http: '+str(checks)+' checks passed (invalid-upload retention, NUL/duplicates/encoding, protected thumbnail, missing payload, corrupt metadata, capacity, concurrency)')
    print('Disposable fixtures retained: '+str(root))
if __name__=='__main__':main()
