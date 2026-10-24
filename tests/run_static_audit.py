#!/usr/bin/env python3
# SPDX-License-Identifier: Zlib
"""Analyze the configured Apache module's translation units, recording all diagnostics."""
import concurrent.futures, json, re, subprocess, sys
from pathlib import Path
build=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve();output.mkdir(exist_ok=True)
deps=(build/'src/GNUmakefile.dep').read_text(errors='replace')
block=deps[deps.index('mod_uploader.so: '):].split('\n\n',1)[0]
names=sorted(set(re.findall(r'([A-Za-z_0-9]+)\.\$\(OBJ_EXT\)',block)))
assert len(names)>30, names
def analyze(name):
    source=build/'src'/(name+'.cpp')
    if not source.exists():return {'source':name,'status':'missing-configured-source'}
    cmd=['clang++','--analyze','-std=c++11','-Wno-deprecated-declarations','-Wno-ignored-attributes',
         '-DUploaderAudit=1','-DUPLOADER_TYPE_APACHE','-DEAPI','-include','httpd.h',
         '-I'+str(build/'include'),'-I'+str(build/'src'),'-I/usr/local/include/apache24','-I/usr/local/include/apr-1','-I/usr/local/include',
         '-Xanalyzer','-analyzer-output=text',str(source)]
    p=subprocess.run(cmd,capture_output=True,text=True,errors='replace',cwd=output)
    text=p.stdout+p.stderr;(output/(name+'.log')).write_text(text)
    return {'source':name+'.cpp','exit':p.returncode,'warnings':len(re.findall(r'warning:',text)),'errors':len(re.findall(r'error:',text))}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:results=list(ex.map(analyze,names))
(output/'summary.json').write_text(json.dumps(results,indent=2)+'\n')
print('static-analysis: '+str(len(results))+' configured module translation units; '+str(sum(x.get('warnings',0) for x in results))+' diagnostics; '+str(sum(x.get('errors',0) for x in results))+' compile errors')
for x in results:
    if x.get('warnings') or x.get('errors') or x.get('status'):print(json.dumps(x))
if any(x.get('exit',1)!=0 for x in results):sys.exit(1)
