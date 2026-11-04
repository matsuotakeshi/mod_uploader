#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Load the distributed root/subpath samples with isolated paths and Japanese views."""
import argparse, re, sys, tempfile
from pathlib import Path
from apache_paths import load_module
from security_http_test import Server, setup, run
from root_http_test import MountedClient, free_port

def exercise(build, workdir, mount, samples=None):
    root=Path(tempfile.mkdtemp(prefix='root-sample-',dir=workdir))
    setup(root,build/'src/password_tool')
    source=Path(__file__).resolve().parents[1]
    command=[sys.executable,source/'util/migrate_passwords.py','--tool',build/'src/password_tool','--backup-dir',root/'backup','--server-stopped']
    for name in ['data','file','thumb','temp']:command+=['--'+name+'-dir',root/name]
    run(*command)
    port=free_port();server=Server(root,build,port)
    header=server.conf.read_text().split('<Location /up>')[0]
    sample=(samples/('mod_uploader'+('-root' if not mount else '')+'.conf.sample') if samples else source/'ports/www/mod_uploader/files'/('mod_uploader'+('-root' if not mount else '')+'.conf.in'))
    text=sample.read_text().replace('%%DATADIR%%',str(build)).replace('%%PREFIX%%','/usr/local').replace('%%APACHEMODDIR%%','libexec/apache24')
    text=re.sub(r'^LoadModule .*\n','',text,flags=re.M)
    text=text.replace('/var/db/mod_uploader',str(root)).replace('/var/lib/mod_uploader',str(root)).replace('/usr/share/mod_uploader',str(build))
    origin='http://127.0.0.1:'+str(port)
    text=re.sub(r'UploaderBaseUrl "[^"]+"','UploaderBaseUrl "'+origin+mount+'/"',text)
    server.conf.write_text(header+load_module('alias')+'<VirtualHost 127.0.0.1:'+str(port)+'>\n'+text+'\n</VirtualHost>\n')
    checks=0
    def check(condition,description):
        nonlocal checks
        assert condition,description+' in '+str(root)
        checks+=1
    try:
        server.start();client=MountedClient(port,mount)
        _,page=client.index();check(b'charset=EUC-JP' in page,'Japanese sample top page')
        check((origin+'/up_css/default.css').encode() in page,'sample stylesheet URL')
        for name in ['img/title.png','css/default.css','js/progress.js']:
            status,_,data=client.request('/up_'+name)
            check(status==200 and data==(build/name).read_bytes(),'sample static '+name)
        check(client.request('/up/admin/')[0]==403,'sample admin disabled')
        check(client.request('/up/mail/')[0]==403,'sample mail disabled')
        for path in ['/up/data/01/1','/up/file/01/1.txt','/up/.csrf-key']:
            _,_,body=client.request(path)
            check(b'fixture-content\n' not in body and b'pbkdf2-sha256' not in body,'sample private files '+path)
    finally:server.stop()
    print(str(sample.name)+': '+str(checks)+' checks passed; '+str(root))
    return checks

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--build-root',type=Path,required=True);parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--samples-dir',type=Path)
    args=parser.parse_args()
    total=sum(exercise(args.build_root.resolve(),args.workdir,mount,args.samples_dir) for mount in ['', '/up'])
    print('root-samples: '+str(total)+' checks passed across 2 distributed configuration samples')

if __name__=='__main__':main()
