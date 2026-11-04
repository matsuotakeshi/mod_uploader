#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Installed RPM test in httpd_t, on a disposable EL host with SELinux Enforcing.

Requires root, systemd, httpd-devel and policycoreutils-python-utils. Uses a unique
storage tree and transient unit. Never modifies the main httpd service/config.
"""
import argparse
import base64
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import time
import uuid
from apache_paths import httpd, load_module, apxs_query, program
from root_http_test import MountedClient, png
from security_http_test import run, setup


def main():
    p=argparse.ArgumentParser();p.add_argument('--thumbnail',action='store_true');args=p.parse_args()
    assert os.geteuid()==0, 'Requires root on a disposable test host'
    assert run('getenforce').stdout.strip()==b'Enforcing', 'SELinux must be enforcing'
    run('rpm','-q','mod_uploader')
    if args.thumbnail:
        assert b'--> on' in run('getsebool','httpd_setrlimit').stdout, 'Thumbnail setup requires httpd_setrlimit on; see LINUX-ja.md'
    account=pwd.getpwnam('apache');token=uuid.uuid4().hex
    root=Path('/var/lib/mod_uploader-test-'+token);root.mkdir(mode=0o700)
    rule=str(root)+'(/.*)?';unit='mod-uploader-test-'+token
    config=Path('/etc/httpd/mod-uploader-test-'+token+'.conf')
    tools=Path('/usr/libexec/mod_uploader');checks=0
    def check(ok,why):
        nonlocal checks
        assert ok,(why,root);checks+=1
    setup(root,tools/'password_tool')
    command=[os.sys.executable,tools/'migrate_passwords.py','--tool',tools/'password_tool',
             '--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:command+=['--'+name+'-dir',root/name]
    run(*command)
    auth=root/'admin.htpasswd';auth.write_bytes(run(program('HTPASSWD','htpasswd'),'-niB','-C','5','review',input=b'fixture-admin-pass\n').stdout)
    os.chmod(auth,0o600)
    for path in [root,*root.rglob('*')]:os.chown(path,account.pw_uid,account.pw_gid)
    run('semanage','fcontext','-a','-t','httpd_sys_rw_content_t',rule)
    run('restorecon','-RF',root)
    try:
        # 8008 is a standard http_port_t port in the EL policy. No new port rule.
        port=8008
        with socket.socket() as sock:sock.bind(('127.0.0.1',port))
        for mount in ['', '/up']:
            sample=Path('/etc/mod_uploader/mod_uploader'+('-root' if not mount else '')+'.conf.sample')
            text=sample.read_text().replace('/var/lib/mod_uploader',str(root))
            origin='http://127.0.0.1:'+str(port)
            text=re.sub(r'UploaderBaseUrl "[^"]+"','UploaderBaseUrl "'+origin+mount+'/"',text)
            admin='<Location '+mount+'/admin>\n    Require all denied\n</Location>'
            assert admin in text
            text=text.replace(admin,'<Location '+mount+'/admin>\nAuthType Basic\nAuthName "Isolated RPM test"\nAuthBasicProvider file\nAuthUserFile "'+str(auth)+'"\n<RequireAll>\nRequire ip 127.0.0.1\nRequire valid-user\n</RequireAll>\n</Location>')
            header='ServerRoot /etc/httpd\nServerName localhost\nDocumentRoot /var/www/html\n'
            header+='Listen 127.0.0.1:'+str(port)+'\nPidFile "'+str(root/'httpd.pid')+'"\nErrorLog "'+str(root/'error.log')+'"\nUser apache\nGroup apache\n'
            for name in ['mpm_event','unixd','authz_core','authz_host','auth_basic','authn_core','authn_file','authz_user','alias']:
                header+=load_module(name)
            header+='LoadModule uploader_module "'+str(Path(apxs_query('LIBEXECDIR'))/'mod_uploader.so')+'"\n'
            with config.open('x') as stream:stream.write(header+'<VirtualHost 127.0.0.1:'+str(port)+'>\n'+text+'\n</VirtualHost>\n')
            run('restorecon',config);run(httpd(),'-t','-f',config)
            run('systemd-run','--unit='+unit,'--collect','--property=Type=simple','--property=RuntimeMaxSec=120',httpd(),'-DFOREGROUND','-f',config)
            try:
                for attempt in range(100):
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                    except OSError:time.sleep(.1)
                else:raise AssertionError('SELinux Apache startup failed; inspect '+str(root/'error.log'))
                pid=run('systemctl','show','--value','-p','MainPID',unit).stdout.decode().strip()
                domain=Path('/proc')/pid/'attr/current'
                check(':httpd_t:' in domain.read_text(),'Apache is confined in httpd_t')
                print('mount='+repr(mount or '/')+' domain='+domain.read_text().strip(),flush=True)
                c=MountedClient(port,mount);_,page=c.index();check(b'csrf_token' in page,'top page')
                for name in ['img/title.png','css/default.css','js/progress.js']:
                    status,_,body=c.request('/up_'+name)
                    check(status==200 and body==(Path('/usr/share/mod_uploader')/name).read_bytes(),'static '+name)
                check(c.request('/up/rss/')[0]==200,'RSS')
                check(c.request('/up/admin/')[0] in (401,403),'unauthenticated admin denied')
                fields=[('file',('selinux.png',png())),('comment','SELinux fixture'),('remove_pass',''),('download_pass',''),('code_pat','')]
                check(c.request('/up/upload/',fields)[0]==403,'CSRF upload denied')
                status,_,body=c.request('/up/upload/',fields+[('csrf_token',c.token)])
                item=re.search(rb'/info/(\d+)',body);check(status==200 and item is not None,'upload in httpd_t')
                item=item[1].decode();check(c.request('/up/download/'+item+'.png')[2]==png(),'original download')
                if args.thumbnail:
                    status,_,body=c.request('/up/thumbnail/view/'+item+'.gif')
                    check(status==200 and body[:6] in (b'GIF87a',b'GIF89a'),'thumbnail in httpd_t')
                check(c.request('/up/data/01/1')[2]!=(root/'data/01/1').read_bytes(),'metadata not served')
                c.admin_credentials='Basic '+base64.b64encode(b'review:fixture-admin-pass').decode()
                check(c.request('/up/admin/')[0]==200,'authenticated admin')
                check(c.request('/up/admin/remove/',[('id',item),('remove_pass',''),('csrf_token',c.token)])[0]==200,'authenticated deletion')
                check(not any(x.name==item for x in (root/'data').glob('*/*')),'record removed')
            finally:
                subprocess.run(['systemctl','stop',unit],check=False,capture_output=True)
                config.unlink()
    finally:
        run('semanage','fcontext','-d',rule)
    print('linux-selinux: '+str(checks)+' checks passed; retained fixtures: '+str(root))


if __name__=='__main__':main()
