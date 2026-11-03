#!/usr/local/bin/python3
import json, os, pathlib, shutil, subprocess, sys
base=pathlib.Path(sys.argv[1]).resolve()
variant=sys.argv[2]
assert variant in ('plain','thumb')
jail_name='uploader151-uploaderq4-'+variant+'-n'
jailpath=pathlib.Path(subprocess.check_output(['jls','-j',jail_name,'-h','path'],text=True).splitlines()[-1]).resolve()
expected=base/'poudriere/data/.m'/('uploader151-uploaderq4-'+variant)/'ref'
assert jailpath==expected.resolve(), (jailpath,expected)
review=jailpath/'review'
review.mkdir(mode=0o755)
review.chmod(0o755)
shutil.copytree(base/'source/tests',review/'tests')
(review/'util').symlink_to('/usr/local/libexec/mod_uploader',target_is_directory=True)
adapter=review/'installed'
(adapter/'src').mkdir(parents=True)
for name,target in [('mod_uploader.so','/usr/local/libexec/apache24/mod_uploader.so'),('password_tool','/usr/local/libexec/mod_uploader/password_tool')]:
    (adapter/'src'/name).symlink_to(target)
for name in ('tmpl','img','css','js'):
    (adapter/name).symlink_to('/usr/local/share/mod_uploader/'+name,target_is_directory=True)
(adapter/'swf').mkdir()
shutil.copyfile(base/'source/swf/UploadPanel.swf',adapter/'swf/UploadPanel.swf')
samples=review/'ports/www/mod_uploader/files'
samples.mkdir(parents=True)
for suffix in ('','-root'):
    installed=jailpath/('usr/local/etc/mod_uploader/mod_uploader'+suffix+'.conf.sample')
    text=installed.read_text().replace('/usr/local/share/mod_uploader','%%DATADIR%%')
    (samples/('mod_uploader'+suffix+'.conf.in')).write_text(text)
for path in review.rglob('*'):
    if not path.is_symlink():
        path.chmod(0o755 if path.is_dir() else 0o644)
work=review/'work'
work.mkdir(mode=0o700)
os.chown(work,65534,65534)
out=base/('jail-'+variant)
out.mkdir()
meta=['/bin/sh','-c','freebsd-version -u; id; pkg query "%n-%v" ap24-mod_uploader apache24 python312 ImageMagick7-nox11; ldd /usr/local/libexec/apache24/mod_uploader.so']
with (out/'environment.log').open('w') as log:
    subprocess.run(['jexec',jail_name,*meta],stdout=log,stderr=subprocess.STDOUT,check=True)
print('SWF static routing uses a source fixture; SWF is not shipped by this Port.',flush=True)
results={}
for test in ('root_http','operations_http','root_sample'):
    cmd=['jexec','-u','nobody',jail_name,'env','PYTHONDONTWRITEBYTECODE=1','MAGICK_CONVERT=/usr/local/bin/magick','/usr/local/bin/python3.12','/review/tests/'+test+'_test.py','--build-root','/review/installed','--workdir','/review/work']
    if variant=='thumb' and test!='root_sample':cmd+=['--thumbnail']
    if test=='operations_http':cmd+=['--tools-root','/usr/local/libexec/mod_uploader']
    with (out/(test+'.log')).open('w') as log:
        log.write('COMMAND: '+' '.join(cmd)+'\n');log.flush()
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    results[test]=result.returncode
    print(test,result.returncode,(out/(test+'.log')).read_text()[-1700:],flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
sys.exit(any(results.values()))
