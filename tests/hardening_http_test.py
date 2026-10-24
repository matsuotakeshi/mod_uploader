#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Real loopback proxy/backend Apache; dedicated metadata and no production changes."""
import argparse, base64, concurrent.futures, fcntl, os, socket, tempfile
from pathlib import Path
from security_http_test import Server, Client, setup, run

def freeport():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

class Proxy(Server):
    def __init__(self,root,port,backend):
        root.mkdir();self.root=root;self.port=port;self.conf=root/'httpd.conf';self.proc=None
        text='Mutex file:'+str(root)+' default\nServerRoot "'+str(root)+'"\nPidFile "'+str(root/'httpd.pid')+'"\nListen 127.0.0.1:'+str(port)+'\nServerName 127.0.0.1\nErrorLog "'+str(root/'error.log')+'"\n'
        for name in ['mpm_event','unixd','authz_core','proxy','proxy_http']:
            text+='LoadModule '+name+'_module /usr/local/libexec/apache24/mod_'+name+'.so\n'
        text+='ProxyRequests Off\nProxyPass / http://127.0.0.1:'+str(backend)+'/\nProxyPassReverse / http://127.0.0.1:'+str(backend)+'/\n'
        self.conf.write_text(text)

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--workdir',type=Path);args=p.parse_args()
    root=Path(tempfile.mkdtemp(prefix='hardening-http-',dir=args.workdir));build=args.build_root.resolve();setup(root,build/'src/password_tool')
    driver=Path(__file__).resolve().parents[1]/'util/migrate_passwords.py'
    cmd=[os.sys.executable,driver,'--tool',build/'src/password_tool','--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:cmd+=['--'+name+'-dir',root/name]
    run(*cmd);port=freeport();front=freeport();checks=0
    server=Server(root,build,port,admin_auth=False);proxy=Proxy(root/'proxy',front,port)
    def public_base():
        text=server.conf.read_text().replace('http://127.0.0.1:'+str(port)+'/up','http://127.0.0.1:'+str(front)+'/up')
        server.conf.write_text(text)
    public_base()
    try:
        server.start();proxy.start();a=Client(front);a.index()
        # Require local allows the loopback proxy; the module still rejects unauthenticated admin.
        for path in ['/up/admin/','/up/admin/info','/up/admin/download/1.txt','/up/%61dmin/']:
            assert a.request(path)[0]==403,path;checks+=1
        assert a.request('/up/admin/remove/',[('id','1'),('remove_pass',''),('csrf_token',a.token)])[0]==403;checks+=1
        assert (root/'data/01/1').exists();checks+=1
        fake={'X-Remote-User':'review','X-Forwarded-User':'review','Authorization':'Basic '+base64.b64encode(b'review:fixture-admin-pass').decode()}
        assert a.request('/up/admin/',headers=fake)[0]==403;checks+=1
        # Configure actual Apache Basic authentication; credential headers alone now require validation.
        server.stop();server=Server(root,build,port);public_base();server.start()
        assert a.request('/up/admin/')[0]==401;checks+=1
        assert a.request('/up/admin/',headers={'Authorization':'Basic '+base64.b64encode(b'review:wrong').decode()})[0]==401;checks+=1
        a.admin_credentials='Basic '+base64.b64encode(b'review:fixture-admin-pass').decode()
        for path in ['/up/admin/','/up/admin/info','/up/admin/download/1.txt']:
            status,_,body=a.request(path);assert status==200,(path,status);checks+=1
            if 'download' in path:assert body==b'fixture-content\n';checks+=1
        assert a.request('/up/admin/remove/',[('id','1'),('remove_pass','')])[0]==403;checks+=1
        # No token/session churn or untrusted forwarded-IP header grants additional guesses.
        b=Client(front);b.index();dl='/up/download/1.txt'
        for i in range(10):
            client=a if i%2 else b
            status,_,body=client.request(dl,[('download_pass','wrong'),('csrf_token',client.token)],headers={'X-Forwarded-For':'192.0.2.'+str(i+1)})
            assert status==200 and body!=b'fixture-content\n',(i,status);checks+=1
        status,h,_=b.request(dl,[('download_pass','download123'),('csrf_token',b.token)])
        assert status==429 and 1<=int(h['Retry-After'])<=60;checks+=1
        assert b.request('/up/remove/',[('id','1'),('remove_pass','remove123'),('csrf_token',b.token)])[0]==429;checks+=1
        upload=[('file',('blocked.txt',b'blocked upload')),('comment',''),('remove_pass','remove'),('download_pass','download'),('code_pat',''),('csrf_token',b.token)]
        assert b.request('/up/upload/',upload)[0]==429;checks+=1
        assert not list((root/'temp').glob('*'));checks+=1
        assert (root/'data/01/1').exists();checks+=1
        # Password prompts/empty values do not run PBKDF2 or consume another rate slot.
        assert b.request(dl)[0]==200;checks+=1
        assert b.request(dl,[('download_pass',''),('csrf_token',b.token)])[0]==200;checks+=1
        server.stop();server.start()
        assert b.request(dl,[('download_pass','wrong'),('csrf_token',b.token)])[0]==429;checks+=1
        # Authenticated admin bypass is intentional and retains CSRF validation.
        assert a.request('/up/admin/download/1.txt')[2]==b'fixture-content\n';checks+=1
        # Public frontend can independently block admin even when credentials are correct.
        proxy.stop();proxy.conf.write_text(proxy.conf.read_text()+'\n<LocationMatch "^/up/admin(?:/|$)">\nRequire all denied\n</LocationMatch>\n');proxy.start()
        assert a.request('/up/admin/')[0]==403;checks+=1
        assert a.request('/up/admin/download/1.txt')[0]==403;checks+=1
        assert a.request('/up/')[0]==200;checks+=1
        proxy.stop()
        # Fresh fixture to exercise shared worker slots without the preceding rate exhaustion.
        server.stop()
        # Remove ONLY this stopped disposable test's rate state; never do this in a running installation.
        (root/'data/.auth-attempts').unlink()
        public_base_text=server.conf.read_text().replace('http://127.0.0.1:'+str(front)+'/up','http://127.0.0.1:'+str(port)+'/up')
        server.conf.write_text(public_base_text);server.start();c=Client(port);c.index()
        handles=[]
        for i in range(2):
            fd=os.open(root/'data'/('.auth-slot-'+str(i)),os.O_RDWR|os.O_CREAT,0o600);f=os.fdopen(fd,'r+b');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);handles.append(f)
        try:
            status,h,_=c.request(dl,[('download_pass','download123'),('csrf_token',c.token)])
            assert status==429 and h['Retry-After']=='1';checks+=1
        finally:
            for f in handles:f.close()
        assert c.request(dl,[('download_pass','download123'),('csrf_token',c.token)])[2]==b'fixture-content\n';checks+=1
        def guess(i):
            d=Client(port);d.index();return d.request(dl,[('download_pass','wrong'),('csrf_token',d.token)])[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:statuses=list(ex.map(guess,range(16)))
        assert 429 in statuses and set(statuses)<={200,429},statuses;checks+=1
        c.admin_credentials=a.admin_credentials
        assert c.request('/up/admin/remove/',[('id','1'),('remove_pass',''),('csrf_token',c.token)])[0]==200;checks+=1
        assert not (root/'data/01/1').exists() and not (root/'file/01/1.txt').exists();checks+=1
    finally:proxy.stop();server.stop()
    print('hardening-http: '+str(checks)+' checks passed (real proxy, authenticated admin, shared IP/worker limits, concurrent requests, restart)')
    print('Disposable test directory retained: '+str(root))
if __name__=='__main__':main()
