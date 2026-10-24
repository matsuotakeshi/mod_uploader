#include "../include/SecurityTokens.h"
#include <cassert>
#include <iostream>
int main() {
    std::string a=PasswordHash::make("password-example"),b=PasswordHash::make("password-example");
    assert(a!=b);assert(a.size()<128);assert(PasswordHash::valid(a.c_str()));
    assert(PasswordHash::verify(a.c_str(),"password-example"));
    assert(!PasswordHash::verify(a.c_str(),"wrong"));assert(!PasswordHash::verify(a.c_str(),"password-example-extra"));
    assert(!PasswordHash::verify("password-example","password-example"));
    assert(PasswordHash::make("").empty());assert(PasswordHash::verify("",""));assert(!PasswordHash::verify("","x"));
    std::string bad=a;bad[14]='0';assert(!PasswordHash::valid(bad.c_str()));
    assert(!PasswordHash::verify("pbkdf2-sha256$999999999999$00$00","x"));
    std::string key(32,'k'),sid=SecurityTokens::random_hex(),other=SecurityTokens::random_hex();
    std::string token=SecurityTokens::issue(key,"https://example.org/up",sid,10000);
    assert(SecurityTokens::verify(key,"https://example.org/up",sid,token,10000));
    assert(SecurityTokens::verify(key,"https://example.org/up",sid,token,17200));
    assert(!SecurityTokens::verify(key,"https://example.org/up",sid,token,17201));
    assert(!SecurityTokens::verify(key,"https://example.org/up",sid,token,9999));
    assert(!SecurityTokens::verify(key,"https://example.org/up",other,token,10000));
    assert(!SecurityTokens::verify(key,"https://example.org/other",sid,token,10000));
    assert(!SecurityTokens::verify(std::string(32,'z'),"https://example.org/up",sid,token,10000));
    token.back()=token.back()=='0'?'1':'0';assert(!SecurityTokens::verify(key,"https://example.org/up",sid,token,10000));
    assert(!SecurityTokens::verify(key,"https://example.org/up",sid,"99999999999999999999.x",10000));
    std::cout << "security: 21 checks passed\n";
}
