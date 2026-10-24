// SPDX-License-Identifier: Zlib
#include "Environment.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <random>
#include <limits>
#include "apr_general.h"
#include "UploadItem.h"
#include "UploadItemList.h"
#include "HtmlSafety.h"
#include "MetadataSafety.h"
#include "BasicFileWriter.h"
#include "RFC1867Parser.h"
#define TEMPLATE_INSTANTIATION
#include "MultipartMessageParser.cpp"
#include "RFC1867Parser.cpp"
// Heap adapter exposes the list's exact allocation to ASan redzones.
extern "C" void *apr_shm_baseaddr_get(const apr_shm_t *memory) {
    return const_cast<apr_shm_t *>(memory);
}
// Deterministic timeout injection exercises the real lock constructors without a 300s wait.
bool ReadWriteLocker::should_timeout(apr_uint32_t) { return true; }
struct MemoryReader {
    const std::string *data; size_t pos, chunk;
    MemoryReader(const std::string& s,size_t c):data(&s),pos(0),chunk(c){}
    void read(char *out, apr_size_t capacity, apr_size_t *read_size) {
        *read_size=std::min(std::min(static_cast<size_t>(capacity),chunk),data->size()-pos);
        memcpy(out,data->data()+pos,*read_size);pos+=*read_size;
    }
};
static unsigned parse(const std::string& body,size_t chunk,const char *directory,bool must_reject=false) {
    apr_pool_t *pool;assert(apr_pool_create(&pool,NULL)==APR_SUCCESS);unsigned result=0;
    try { MemoryReader reader(body,chunk);RFC1867Parser<MemoryReader> parser(pool,reader,directory,1024,4096,8);
          parser.parse("multipart/form-data; boundary=audit-boundary",body.size());assert(!must_reject);result=1;
    } catch(const char *) {result=2;}
    apr_pool_destroy(pool);return result;
}
int main(int argc,char **argv) {
    assert(argc==2);assert(apr_initialize()==APR_SUCCESS);unsigned checks=0;
    apr_atomic_t lock=0x7fff;
    try {ReadLocker guard(&lock);assert(false);}catch(const char *){assert(lock==0x7fff);++checks;}
    try {WriteLocker guard(&lock);assert(false);}catch(const char *){assert((lock&0x7fff)==0x7fff && (lock&0x3f0000)==0);++checks;}
    lock=0;{WriteLocker guard(&lock);assert(WriteLocker::is_locked(&lock));}assert(!ReadLocker::is_locked(&lock));++checks;
    {ReadLocker a(&lock);{ReadLocker b(&lock);assert((lock&0x7fff)==2);}assert((lock&0x7fff)==1);}assert(!ReadLocker::is_locked(&lock));++checks;
    // Actual list implementation, heap redzones around exactly sized storage.
    size_t bytes=UploadItemList::get_memory_size(2);void *storage=malloc(bytes);assert(storage);
    UploadItemList *list=UploadItemList::get_instance(reinterpret_cast<apr_shm_t *>(storage),100,2);
    UploadItem::header_t h;h.id=1;h.file_size=10;
    list->add(reinterpret_cast<UploadItem *>(&h));h.id=2;list->add(reinterpret_cast<UploadItem *>(&h));
    try {h.id=3;list->add(reinterpret_cast<UploadItem *>(&h));assert(false);}catch(const char *){++checks;}
    assert(list->size()==2&&list->get_total_file_size()==20);++checks;
    try{list->get_by_index(2);assert(false);}catch(const char *){++checks;}
    assert(list->is_full(std::numeric_limits<apr_uint64_t>::max()));++checks;
    free(storage);
    UploadItem::header_t copy;memcpy(&copy,&h,sizeof(h));
    assert(MetadataSafety::same_identity(h,copy));++checks;
    ++copy.mtime;assert(!MetadataSafety::same_identity(h,copy));++checks;copy.mtime=h.mtime;
    strcpy(copy.download_pass,"different");assert(!MetadataSafety::same_identity(h,copy));++checks;copy.download_pass[0]=0;
    ++copy.index;assert(!MetadataSafety::same_identity(h,copy));++checks;

    assert(HtmlSafety::escape("\"'><script>&")=="&quot;&#39;&gt;&lt;script&gt;&amp;");++checks;
    // Corpus: valid input split at every byte, truncations, NUL and duplicate fields, mutations.
    std::string body="--audit-boundary\r\nContent-Disposition: form-data; name=\"comment\"\r\n\r\nhello\r\n--audit-boundary--\r\n";
    for(size_t chunk:{size_t(1),size_t(7),size_t(64),size_t(4096)}){assert(parse(body,chunk,argv[1])==1);++checks;}
    for(size_t n=0;n<body.size();++n){parse(body.substr(0,n),7,argv[1]);++checks;}
    std::string nul=body;nul.insert(nul.find("hello")+2,1,'\0');parse(nul,1,argv[1],true);++checks;
    std::string duplicate="--audit-boundary\r\nContent-Disposition: form-data; name=\"id\"\r\n\r\n1\r\n--audit-boundary\r\nContent-Disposition: form-data; name=\"id\"\r\n\r\n2\r\n--audit-boundary--\r\n";
    parse(duplicate,3,argv[1],true);++checks;
    std::mt19937 random(20261024);
    for(unsigned i=0;i<2000;++i){std::string mutated=body;for(unsigned j=0;j<1+i%8;++j)mutated[random()%mutated.size()]=static_cast<char>(random()%256);parse(mutated,1+random()%128,argv[1]);++checks;}
    // Binary file payload is intentionally permitted, including embedded NUL.
    std::string file="--audit-boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.txt\"\r\nContent-Type: application/octet-stream\r\n\r\n";
    file.append("a\0b",3);file+="\r\n--audit-boundary--\r\n";assert(parse(file,1,argv[1])==1);++checks;
    apr_terminate();std::printf("audit-sanitizer: %u checks passed (real APR/parser/list; ASan+UBSan)\n",checks);
}
