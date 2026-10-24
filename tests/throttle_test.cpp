// SPDX-License-Identifier: Zlib
#include "AuthenticationThrottle.h"
#include <cassert>
#include <cstdlib>
#include <sys/wait.h>
#include <signal.h>
#include <cstdio>
#include <thread>
#include <atomic>
#include <stdexcept>
int main() {
    char name[]="/tmp/uploader-throttle-XXXXXX";const char *dir=mkdtemp(name);assert(dir);
    unsigned checks=0;
    for(unsigned i=0;i<10;++i){AuthenticationThrottle t(dir,"192.0.2.1",true,1000);assert(t.allowed());++checks;}
    {AuthenticationThrottle t(dir,"192.0.2.1",true,1001);assert(!t.allowed()&&t.retry_after()==59);++checks;}
    {AuthenticationThrottle t(dir,"192.0.2.1",true,999);assert(!t.allowed());++checks;}
    {AuthenticationThrottle t(dir,"192.0.2.1",true,1060);assert(t.allowed());++checks;}
    // Closing a guard during exception unwinding releases its concurrency slot.
    try{AuthenticationThrottle t(dir,"192.0.2.2",true,1060);assert(t.allowed());throw std::runtime_error("test");}catch(const std::runtime_error&){}
    {AuthenticationThrottle a(dir,"192.0.2.3",true,1060),b(dir,"192.0.2.4",true,1060),c(dir,"192.0.2.5",true,1060);assert(a.allowed()&&b.allowed()&&!c.allowed());++checks;}
    int pipefd[2];assert(pipe(pipefd)==0);pid_t child=fork();assert(child>=0);
    if(child==0){close(pipefd[0]);AuthenticationThrottle t(dir,"192.0.2.6",true,1060);char c=t.allowed()?'Y':'N';assert(write(pipefd[1],&c,1)==1);for(;;)pause();}
    close(pipefd[1]);char ready;assert(read(pipefd[0],&ready,1)==1&&ready=='Y');close(pipefd[0]);
    {AuthenticationThrottle a(dir,"192.0.2.7",true,1060),b(dir,"192.0.2.8",true,1060);assert(a.allowed()&&!b.allowed());++checks;
     assert(kill(child,SIGKILL)==0);int status;assert(waitpid(child,&status,0)==child);
     AuthenticationThrottle c(dir,"192.0.2.9",true,1060);assert(c.allowed());++checks;}
    std::atomic<int> entered(0),release(0),allowed(0);
    auto worker=[&](const char *ip){AuthenticationThrottle t(dir,ip,true,1060);if(t.allowed())++allowed;++entered;while(!release.load())std::this_thread::yield();};
    std::thread a(worker,"198.51.100.1");while(entered.load()!=1)std::this_thread::yield();
    std::thread b(worker,"198.51.100.2");while(entered.load()!=2)std::this_thread::yield();
    {AuthenticationThrottle t(dir,"198.51.100.3",true,1060);assert(allowed.load()==2&&!t.allowed());++checks;}
    release=1;a.join();b.join();
    // Restart/new guard keeps the same persisted rate budget.
    for(unsigned i=0;i<9;++i){AuthenticationThrottle t(dir,"192.0.2.1",true,1061);assert(t.allowed());}
    {AuthenticationThrottle t(dir,"192.0.2.1",true,1062);assert(!t.allowed());++checks;}
    char bad[]="/tmp/uploader-throttle-bad-XXXXXX";assert(mkdtemp(bad));std::string path=std::string(bad)+"/.auth-attempts";
    assert(symlink("/dev/null",path.c_str())==0);
    {AuthenticationThrottle t(bad,"192.0.2.1",true,1060);assert(!t.allowed());++checks;}
    unlink(path.c_str());int fd=open(path.c_str(),O_WRONLY|O_CREAT,0600);assert(fd>=0);assert(write(fd,"bad",3)==3);close(fd);
    {AuthenticationThrottle t(bad,"192.0.2.1",true,1060);assert(!t.allowed());++checks;}
    std::printf("throttle: %u checks passed (persistent IP budget, threads, processes, crash release, unsafe state)\n",checks);
    for(const char *root:{dir,static_cast<const char*>(bad)}) {for(const char *file:{".auth-slot-0",".auth-slot-1",".auth-attempts"})unlink((std::string(root)+"/"+file).c_str());rmdir(root);}
}
