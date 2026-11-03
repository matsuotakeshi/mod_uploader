// SPDX-License-Identifier: Zlib
#include "ConfigNumber.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
int main() {
    uint64_t n;
    assert(ConfigNumber::parse("1024",INT64_MAX/1024,n)&&n==1024);
    assert(ConfigNumber::parse("9007199254740991",INT64_MAX/1024,n)&&n==9007199254740991ULL);
    assert(ConfigNumber::parse("1000000",1000000,n)&&n==1000000);
    for(const char *bad : {"", "0", "-1", "+1", " 1", "1K", "1 ", "1000001", "999999999999999999999999"})
        assert(!ConfigNumber::parse(bad,1000000,n));
    assert(!ConfigNumber::parse("9007199254740992",INT64_MAX/1024,n));
    assert(!ConfigNumber::parse(NULL,1000000,n));
    std::puts("config-number: 14 checks passed");
}
