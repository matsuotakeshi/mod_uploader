#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
import argparse, os, socket, ssl, tempfile
from pathlib import Path
from security_http_test import Server,Client,setup,run

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--workdir',type=Path);args=p.parse_args()
    root=Path(tempfile.mkdtemp(prefix='https-security-',dir=args.workdir));build=args.build_root.resolve();setup(root,build/'src/password_tool')
    driver=Path(__file__).resolve().parents[1]/'util/migrate_passwords.py'
    cmd=[os.sys.executable,driver,'--tool',build/'src/password_tool','--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:cmd+=['--'+name+'-dir',root/name]
    run(*cmd)
    run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',root/'server.key','-out',root/'server.crt','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1')
    os.chmod(root/'server.key',0o600)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    server=Server(root,build,port);text=server.conf.read_text().replace('http://127.0.0.1:','https://127.0.0.1:')
    text+='\nLoadModule ssl_module /usr/local/libexec/apache24/mod_ssl.so\nSSLEngine on\nSSLCertificateFile "'+str(root/'server.crt')+'"\nSSLCertificateKeyFile "'+str(root/'server.key')+'"\n'
    server.conf.write_text(text);checks=0
    try:
        server.start();client=Client(port,ssl.create_default_context(cafile=str(root/'server.crt')));headers,_=client.index();cookie=headers['Set-Cookie']
        assert cookie.startswith('__Host-mod_uploader_sid=');checks+=1
        assert '; Secure' in cookie and '; HttpOnly' in cookie and '; SameSite=Strict' in cookie and '; Path=/' in cookie;checks+=1
        assert 'Domain=' not in cookie;checks+=1
        assert client.request('/up/download/1.txt',[('download_pass','download123')])[0]==403;checks+=1
        status,_,body=client.request('/up/download/1.txt',[('download_pass','download123'),('csrf_token',client.token)])
        assert status==200 and body==b'fixture-content\n';checks+=1
        assert client.request('/up/remove/',[('id','1'),('remove_pass','remove123'),('csrf_token',client.token)],headers={'Origin':'http://127.0.0.1:'+str(port)})[0]==403;checks+=1
    finally:server.stop()
    print('https-security: '+str(checks)+' checks passed (validated local TLS certificate, __Host cookie and protected POST)')
    print('Disposable test directory retained: '+str(root))
if __name__=='__main__':main()
