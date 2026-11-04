# SPDX-License-Identifier: Zlib
"""Find the Apache installation under test on FreeBSD and Enterprise Linux."""
import functools
import os
from pathlib import Path
import shutil
import subprocess


def program(variable, *names):
    value = os.environ.get(variable)
    if value:
        return value
    for name in names:
        value = shutil.which(name)
        if value:
            return value
    raise RuntimeError('Required program missing: ' + '/'.join(names))


@functools.lru_cache(None)
def apxs_query(key):
    return subprocess.check_output([program('APXS', 'apxs', 'apxs2'), '-q', key],
                                   text=True).strip()


def httpd():
    return os.environ.get('HTTPD') or str(Path(apxs_query('SBINDIR')) / apxs_query('TARGET'))


@functools.lru_cache(None)
def builtins():
    return subprocess.check_output([httpd(), '-l'], text=True).split()


def load_module(name):
    # Some distributions compile unixd into httpd instead of shipping a DSO.
    if 'mod_' + name + '.c' in builtins():
        return ''
    path = Path(os.environ.get('APACHE_MODULE_DIR') or apxs_query('LIBEXECDIR')) / ('mod_' + name + '.so')
    if not path.is_file():
        raise RuntimeError('Required Apache module missing: ' + str(path))
    return 'LoadModule ' + name + '_module "' + str(path) + '"\n'
