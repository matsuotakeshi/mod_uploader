// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_STORAGE_LOCK_H
#define UPLOADER_STORAGE_LOCK_H
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <string>
namespace StorageLock {
inline apr_status_t release(void *data) {int *fd=static_cast<int*>(data);close(*fd);return APR_SUCCESS;}
inline void hold(apr_pool_t *pool,const char *directory) {
    std::string path=std::string(directory)+"/.format-lock";
    int fd=open(path.c_str(),O_RDONLY|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0)throw "Cannot open storage lock";
    struct stat st;
    if(fstat(fd,&st)!=0||!S_ISREG(st.st_mode)||flock(fd,LOCK_SH|LOCK_NB)!=0) {
        close(fd);throw "Storage migration is running; stop and retry later";
    }
    int *handle=static_cast<int*>(apr_palloc(pool,sizeof(int)));*handle=fd;
    apr_pool_cleanup_register(pool,handle,release,apr_pool_cleanup_null);
}
}
#endif
