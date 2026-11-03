#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Read-only FreeBSD package audit; downloads VuXML into a new private report directory."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

def command(args):
    result=subprocess.run(args,capture_output=True,text=True,errors='replace',timeout=300)
    return result.returncode,result.stdout+result.stderr

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); os.umask(0o077); args.output.mkdir(mode=0o700)
    if not sys.platform.startswith('freebsd'): raise RuntimeError('This tool requires FreeBSD pkg')
    pkg='/usr/local/sbin/pkg'
    status,listing=command([pkg,'query','%n-%v'])
    if status: raise RuntimeError(listing)
    roots=[n for n in listing.splitlines() if n.startswith(('apache24-','apr-','ImageMagick6-','ImageMagick7-','python31','libiconv-'))]
    packages=set(); pending=roots[:]
    while pending:
        name=pending.pop()
        if name in packages: continue
        packages.add(name)
        code,deps=command([pkg,'query','%dn-%dv',name])
        if code not in (0,1): raise RuntimeError(deps)
        if code==0: pending.extend(n for n in deps.splitlines() if n)
    database=args.output/'vuln.xml'
    code,output=command([pkg,'audit','-F','-f',str(database)])
    (args.output/'host-audit.log').write_text(output,encoding='utf8')
    if code not in (0,1) or not database.exists(): raise RuntimeError('Vulnerability database refresh failed; see host-audit.log')
    results=[]
    for name in sorted(packages):
        code,text=command([pkg,'audit','-f',str(database),name])
        (args.output/(name+'.log')).write_text(text,encoding='utf8')
        if code not in (0,1): raise RuntimeError('Package audit failed: '+name)
        results.append({'package':name,'audit_exit':code,'vulnerable':code==1})
    version={}
    for label,cmd in [('freebsd',['freebsd-version','-ku']),('openssl',['/usr/bin/openssl','version','-a']),('apache',['/usr/local/sbin/httpd','-v'])]:
        code,text=command(cmd); version[label]={'exit':code,'output':text}
    report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':roots,'environment':version,'packages':results,
        'limits':'pkg audit covers registered packages and published VuXML entries; base-system OpenSSL and private prefixes need separate advisory review.'}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    bad=[r['package'] for r in results if r['vulnerable']]
    print(f'{len(results)} packages checked; {len(bad)} with VuXML findings')
    for name in bad: print(name)
    return 1 if bad else 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print('Audit incomplete: '+str(exc),file=sys.stderr); raise SystemExit(2)
