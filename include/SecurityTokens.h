// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_SECURITY_TOKENS_H
#define UPLOADER_SECURITY_TOKENS_H
#include "PasswordHash.h"
#include <openssl/hmac.h>
#include <ctime>
#include <cstdint>
namespace SecurityTokens {
static const uint64_t LIFETIME=7200;
inline std::string random_hex() {unsigned char value[32];if(RAND_bytes(value,32)!=1)throw "Random generator failed";return PasswordHash::hex(value,32);}
inline bool session_valid(const std::string& sid) {unsigned char value[32];return PasswordHash::unhex(sid,value,32);}
inline std::string sign(const std::string& key,const std::string& base,const std::string& sid,const std::string& stamp) {
    std::string input=base+"\n"+sid+"\n"+stamp;unsigned char mac[EVP_MAX_MD_SIZE];unsigned int size=0;
    if(key.size()!=32 || !HMAC(EVP_sha256(),key.data(),32,reinterpret_cast<const unsigned char*>(input.data()),input.size(),mac,&size) || size!=32)
        throw "Token signing failed";
    return PasswordHash::hex(mac,size);
}
inline std::string issue(const std::string& key,const std::string& base,const std::string& sid,uint64_t now) {
    if(!session_valid(sid))throw "Invalid session";
    std::string stamp=std::to_string(now);return stamp+"."+sign(key,base,sid,stamp);
}
inline bool verify(const std::string& key,const std::string& base,const std::string& sid,const std::string& token,uint64_t now) {
    if(!session_valid(sid))return false;
    size_t dot=token.find('.');
    if(dot==std::string::npos || dot==0 || dot>20 || token.size()!=dot+65)return false;
    uint64_t stamp=0;
    for(size_t i=0;i<dot;++i) {if(token[i]<'0'||token[i]>'9' || stamp>(UINT64_MAX-9)/10)return false;stamp=stamp*10+token[i]-'0';}
    if(std::to_string(stamp)!=token.substr(0,dot) || stamp>now || now-stamp>LIFETIME)return false;
    unsigned char mac[32];if(!PasswordHash::unhex(token.substr(dot+1),mac,32))return false;
    std::string expected=sign(key,base,sid,token.substr(0,dot));return CRYPTO_memcmp(expected.data(),token.data()+dot+1,64)==0;
}
}
#endif
