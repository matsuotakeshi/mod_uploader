#include "../include/UploadSafety.h"
#include <cassert>
#include <string>
#include <iostream>
#include <limits>
int main(){
 const char *token="abc123";
 std::string s="x\r\n--abc123\r\ny";
 assert(UploadSafety::boundary(s.data(),s.size(),token,6)==s.data()+5);
 s="\r\n--abc123--";assert(UploadSafety::boundary(s.data(),s.size(),token,6)==s.data()+4);
 const char *bad[]={"abc123", "xabc123", "\r\n--abc123X!", "\r\n--abc123", "\r\n--abc123-", "--abc123\r\n"};
 for(unsigned i=0;i<6;++i) assert(!UploadSafety::boundary(bad[i],strlen(bad[i]),token,6));
 for(unsigned n=0;n<10000;++n){
   std::string x(n%200,'z');x += "\r\n--abc123\r\n";
   assert(UploadSafety::boundary(x.data(),x.size(),token,6)==x.data()+n%200+4);
   for(unsigned cut=1;cut<=7;++cut) assert(!UploadSafety::boundary(x.data(),x.size()-cut,token,6));
 }
 assert(UploadSafety::allowed(9,1,10));assert(!UploadSafety::allowed(9,2,10));
 assert(!UploadSafety::allowed(11,0,10));
 assert(!UploadSafety::allowed(1,std::numeric_limits<std::size_t>::max(),10));
 std::cout<<"safety: 80012 checks passed\n";
}
