#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Read-only storage capacity and unfinished-work check, suitable for cron."""
import argparse
import json
import os
from pathlib import Path
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('data','file','thumb','temp'): p.add_argument('--'+name+'-dir',type=Path,required=True)
    p.add_argument('--min-free-mib',type=int,default=512)
    p.add_argument('--min-free-percent',type=float,default=10)
    args=p.parse_args()
    if args.min_free_mib<0 or not 0<=args.min_free_percent<=100: p.error('Invalid threshold')
    problems=[]; report={}
    for name in ('data','file','thumb','temp'):
        path=getattr(args,name+'_dir'); info=os.statvfs(path)
        free=info.f_bavail*info.f_frsize; total=info.f_blocks*info.f_frsize
        percent=100*free/total if total else 0
        report[name]={'path':str(path),'available_bytes':free,'available_percent':round(percent,2),'available_inodes':info.f_favail}
        if free<args.min_free_mib*1024*1024 or percent<args.min_free_percent: problems.append(name+': low disk space')
        if info.f_files and info.f_favail<100: problems.append(name+': low free inode count')
    for marker in ('.storage-transaction','.migration-in-progress'):
        path=args.data_dir/marker
        if path.exists() or path.is_symlink(): problems.append('Offline recovery required: '+marker)
    print(json.dumps({'storage':report,'problems':problems},indent=2))
    return 1 if problems else 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print('Storage health check failed: '+str(exc),file=sys.stderr); raise SystemExit(2)
