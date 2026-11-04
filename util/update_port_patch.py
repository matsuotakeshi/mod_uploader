#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Regenerate the Port patch against the pinned upstream archive (does not download)."""
import argparse
import difflib
import hashlib
from pathlib import Path
import tarfile

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('upstream',type=Path);args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if hashlib.sha256(args.upstream.read_bytes()).hexdigest()!='3322f5b2c30a77d6cc01cd3b9ea8a3e182015ddce803c46a6a7eaf0901e5684a':
        raise ValueError('Archive does not match the pinned Port distinfo')
    base={}
    with tarfile.open(args.upstream) as tar:
        for member in tar.getmembers():
            if member.isfile():base[member.name.split('/',1)[1]]=tar.extractfile(member).read().replace(b'\r\n',b'\n')
    patch=b''; changed=[]
    def delta(name,old,data):
        return b''.join(difflib.diff_bytes(difflib.unified_diff,old.splitlines(True),data.splitlines(True),
            fromfile=('a/'+name).encode() if name in base else b'/dev/null',tofile=('b/'+name).encode()))
    for name,old in sorted(base.items()):
        path=root/name
        if path.is_file():
            data=path.read_bytes().replace(b'\r\n',b'\n')
            if data!=old:changed.append(name);patch+=delta(name,old,data)
    new=['MODIFICATIONS','README.md','docs/ROOT-DEPLOYMENT-ja.md','docs/SECURITY-MIGRATION-ja.md','docs/OPERATIONS-ja.md','docs/LINUX-ja.md']
    new += [str(p.relative_to(root)).replace('\\','/') for directory in ['include','util'] for p in (root/directory).iterdir()
        if p.is_file() and p.suffix in ('.h','.cpp','.py') and str(p.relative_to(root)).replace('\\','/') not in base and p.name!='update_port_patch.py']
    for name in sorted(set(new)):
        if name not in base:patch+=delta(name,b'',(root/name).read_bytes().replace(b'\r\n',b'\n'))
    (root/'ports/www/mod_uploader/files/patch-modern-freebsd').write_bytes(patch)
    makefile=root/'ports/www/mod_uploader/Makefile';data=makefile.read_text(encoding='utf8')
    start=data.index('pre-patch:');end=data.index('post-configure:',start)
    block="pre-patch:\n\t${PERL} -pi -e 's/\\r\\n/\\n/g' \\\n"+' \\\n'.join('\t\t${WRKSRC}/'+name for name in changed)
    block+="\n\npost-patch:\n\t${REINPLACE_CMD} -e '1s|.*|#!${PYTHON_CMD}|' ${WRKSRC}/util/*.py\n\n"
    makefile.write_text(data[:start]+block+data[end:],encoding='utf8',newline='\n')
    print(f'Port patch regenerated: {len(changed)} existing files, {len(set(new))} added files')

if __name__=='__main__':main()
