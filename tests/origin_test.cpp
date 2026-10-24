#include "../include/RequestOrigin.h"
#include <cassert>
#include <iostream>
int main() {
    using RequestOrigin::allowed;
    const char *base="https://example.org/up";
    assert(allowed(base,"https://example.org",NULL,"same-origin"));
    assert(allowed(base,NULL,"https://example.org/up/",NULL));
    assert(allowed(base,"https://EXAMPLE.ORG",NULL,NULL));
    assert(!allowed(base,NULL,NULL,"same-origin"));
    assert(!allowed(base,"null","https://example.org/up",NULL));
    assert(!allowed(base,"https://evil.org","https://example.org/up",NULL));
    assert(!allowed(base,"https://example.org",NULL,"cross-site"));
    assert(!allowed(base,NULL,"https://example.org.evil.org/up",NULL));
    assert(!allowed(base,NULL,"https://example.org@evil.org/up",NULL));
    assert(!allowed(base,NULL,"http://example.org/up",NULL));
    assert(!allowed(base,"https://example.org/",NULL,NULL));
    assert(!allowed(base,"https://example.org:443",NULL,NULL));
    assert(!allowed(base,NULL,"https:///up",NULL));
    assert(!allowed(base,NULL,"https://example.org\\evil/up",NULL));
    assert(!allowed(base,"https://example.org\n",NULL,NULL));
    assert(!allowed(NULL,"https://example.org",NULL,NULL));
    std::cout << "origin: 16 checks passed\n";
}
