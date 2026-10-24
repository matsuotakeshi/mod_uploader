#pragma once
#include <cstddef>
#include <cstring>
#include <string>
#include <deque>
#include <cassert>
typedef std::size_t apr_size_t;
typedef int apr_status_t;
#define AP_SERVER_MAJORVERSION_NUMBER 2
#define APR_SUCCESS 0
#define APR_BLOCK_READ 0
#define AP_MODE_READBYTES 0
#define UNLIKELY(x) (x)
#define THROW(x) throw x
#define MESSAGE_POST_READ_FAILED "read failed"
#define SOURCE_INFO_ADD(x)
struct apr_bucket {std::string data; int kind; apr_bucket *next;};
struct apr_bucket_brigade {apr_bucket sentinel; apr_bucket *first;};
struct MockConnection {void *bucket_alloc;};
namespace ApacheResponse {struct Handle {void *pool; MockConnection *connection; void *input_filters;};}
static int mock_error=0;
static std::deque<apr_bucket*> input;
static apr_bucket_brigade *apr_brigade_create(void*,void*) {auto b=new apr_bucket_brigade; b->first=&b->sentinel;return b;}
static void apr_brigade_cleanup(apr_bucket_brigade*) {}
static void apr_brigade_destroy(apr_bucket_brigade *b){delete b;}
#define APR_BRIGADE_SENTINEL(b) (&(b)->sentinel)
#define APR_BRIGADE_FIRST(b) ((b)->first)
#define APR_BRIGADE_EMPTY(b) ((b)->first==&(b)->sentinel)
#define APR_BUCKET_IS_EOS(b) ((b)->kind==2)
#define APR_BUCKET_IS_METADATA(b) ((b)->kind==1)
#define APR_BUCKET_NEXT(b) ((b)->next)
static int apr_bucket_read(apr_bucket *b,const char **p,std::size_t *n,int){*p=b->data.data();*n=b->data.size();return mock_error;}
static int apr_bucket_split(apr_bucket *b,std::size_t n){auto tail=new apr_bucket{b->data.substr(n),0,b->next};b->next=tail;return 0;}
static int ap_get_brigade(void*,apr_bucket_brigade *b,int,int,std::size_t){
 if(input.empty()) return 1;
 b->first=input.front();input.pop_front();b->first->next=&b->sentinel;return 0;
}
struct RequestReader {
 struct post_progress_t{};
 std::size_t count;
 explicit RequestReader(post_progress_t*):count(0){}
 void update(std::size_t n){count+=n;}
 std::size_t get_block_size(){return 4096;}
};
class ApacheRequestReader:public RequestReader {
 public:
 ApacheRequestReader(post_progress_t*,ApacheResponse::Handle*);
 ~ApacheRequestReader();
 void read(char*,std::size_t,std::size_t*);
 static const std::size_t READ_SLEEP_FACTOR, READ_SLEEP_USEC;
 private:
 void get_brigade();
 ApacheResponse::Handle *request_;
 apr_bucket_brigade *brigade_;
 apr_bucket *bucket_;
 bool is_eos_;
};
