// Actual reader implementation against a simulated filter/bucket API.
#include "../src/ApacheRequestReader.cpp"
#include <iostream>
int main(){
 MockConnection c={NULL};ApacheResponse::Handle h={NULL,&c,NULL};RequestReader::post_progress_t p;
 apr_bucket meta={"",1,NULL}, data={"abcdefghijk",0,NULL}, eos={"",2,NULL};
 input.push_back(&meta);input.push_back(&data);input.push_back(&eos);
 ApacheRequestReader r(&p,&h);char buf[6];std::size_t n;std::string result;
 for(int i=0;i<3;++i){memset(buf,'!',6);r.read(buf+1,4,&n);assert(n<=4&&buf[0]=='!'&&buf[5]=='!');result.append(buf+1,n);}
 assert(result=="abcdefghijk"&&r.count==11);r.read(buf,4,&n);assert(n==0);r.read(buf,4,&n);assert(n==0);
 apr_bucket bad={"abc",0,NULL};input.push_back(&bad);ApacheRequestReader fail(&p,&h);mock_error=1;
 bool caught=false;try{fail.read(buf,4,&n);}catch(const char*){caught=true;}assert(caught);
 std::cout<<"reader: 7 checks passed (mock APR/Apache)\n";
}
