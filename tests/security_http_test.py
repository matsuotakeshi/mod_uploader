#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Real httpd on loopback, isolated storage, no production configuration changes."""
import base64
import concurrent.futures
import argparse, hashlib, hmac, http.client, json, os, pwd, re, shutil, socket, ssl, subprocess, tempfile, time
from pathlib import Path

def run(*args,input=None,code=0):
    p=subprocess.run(list(map(str,args)),input=input,capture_output=True)
    assert p.returncode==code,(p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace'))
    return p

class Server:
    def __init__(self,root,build,port,admin_auth=True):
        self.root=root;self.port=port;self.conf=root/'httpd.conf';self.proc=None
        mods=Path('/usr/local/libexec/apache24');base='http://127.0.0.1:'+str(port)+'/up'
        (root/'www').mkdir(exist_ok=True)
        text='DocumentRoot \"'+str(root/'www')+'\"\n'
        text+='ServerRoot "'+str(root)+'"\nPidFile "'+str(root/'httpd.pid')+'"\n'
        text+='Listen 127.0.0.1:'+str(port)+'\nServerName 127.0.0.1\nErrorLog "'+str(root/'error.log')+'"\nLogLevel info\n'
        for name in ['mpm_event','unixd','authz_core','authz_host','auth_basic','authn_core','authn_file','authz_user']:text+='LoadModule '+name+'_module "'+str(mods/('mod_'+name+'.so'))+'"\n'
        text+='LoadModule uploader_module "'+str(build/'src/mod_uploader.so')+'"\n'
        text+='User '+pwd.getpwuid(os.geteuid()).pw_name+'\nGroup #'+str(os.getegid())+'\n'
        text+='<Location /up>\nSetHandler uploader\nRequire all granted\nUploaderBaseUrl "'+base+'"\n'
        for key,name in [('Data','data'),('File','file'),('Thumb','thumb'),('Temp','temp')]:text+='Uploader'+key+'Directory "'+str(root/name)+'"\n'
        text+='UploaderTotalFileSizeLimit 10485760\nUploaderTotalFileNumberLimit 100\nUploaderFileSizeLimit 1048576\nUploaderPerPageItemNumber 30\n'
        for key,name in [('Index','index'),('Info','info'),('Progress','progress'),('Download','download'),('Thumbnail','thumbnail'),('Admin','admin'),('Error','error')]:
            text+='Uploader'+key+'ViewTemplate "'+str(build/'tmpl/en'/(name+'.htm'))+'"\n'
        text+='</Location>\n<Location /up/admin>\n'
        if admin_auth:
            auth=root/'admin.htpasswd'
            auth.write_bytes(run('/usr/local/bin/htpasswd','-niB','-C','5','review',input=b'fixture-admin-pass\n').stdout)
            os.chmod(auth,0o600)
            text+='AuthType Basic\nAuthName "Uploader administration"\nAuthBasicProvider file\nAuthUserFile "'+str(auth)+'"\nRequire valid-user\n'
        else:text+='Require local\n'
        text+='</Location>\n<Location /up/mail>\nRequire local\n</Location>\n'
        self.conf.write_text(text)
    def start(self,success=True):
        self.log=(self.root/'process.log').open('ab')
        self.proc=subprocess.Popen(['/usr/local/sbin/httpd','-DFOREGROUND','-f',str(self.conf)],stdout=self.log,stderr=self.log)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if self.proc.poll() is not None:
                if not success:
                    assert self.proc.returncode > 0, 'Expected a rejected startup, not a signal/crash'
                    return
                raise AssertionError((self.root/'process.log').read_text(errors='replace')+(self.root/'error.log').read_text(errors='replace'))
            # Apache can bind its socket before post_config rejects storage.
            # For rejection tests, wait for the process to exit, not a TCP connect.
            if not success:
                time.sleep(.05)
                continue
            try:
                with socket.create_connection(('127.0.0.1',self.port),timeout=.2):
                    return
            except OSError:time.sleep(.05)
        raise AssertionError('httpd did not reach the expected state')
    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate();self.proc.wait(timeout=15)
            assert self.proc.returncode==0, 'Apache shutdown failed: '+str(self.proc.returncode)
        if hasattr(self,'log'):self.log.close()

class Client:
    def __init__(self,port,tls_context=None):
        self.port=port;self.admin_credentials=None;self.cookie='';self.token='';self.tls_context=tls_context;self.origin=('https://' if tls_context else 'http://')+'127.0.0.1:'+str(port)
    def request(self,path,fields=None,headers=None,cookie=None):
        h={} if headers is None else dict(headers)
        if path.startswith('/up/admin') and self.admin_credentials:h.setdefault('Authorization',self.admin_credentials)
        if cookie is None:cookie=self.cookie
        if cookie:h['Cookie']=cookie
        body=None;method='GET'
        if fields is not None:
            method='POST';boundary='security-test-boundary-8da9';pieces=[]
            for name,value in fields:
                pieces.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"').encode())
                if isinstance(value,tuple):
                    filename,data=value;pieces[-1]+=('; filename="'+filename+'"\r\nContent-Type: application/octet-stream').encode();value=data
                if isinstance(value,str):value=value.encode()
                pieces[-1]+=b'\r\n\r\n'+value+b'\r\n'
            body=b''.join(pieces)+('--'+boundary+'--\r\n').encode()
            h['Content-Type']='multipart/form-data; boundary='+boundary;h.setdefault('Origin',self.origin)
            if h.get('Origin') is None:h.pop('Origin',None)
        c=http.client.HTTPSConnection('127.0.0.1',self.port,timeout=20,context=self.tls_context) if self.tls_context else http.client.HTTPConnection('127.0.0.1',self.port,timeout=20)
        c.request(method,path,body=body,headers=h);response=c.getresponse();data=response.read();status=response.status;rh=dict(response.getheaders())
        for k,v in response.getheaders():
            if k.lower()=='set-cookie':self.cookie=v.split(';',1)[0]
        c.close();return status,rh,data
    def index(self):
        status,headers,data=self.request('/up/');assert status==200,(status,data[:200]);m=re.search(rb'name="csrf_token" value="([0-9]+\.[0-9a-f]{64})"',data);assert m,'rendered form lacks token';self.token=m[1].decode();return headers,data

def setup(root,tool):
    for name in ['data','file','thumb','temp']:(root/name).mkdir(parents=True)
    (root/'data/01').mkdir();(root/'file/01').mkdir();run(tool,'--fixture3',root/'data/01/1');(root/'file/01/1.txt').write_bytes(b'fixture-content\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--legacy-build-root',type=Path);p.add_argument('--workdir',type=Path);args=p.parse_args()
    root=Path(tempfile.mkdtemp(prefix='http-security-',dir=args.workdir));build=args.build_root.resolve();tool=build/'src/password_tool';setup(root,tool)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    server=Server(root,build,port);checks=0
    try:
        server.start(success=False);assert 'Legacy metadata' in (root/'error.log').read_text(errors='replace');checks+=1;server.stop()
        driver=Path(__file__).resolve().parents[1]/'util/migrate_passwords.py'
        cmd=[os.sys.executable,driver,'--tool',tool,'--backup-dir',root/'backup','--server-stopped']
        for name in ['data','file','thumb','temp']:cmd+=['--'+name+'-dir',root/name]
        run(*cmd);assert (root/'data/01/1').read_bytes()[16:17]==b'4';checks+=1
        (root/'data/.migration-in-progress').write_text('test interrupted migration')
        server.start(success=False);checks+=1;server.stop();(root/'data/.migration-in-progress').unlink()
        server.start()
        def first_get(_):
            client=Client(port);client.index();return client.cookie
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            cookies=list(executor.map(first_get,range(12)))
        assert len(set(cookies))==12;checks+=1
        live_cmd=list(cmd);live_cmd[live_cmd.index('--backup-dir')+1]=root/'live-backup'
        run(*live_cmd,code=1);assert not (root/'live-backup').exists();checks+=1
        a=Client(port);a.admin_credentials='Basic '+base64.b64encode(b'review:fixture-admin-pass').decode();headers,page=a.index();assert 'no-store' in headers['Cache-Control'];checks+=1
        cookie_header=headers.get('Set-Cookie','');assert 'HttpOnly' in cookie_header and 'SameSite=Strict' in cookie_header;checks+=1
        assert (root/'data/.csrf-key').stat().st_mode&0o777==0o600;checks+=1
        for form_path in ['/up/admin/','/up/download/1.txt']:
            status,_,form=a.request(form_path);assert status==200 and re.search(rb'name="csrf_token" value="[0-9]+\.[0-9a-f]{64}"',form);checks+=1
        b=Client(port);b.index();assert a.cookie!=b.cookie;checks+=1
        remove=[('id','1'),('remove_pass','wrong')]
        assert a.request('/up/remove/',remove)[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token','forged')])[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token',a.token)],cookie=a.cookie+'; '+a.cookie)[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token',a.token)],headers={'X-CSRF-Token':'forged'})[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token_evil',a.token)])[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token',a.token)],headers={'Origin':None})[0]==403;checks+=1
        assert b.request('/up/remove/',remove+[('csrf_token',a.token)])[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token',a.token)],cookie='')[0]==403;checks+=1
        assert a.request('/up/remove/',remove+[('csrf_token',a.token)],headers={'Origin':'https://evil.example'})[0]==403;checks+=1
        # Duplicate fields now fail in the multipart parser, before CSRF handling.
        # The legacy error template uses HTTP 200; even a correct password must not delete.
        status,_,body=a.request('/up/remove/',[('id','1'),('remove_pass','remove123'),('csrf_token',a.token),('csrf_token',a.token)])
        assert status==200 and b'MESSAGE_RFC1867_FORMAT_INVALID' in body and (root/'data/01/1').exists();checks+=1
        key=(root/'data/.csrf-key').read_bytes();sid=a.cookie.split('=',1)[1];base=a.origin+'/up'
        for stamp in [int(time.time())-7201,int(time.time())+120]:
            stamp=str(stamp);token=stamp+'.'+hmac.new(key,(base+'\n'+sid+'\n'+stamp).encode(),hashlib.sha256).hexdigest()
            assert a.request('/up/remove/',remove+[('csrf_token',token)])[0]==403;checks+=1
        assert (root/'data/01/1').exists();checks+=1
        # Old tab token remains valid after a second GET; correct source alone is insufficient.
        old=a.token;a.index();status,_,_=a.request('/up/remove/',remove+[('csrf_token',old)]);assert status==200 and (root/'data/01/1').exists();checks+=1
        dl='/up/download/1.txt';payload=(root/'file/01/1.txt').read_bytes()
        for password in ['wrong','download123-extra']:
            assert a.request(dl,[('download_pass',password),('csrf_token',a.token)])[2]!=payload;checks+=1
        status,h,data=a.request(dl,[('download_pass','download123'),('csrf_token',a.token)])
        assert status==200 and data==payload;checks+=1
        assert h['Content-Disposition']=='attachment' and h['X-Content-Type-Options']=='nosniff';checks+=1
        status,_,data=a.request(dl,[('download_pass','download123'),('csrf_token',a.token)],headers={'Origin':None,'Referer':a.origin+'/up/'})
        assert status==200 and data==payload;checks+=1
        # Header token is supported for scripted clients and cookie/session binding still applies.
        status,_,data=a.request(dl,[('download_pass','download123')],headers={'X-CSRF-Token':a.token});assert status==200 and data==payload;checks+=1
        assert a.request('/up/admin/remove/',[('id','1')])[0]==403;checks+=1
        # Upload tokens are verified before a new item can be committed.
        upload=[('file',('new.txt',b'new upload bytes\n')),('comment','security test'),('remove_pass','new-remove'),('download_pass','new-download'),('code_pat','')]
        assert a.request('/up/upload/',upload)[0]==403;checks+=1
        before=set((root/'data').glob('*/*'))
        status,_,_=a.request('/up/upload/',upload+[('csrf_token',a.token)]);assert status==200
        after=set((root/'data').glob('*/*'));created=[f for f in after-before if f.name.isdigit()];assert len(created)==1,(status,created);checks+=1
        record=created[0].read_bytes();assert b'new-remove' not in record and b'new-download' not in record and record[16:17]==b'4';checks+=1
        run(tool,'--verify-remove',created[0],input=b'new-remove\n');run(tool,'--verify-download',created[0],input=b'new-download\n');checks+=1
        assert a.request('/up/remove/',[('id','1'),('remove_pass','remove123-extra'),('csrf_token',a.token)])[0]==200 and (root/'data/01/1').exists();checks+=1
        assert a.request('/up/remove/',[('id','1'),('remove_pass','remove123'),('csrf_token',a.token)])[0]==200 and not (root/'data/01/1').exists();checks+=1
        assert not (root/'file/01/1.txt').exists();checks+=1
        server.stop();server.start()
        status,_,_=a.request('/up/admin/remove/',[('id',created[0].name)],headers={'X-CSRF-Token':a.token});assert status==200 and created[0].exists();checks+=1
        status,_,_=a.request('/up/admin/remove/',[('id',created[0].name),('remove_pass','')],headers={'X-CSRF-Token':a.token});assert status==200 and not created[0].exists();checks+=1
        assert (root/'backup/snapshot/data/01/1').read_bytes()[16:17]==b'3';checks+=1
    finally:server.stop()
    if args.legacy_build_root:
        restored=root/'rollback';shutil.copytree(root/'backup/snapshot',restored)
        old=Server(restored,args.legacy_build_root.resolve(),port)
        try:
            old.start();c=Client(port);status,_,_=c.request('/up/');assert status==200;checks+=1
            status,_,data=c.request('/up/download/1.txt',[('download_pass','download123')]);assert status==200 and data==b'fixture-content\n';checks+=1
        finally:old.stop()
    print('http-security: '+str(checks)+' checks passed (real loopback Apache, migration, passwords, CSRF, restart'+', rollback' * bool(args.legacy_build_root)+')')
    print('Disposable test data retained for review: '+str(root))
if __name__=='__main__':main()
