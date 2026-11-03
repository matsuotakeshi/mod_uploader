#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Isolated real VirtualHosts; exercise both mounts with the unchanged security client."""
import argparse, base64, os, re, socket, ssl, struct, tempfile, zlib
from pathlib import Path
from urllib.parse import urlsplit
from security_http_test import Server, Client, setup, run

class MountedClient(Client):
    def __init__(self, port, mount, tls_context=None):
        super().__init__(port, tls_context); self.mount=mount
    def request(self, path, fields=None, headers=None, cookie=None):
        h=dict(headers or {})
        if path.startswith('/up/admin') and self.admin_credentials:
            h.setdefault('Authorization', self.admin_credentials)
        if path=='/up' or path.startswith('/up/'):
            path=self.mount+path[3:]
        return super().request(path,fields,h,cookie)

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]

def png():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,24,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x28\x90\xd0'*32)*24))+chunk(b'IEND',b'')

def make_server(root, build, mount, trailing, tls):
    port=free_port(); server=Server(root,build,port)
    origin=('https' if tls else 'http')+'://127.0.0.1:'+str(port)
    base=origin+mount+('/' if trailing else '')
    text=server.conf.read_text().replace('http://127.0.0.1:'+str(port)+'/up',base)
    for old,new in [('/up/admin',mount+'/admin'),('/up/mail',mount+'/mail'),('/up',mount or '/')]:
        text=text.replace('<Location '+old+'>','<Location '+new+'>')
    text=text.replace('Require valid-user','<RequireAll>\nRequire ip 127.0.0.1\nRequire valid-user\n</RequireAll>')
    text+='LoadModule alias_module /usr/local/libexec/apache24/mod_alias.so\n'
    assets=mount.rsplit('/',1)[0] if mount else ''
    for name,folder,mime in [('img','img','image/png'),('css','css','text/css'),('js','js','application/javascript'),('swf','swf','application/x-shockwave-flash')]:
        prefix=assets+'/up_'+name
        text+='Alias '+prefix+' "'+str(build/folder)+'"\n'
        text+='<Location "'+prefix+'">\nSetHandler default-handler\nRequire all granted\nForceType '+mime+'\n</Location>\n'
        text+='<Directory "'+str(build/folder)+'">\nOptions None\nAllowOverride None\nRequire all granted\n</Directory>\n'
    text+='<Directory "'+str(root/'data')+'">\nRequire all denied\n</Directory>\n'
    # A dedicated webroot for Certbot HTTP-01 coexistence; no ACME network traffic.
    (root/'www/.well-known/acme-challenge').mkdir(parents=True)
    (root/'www/.well-known/acme-challenge/probe').write_bytes(b'acme-test-only')
    text+='<Location /.well-known/acme-challenge/>\nSetHandler default-handler\nRequire all granted\n</Location>\n'
    text+='<Directory "'+str(root/'www')+'">\nOptions None\nAllowOverride None\nRequire all granted\n</Directory>\n'
    context=None
    if tls:
        run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',root/'server.key','-out',root/'server.crt','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1')
        os.chmod(root/'server.key',0o600)
        text+='LoadModule ssl_module /usr/local/libexec/apache24/mod_ssl.so\nSSLEngine on\nSSLCertificateFile "'+str(root/'server.crt')+'"\nSSLCertificateKeyFile "'+str(root/'server.key')+'"\n'
        context=ssl.create_default_context(cafile=str(root/'server.crt'))
    # Put routing and authorization in an actual VirtualHost. Process-level directives stay outside.
    outside=[];inside=[]
    for line in text.splitlines():
        (outside if line.startswith(('LoadModule ','ServerRoot ','PidFile ','Listen ','User ','Group ','ErrorLog ')) else inside).append(line)
    server.conf.write_text('\n'.join(outside)+'\n<VirtualHost 127.0.0.1:'+str(port)+'>\n'+'\n'.join(inside)+'\n</VirtualHost>\n')
    return server,MountedClient(port,mount,context),origin,assets

def exercise(args,mount,trailing,tls):
    root=Path(tempfile.mkdtemp(prefix='root-http-',dir=args.workdir));build=args.build_root.resolve()
    setup(root,build/'src/password_tool')
    cmd=[os.sys.executable,Path(__file__).resolve().parents[1]/'util/migrate_passwords.py','--tool',build/'src/password_tool','--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:cmd+=['--'+name+'-dir',root/name]
    run(*cmd)
    server,c,origin,assets=make_server(root,build,mount,trailing,tls);checks=0
    def check(condition,description):
        nonlocal checks
        assert condition,description+' in '+str(root);checks+=1
    def urls(body):
        for value in re.findall(rb'https?://[^\s<>"\x27]+',body):
            parsed=urlsplit(value.decode('ascii',errors='ignore'))
            if parsed.netloc==urlsplit(origin).netloc:
                check('//' not in parsed.path and '/..' not in parsed.path,'noncanonical generated URL '+str(value))
    try:
        server.start()
        if args.expect_vulnerable:
            _,_,body=c.request('/up/')
            check(b'name="csrf_token"' not in body and b'up_css' in body,'root failure baseline')
            print('baseline reproduced: root request renders the environment error instead of the index')
            return checks
        if mount:
            status,h,_=c.request('/up');check(status==307 and h['Location']==origin+mount+'/','subpath canonical redirect')
        h,page=c.index();check('Location' not in h,'index without redirect');urls(page)
        check((origin+mount+'/upload/').encode() in page,'upload form URL')
        check((origin+assets+'/up_css/default.css').encode() in page,'stylesheet URL')
        for path in ['/up/index','/up/index/','/up/thumbnail/']:
            status,_,body=c.request(path)
            expected=b'<h1>Image List</h1>' if 'thumbnail' in path else b'name="csrf_token"'
            check(status==200 and expected in body,'index/thumbnail page '+path);urls(body)
        status,_,rss=c.request('/up/rss/');check(status==200 and b'<rdf:RDF' in rss,'RSS');urls(rss)
        for suffix,file,mime in [('css/default.css','css/default.css','text/css'),('js/progress.js','js/progress.js','application/javascript'),('img/title.png','img/title.png','image/png'),('swf/UploadPanel.swf','swf/UploadPanel.swf','application/x-shockwave-flash')]:
            status,h,data=c.request(assets+'/up_'+suffix)
            check(status==200 and data==(build/file).read_bytes(),'static '+suffix)
            check(h.get('Content-Type','').startswith(mime),'static MIME '+suffix)
        check(c.request('/.well-known/acme-challenge/probe')[2]==b'acme-test-only','ACME static exception')
        for path in ['/up/admin','/up/admin/','/up/admin/info','/up/admin/download/1.txt']:
            check(c.request(path)[0] in (401,403),'unauthenticated admin '+path)
        check(c.request('/up/admin/remove/',[('id','1'),('remove_pass',''),('csrf_token',c.token)])[0] in (401,403),'unauthenticated delete')
        check((root/'data/01/1').exists(),'protected record retained')
        check(c.request('/up/mail/',[('csrf_token',c.token)])[0]==403,'mail authentication')
        check(c.request('/up/thumbnail/view/1.gif')[0]==403,'protected thumbnail')
        check(c.request('/up/download/1.txt',[('download_pass','download123')])[0]==403,'CSRF required')
        check(c.request('/up/download/1.txt',[('download_pass','download123'),('csrf_token',c.token)],headers={'Origin':'https://invalid.example'})[0]==403,'Origin rejected')
        status,h,data=c.request('/up/download/1.txt',[('download_pass','download123'),('csrf_token',c.token)])
        check(status==200 and data==b'fixture-content\n','protected download')
        check(h.get('Content-Disposition')=='attachment' and h.get('X-Content-Type-Options')=='nosniff','download security headers')
        image=png();fields=[('file',('root-test.png',image)),('comment','root deployment'),('remove_pass',''),('download_pass',''),('code_pat','')]
        check(c.request('/up/upload/',fields)[0]==403,'upload CSRF required')
        status,_,body=c.request('/up/upload/',fields+[('csrf_token',c.token)])
        found=re.search(rb'/info/(\d+)',body);check(status==200 and found is not None,'image upload');item=found[1].decode();urls(body)
        status,_,data=c.request('/up/download/'+item+'.png');check(status==200 and data==image,'uploaded image download')
        if args.thumbnail:
            status,h,thumb=c.request('/up/thumbnail/view/'+item+'.gif')
            check(status==200 and thumb[:6] in (b'GIF87a',b'GIF89a'),'generated thumbnail')
            dimensions=struct.unpack('<HH',thumb[6:10]);check(0<dimensions[0]<=250 and 0<dimensions[1]<=250,'thumbnail dimensions')
            check(h.get('Content-Type')=='image/gif','thumbnail MIME')
            status,_,page=c.request('/up/thumbnail/');check(status==200 and (item+'.gif').encode() in page,'thumbnail list includes generated image');urls(page)
        for path in ['/up/no-such-command','/up/%252e%252e/etc/passwd','/up/download/%2e%2e','/up/download/1.txt%00','/up/%5cadmin','/up/.csrf-key','/up/data/01/1','/up/file/01/1.txt','/up/temp/x','/up/thumbnail/view/../../data/01/1']:
            status,_,body=c.request(path);check(status in (200,400,403,404) and b'fixture-content\n' not in body and b'pbkdf2-sha256' not in body,'unsafe URL '+path)
        c.admin_credentials='Basic '+base64.b64encode(b'review:fixture-admin-pass').decode()
        check(c.request('/up/admin/')[0]==200,'authenticated admin')
        check(c.request('/up/admin/download/1.txt')[2]==b'fixture-content\n','authenticated admin download')
        check(c.request('/up/admin/remove/',[('id',item),('remove_pass','')])[0]==403,'admin CSRF required')
        check(c.request('/up/admin/remove/',[('id',item),('remove_pass',''),('csrf_token',c.token)])[0]==200,'authenticated admin deletion')
        check(not any(p.name==item for p in (root/'data').glob('*/*')),'admin deleted target')
        server.stop();server.conf.write_text(server.conf.read_text().replace('Require ip 127.0.0.1','Require ip 127.0.0.2'));server.start()
        check(c.request('/up/admin/')[0]==403,'admin IP restriction')
        server.stop()
        if mount:
            # The historical collision check must remain effective.
            (root/'www'/mount.lstrip('/')).mkdir(parents=True,exist_ok=True)
            server.start();status,_,body=c.request('/up/')
            check(status==500 and b'name="csrf_token"' not in body,'physical directory collision remains an error')
    finally:server.stop()
    print('mount='+repr(mount or '/')+' trailing='+str(trailing)+' tls='+str(tls)+' thumbnail='+str(args.thumbnail)+': '+str(checks)+' checks passed; '+str(root))
    return checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);p.add_argument('--workdir',type=Path,required=True);p.add_argument('--thumbnail',action='store_true');p.add_argument('--expect-vulnerable',action='store_true');args=p.parse_args()
    cases=[('',True,False)] if args.expect_vulnerable else [('',True,False),('',False,False),('/up',False,False),('/up',True,False),('/board/up',True,False),('',True,True),('/up',True,True)]
    count=sum(exercise(args,*case) for case in cases)
    print('root-http: '+str(count)+' checks passed across '+str(len(cases))+' VirtualHost configurations')
if __name__=='__main__':main()
