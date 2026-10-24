// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_PASSWORD_HASH_H
#define UPLOADER_PASSWORD_HASH_H
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/crypto.h>
#include <string>
#include <cstring>
namespace PasswordHash {
static const int ITERATIONS = 600000;
inline std::string hex(const unsigned char *p, size_t n) {
    const char *digits="0123456789abcdef"; std::string out(n*2, '0');
    for(size_t i=0;i<n;++i) {out[2*i]=digits[p[i]>>4];out[2*i+1]=digits[p[i]&15];}return out;
}
inline bool unhex(const std::string& s, unsigned char *p, size_t n) {
    if(s.size()!=n*2)return false;
    for(size_t i=0;i<n*2;++i) {unsigned char c=s[i];int v=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
        if(v<0)return false;
        if(i%2)p[i/2]|=v;else p[i/2]=static_cast<unsigned char>(v<<4);}return true;
}
inline bool decode(const std::string& value, unsigned char *salt, unsigned char *digest) {
    const std::string prefix="pbkdf2-sha256$600000$";
    return value.size()==prefix.size()+32+1+64 && value.compare(0,prefix.size(),prefix)==0 &&
        value[prefix.size()+32]=='$' && unhex(value.substr(prefix.size(),32),salt,16) &&
        unhex(value.substr(prefix.size()+33),digest,32);
}
inline bool valid(const char *s) {unsigned char salt[16],digest[32];return *s==0 || decode(s,salt,digest);}
inline std::string make(const char *password) {
    size_t n=std::strlen(password);if(n==0)return "";if(n>127)throw "Password exceeds 127 bytes";
    unsigned char salt[16],digest[32];
    if(RAND_bytes(salt,16)!=1 || PKCS5_PBKDF2_HMAC(password,static_cast<int>(n),salt,16,ITERATIONS,EVP_sha256(),32,digest)!=1)
        throw "Password hashing failed";
    std::string value="pbkdf2-sha256$600000$"+hex(salt,16)+"$"+hex(digest,32);
    OPENSSL_cleanse(digest,sizeof(digest));return value;
}
inline bool verify(const char *stored,const char *password) {
    size_t n=std::strlen(password);if(n>127)return false;if(*stored==0)return n==0;
    unsigned char salt[16],expected[32],actual[32];if(!decode(stored,salt,expected))return false;
    if(PKCS5_PBKDF2_HMAC(password,static_cast<int>(n),salt,16,ITERATIONS,EVP_sha256(),32,actual)!=1)throw "Password verification failed";
    bool ok=CRYPTO_memcmp(actual,expected,32)==0;OPENSSL_cleanse(actual,sizeof(actual));return ok;
}
}
#endif
