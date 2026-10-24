// Tests actual buffer code with APR size type substituted; not an APR integration test.
#define ENVIRONMENT_H
#define MACRO_H
#define MESSAGE_H
#include <cstdlib>
#include <cstring>
#include <cassert>
#include <iostream>
#define MESSAGE_BUG_FOUND "bounds"
#define THROW(x) throw x
#define MALLOC(p,t,u,n) do { p=static_cast<t>(malloc((u)*(n))); if(!p) throw "alloc"; } while(0)
#include "../src/MultipartMessageParserBuffer.cpp"
int main() {
    MultipartMessageParserBuffer b(8);
    memset(b.get_data(), 'a', 8); b.set_size(8);
    assert(b.get_data()[8] == 0);
    b.erase(3); assert(b.get_size()==5 && b.get_data()[5]==0);
    bool caught=false; try {b.add_size(static_cast<apr_size_t>(-1));}catch(const char*){caught=true;} assert(caught);
    caught=false; try{b.erase(6);}catch(const char*){caught=true;}assert(caught);
    caught=false; try{b.set_size(9);}catch(const char*){caught=true;}assert(caught);
    b.reserve(20); assert(b.get_size()==5 && b.get_data()[5]==0);
    caught=false; try{b.reserve(4);}catch(const char*){caught=true;}assert(caught);
    std::cout << "buffer: 7 checks passed\n";
}
