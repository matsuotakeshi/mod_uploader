// SPDX-License-Identifier: Zlib
// Native ABI converter. This tool never edits its input file.
#include "Environment.h"
#include "UploadItem.h"
#include "PasswordHash.h"
#include "MetadataSafety.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <cstring>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
typedef UploadItem::header_t Header;

static std::vector<char> read_file(const char *path) {
    struct stat st;if(lstat(path,&st)!=0||!S_ISREG(st.st_mode)||st.st_nlink!=1||st.st_size<24||st.st_size>4096)
        throw "Not a regular native metadata file";
    std::ifstream in(path,std::ios::binary);std::vector<char> data(static_cast<size_t>(st.st_size));
    if(!in.read(data.data(),data.size()))throw "Cannot read metadata";return data;
}
template<size_t N> static void terminated(const char (&s)[N]) {if(!memchr(s,0,N))throw "Unterminated metadata field";}
template<class T> static void validate_fields(const T& h) {
    terminated(h.identifier);terminated(h.version);terminated(h.date);terminated(h.ip_address);
    terminated(h.file_name);terminated(h.file_mime);terminated(h.file_ext);terminated(h.file_digest);
    terminated(h.remove_pass);terminated(h.download_pass);terminated(h.comment);
    if(strcmp(h.identifier,"mod_uploader")!=0)throw "Invalid metadata identifier";
    if ((reinterpret_cast<const unsigned char*>(&h.flags)[0]&~3U)!=0)throw "Invalid metadata flags";
}
template<class T> static Header convert(const T& old) {
    validate_fields(old);Header h;
    h.id=old.id;h.index=old.index;h.download_count=old.download_count;memcpy(&h.flags,&old.flags,sizeof(h.flags));
    h.is_need_sync=false;h.file_size=old.file_size;h.mtime=old.mtime;
#define COPY_FIELD(field) memcpy(h.field,old.field,sizeof(h.field))
    COPY_FIELD(date);COPY_FIELD(ip_address);COPY_FIELD(file_name);COPY_FIELD(file_mime);
    COPY_FIELD(file_ext);COPY_FIELD(file_digest);COPY_FIELD(comment);
#undef COPY_FIELD
    std::string remove=PasswordHash::make(old.remove_pass),download=PasswordHash::make(old.download_pass);
    memcpy(h.remove_pass,remove.c_str(),remove.size()+1);memcpy(h.download_pass,download.c_str(),download.size()+1);
    return h;
}
static Header load(const std::vector<char>& data,bool migrate) {
    int version=data[16]-'0';Header h;
    if(version==4) {
        if(data.size()!=sizeof(Header))throw "Wrong native v4 metadata size";
        memcpy(&h,data.data(),sizeof(h));validate_fields(h);
        if(!PasswordHash::valid(h.remove_pass)||!PasswordHash::valid(h.download_pass))throw "Invalid v4 password encoding";
    } else if(version==3) {
        if(data.size()!=sizeof(UploadItem::header_ver3_t))throw "Wrong native v3 metadata size";
        UploadItem::header_ver3_t old;memcpy(&old,data.data(),sizeof(old));validate_fields(old);
        if(migrate){h=convert(old);h.atime=old.atime;}else {h.id=old.id;}
    } else if(version==2) {
        if(data.size()!=sizeof(UploadItem::header_ver2x_t))throw "Wrong native v2 metadata size";
        UploadItem::header_ver2x_t old;memcpy(&old,data.data(),sizeof(old));validate_fields(old);
        if(migrate){h=convert(old);h.atime=old.mtime;}else {h.id=old.id;}
    } else throw "Unsupported metadata version";
    if(migrate && !MetadataSafety::valid(h)) throw "Unsafe metadata strings or path components";
    return h;
}
static void write_file(const char *path,const void *data,size_t size) {
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);if(fd<0)throw "Output must not already exist";
    size_t n=0;while(n<size){ssize_t count=write(fd,static_cast<const char*>(data)+n,size-n);if(count<0&&errno==EINTR)continue;
        if(count<=0){close(fd);throw "Write failed";}n+=count;}
    if(fsync(fd)!=0){close(fd);throw "fsync failed";}if(close(fd)!=0)throw "close failed";
}
int main(int argc,char **argv) {
    try {
        if(argc==3&&(strcmp(argv[1],"--fixture3")==0||strcmp(argv[1],"--fixture2")==0||strcmp(argv[1],"--fixture3-empty")==0)) {
            UploadItem::header_ver3_t h;h.id=1;h.index=0;h.file_size=16;h.mtime=1700000000000000LL;h.atime=h.mtime;
            strcpy(h.date,"23/11/14(Tue) 22:13:20");strcpy(h.ip_address,"127.0.0.1");strcpy(h.file_name,"fixture.txt");
            strcpy(h.file_mime,"text/plain");strcpy(h.file_ext,"txt");strcpy(h.file_digest,"0123456789abcdef0123456789abcdef");
            strcpy(h.remove_pass,"remove123");strcpy(h.download_pass,"download123");strcpy(h.comment,"migration fixture");
            if(strcmp(argv[1],"--fixture3-empty")==0){h.remove_pass[0]=0;h.download_pass[0]=0;}
            if(strcmp(argv[1],"--fixture2")!=0)write_file(argv[2],&h,sizeof(h));
            else {UploadItem::header_ver2x_t v;v.id=h.id;v.index=h.index;v.file_size=h.file_size;v.mtime=h.mtime;
#define COPY_OLD(field) memcpy(v.field,h.field,sizeof(v.field))
                COPY_OLD(date);COPY_OLD(ip_address);COPY_OLD(file_name);COPY_OLD(file_mime);COPY_OLD(file_ext);COPY_OLD(file_digest);COPY_OLD(remove_pass);COPY_OLD(download_pass);COPY_OLD(comment);
#undef COPY_OLD
                strcpy(v.version,"2.0.0");write_file(argv[2],&v,sizeof(v));}return 0;
        }
        if(argc<3)throw "Usage: password_tool --inspect FILE | --convert IN OUT | --verify-remove FILE | --verify-download FILE";
        std::vector<char> data=read_file(argv[2]);bool inspect=strcmp(argv[1],"--inspect")==0;
        Header h=load(data,!inspect);
        if(inspect){std::cout<<"{\"version\":"<<static_cast<int>(data[16]-'0')<<",\"id\":"<<h.id<<",\"bytes\":"<<data.size()<<"}\n";return 0;}
        if(strcmp(argv[1],"--convert")==0&&argc==4){write_file(argv[3],&h,sizeof(h));return 0;}
        if(strcmp(argv[1],"--verify-remove")==0||strcmp(argv[1],"--verify-download")==0) {
            if(data[16]!='4')throw "Verify requires migrated metadata";
            std::string password;std::getline(std::cin,password);
            bool ok=PasswordHash::verify(strcmp(argv[1],"--verify-remove")==0?h.remove_pass:h.download_pass,password.c_str());
            OPENSSL_cleanse(&password[0],password.size());return ok?0:3;
        }
        throw "Invalid arguments";
    }catch(const char *message){std::cerr<<message<<"\n";return 1;}
    catch(...){std::cerr<<"Metadata operation failed\n";return 1;}
}
