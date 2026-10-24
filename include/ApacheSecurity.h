// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_APACHE_SECURITY_H
#define UPLOADER_APACHE_SECURITY_H
#include "SecurityTokens.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <cerrno>
namespace ApacheSecurity {
inline std::string key(const char *directory) {
    std::string path=std::string(directory)+"/.csrf-key";
    int fd=open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(fd<0 && errno==ENOENT) {
        std::string tmp=path+".tmp."+SecurityTokens::random_hex();
        int out=open(tmp.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        if(out<0)throw "Cannot create CSRF secret";
        unsigned char bytes[32];bool good=RAND_bytes(bytes,32)==1;size_t written=0;
        while(good && written<sizeof(bytes)) {
            ssize_t n=write(out,bytes+written,sizeof(bytes)-written);
            if(n<0 && errno==EINTR)continue;if(n<=0){good=false;break;}written+=n;
        }
        if(good && fsync(out)!=0)good=false;
        if(close(out)!=0)good=false;
        OPENSSL_cleanse(bytes,sizeof(bytes));
        if(!good){unlink(tmp.c_str());throw "Cannot write CSRF secret";}
        int result=link(tmp.c_str(),path.c_str());int saved=errno;unlink(tmp.c_str());
        if(result!=0 && saved!=EEXIST)throw "Cannot publish CSRF secret";
        fd=open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    }
    if(fd<0)throw "Cannot open CSRF secret";
    struct stat st;
    if(fstat(fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_size!=32 ||
        (st.st_mode&077)!=0 || st.st_uid!=geteuid()) {close(fd);throw "Unsafe CSRF secret permissions or owner";}
    std::string result(32,'\0');size_t count=0;
    while(count<32) {ssize_t n=read(fd,&result[count],32-count);if(n<0&&errno==EINTR)continue;
        if(n<=0){close(fd);throw "Cannot read CSRF secret";}count+=n;}
    close(fd);return result;
}
inline const char *cookie_name(const char *base) {return std::strncmp(base,"https://",8)==0?"__Host-mod_uploader_sid":"mod_uploader_sid";}
inline std::string session(request_rec *r,const char *base) {
    const char *header=apr_table_get(r->headers_in,"Cookie");if(!header)return "";
    std::string all(header),name=std::string(cookie_name(base))+"=",value;size_t start=0;int found=0;
    while(start<all.size()) {
        size_t end=all.find(';',start);if(end==std::string::npos)end=all.size();
        while(start<end&&(all[start]==' '||all[start]=='\t'))++start;
        if(all.compare(start,name.size(),name)==0){value=all.substr(start+name.size(),end-start-name.size());++found;}
        start=end+1;
    }
    return found==1&&SecurityTokens::session_valid(value)?value:"";
}
inline bool verify(request_rec *r,const char *token) {
    if(!token)return false;
    const char *base=apr_table_get(r->notes,"uploader-csrf-base");
    const char *dir=apr_table_get(r->notes,"uploader-csrf-dir");
    return base&&dir&&SecurityTokens::verify(key(dir),base,session(r,base),token,static_cast<uint64_t>(std::time(NULL)));
}
inline bool prepare(request_rec *r,const char *directory,const char *base) {
    apr_table_setn(r->notes,"uploader-csrf-base",base);apr_table_setn(r->notes,"uploader-csrf-dir",directory);
    if(r->method_number==M_POST) {
        if(session(r,base).empty())return false;
        const char *header=apr_table_get(r->headers_in,"X-CSRF-Token");
        if(header) {if(!verify(r,header))return false;apr_table_setn(r->notes,"uploader-csrf-verified","1");}
        return true;
    }
    std::string sid=session(r,base);
    if(sid.empty()) {
        sid=SecurityTokens::random_hex();std::string cookie=std::string(cookie_name(base))+"="+sid+"; Path=/; HttpOnly; SameSite=Strict";
        if(std::strncmp(base,"https://",8)==0)cookie+="; Secure";
        apr_table_add(r->headers_out,"Set-Cookie",cookie.c_str());
    }
    std::string token=SecurityTokens::issue(key(directory),base,sid,static_cast<uint64_t>(std::time(NULL)));
    apr_table_set(r->notes,"uploader-csrf-token",token.c_str());
    apr_table_setn(r->headers_out,"Cache-Control","private, no-store");
    apr_table_mergen(r->headers_out,"Vary","Cookie");return true;
}
}
#endif
