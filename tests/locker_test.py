# SPDX-License-Identifier: Zlib
"""Compile actual Locker body; inject APR unlock failures, including unwinding."""
import os, subprocess, tempfile
from pathlib import Path
source=(Path(__file__).resolve().parents[1]/'include/Locker.h').read_text(encoding='utf8')
body=source[source.index('class Locker:'):source.index('\n#endif')]
prefix=r"""
#include <cstdio>
#include <cassert>
#include <stdexcept>
#include <string>
#include <type_traits>
class Uncopyable {};
typedef int apr_status_t;
struct apr_global_mutex_t {};
#define APR_SUCCESS 0
#define MEMORY_BARRIER
#define MESSAGE_MUTEX_LOCK_FAILED "lock failed"
#define THROW(x) throw std::runtime_error(x)
static int lock_result=0,unlock_result=0,unlocks=0;
int apr_global_mutex_lock(apr_global_mutex_t*){return lock_result;}
int apr_global_mutex_unlock(apr_global_mutex_t*){++unlocks;return unlock_result;}
"""
suffix=r"""
int main(){
 static_assert(std::is_nothrow_destructible<Locker>::value,"Locker destructor must not throw");
 apr_global_mutex_t mutex;bool locked=false;
 {Locker l(&mutex,&locked);assert(locked);}assert(!locked&&unlocks==1);
 unlock_result=5;{Locker l(&mutex,&locked);}assert(locked&&unlocks==2);
 try{Locker l(&mutex,&locked);throw std::runtime_error("outer");}catch(const std::runtime_error& e){assert(std::string(e.what())=="outer");}
 assert(locked&&unlocks==3);unlock_result=0;
 {Locker l(&mutex);}assert(unlocks==4);
 lock_result=7;try{Locker l(&mutex);assert(false);}catch(const std::runtime_error&){}assert(unlocks==4);
}
"""
with tempfile.TemporaryDirectory() as d:
 cpp=Path(d)/'locker.cpp';exe=Path(d)/'locker';cpp.write_text(prefix+body+suffix,encoding='utf8')
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++11','-Wall','-Wextra','-Werror',str(cpp),'-o',str(exe)],check=True)
 p=subprocess.run([str(exe)],capture_output=True,check=True)
 assert p.stderr.count(b'mutex unlock failed')==2,p.stderr
print('locker: 6 checks passed (actual destructor, injected APR failures; not real APR failure)')
