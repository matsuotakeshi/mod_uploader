// SPDX-License-Identifier: Zlib
#include "UrlRouting.h"
#include <cassert>
#include <cstdio>
#include <string>

int main() {
    unsigned checks = 0;
    const char *argument;
    struct Base { const char *input; const char *base; const char *assets; } bases[] = {
        {"https://example.org/", "https://example.org", "https://example.org"},
        {"https://example.org", "https://example.org", "https://example.org"},
        {"http://example.org/up", "http://example.org/up", "http://example.org"},
        {"http://example.org/up/", "http://example.org/up", "http://example.org"},
        {"http://127.0.0.1:8080/board/up///", "http://127.0.0.1:8080/board/up", "http://127.0.0.1:8080/board"},
        {"https://[::1]:8443/", "https://[::1]:8443", "https://[::1]:8443"}
    };
    for (const Base& b : bases) {
        assert(UrlRouting::normalize_base(b.input) == b.base); ++checks;
        assert(UrlRouting::asset_base(b.base) == b.assets); ++checks;
    }
    const char *bad_bases[] = {NULL, "", "/up", "https://", "https:///up", "javascript:alert(1)",
        "https://x/up?y", "https://x/up#y", "https://x/../up", "https://x/a//b", "https://x/%2f", "https://x/<up", "https://x\n/up", "https://a@x/up"};
    for (const char *b : bad_bases) {
        bool failed=false; try {UrlRouting::normalize_base(b);} catch (const char *) {failed=true;}
        assert(failed); ++checks;
    }
    const char *routes[] = {"/", "/index", "/index/", "/rss/", "/upload/", "/download/123.txt", "/admin/", "/thumbnail/view/123.gif"};
    for (const char *uri : routes) {
        assert(UrlRouting::resolve("https://example.org", uri, "", &argument) == UrlRouting::ROUTE);
        assert(std::string(argument)==uri); ++checks;
        std::string sub = std::string("/up")+uri;
        assert(UrlRouting::resolve("https://example.org/up", sub.c_str(), uri, &argument) == UrlRouting::ROUTE);
        assert(std::string(argument)==uri); ++checks;
    }
    assert(UrlRouting::resolve("https://x/up", "/up", "", &argument)==UrlRouting::REDIRECT); ++checks;
    assert(UrlRouting::resolve("https://x/up", "/up/", "", &argument)==UrlRouting::COLLISION); ++checks;
    assert(UrlRouting::resolve("https://x/up", "/up/", NULL, &argument)==UrlRouting::COLLISION); ++checks;
    assert(UrlRouting::resolve("https://x", "/", NULL, &argument)==UrlRouting::ROUTE); ++checks;
    assert(UrlRouting::resolve("https://x/up", "/upper/admin", "", &argument)==UrlRouting::INVALID); ++checks;
    assert(UrlRouting::resolve("https://x/up", "/u", "", &argument)==UrlRouting::INVALID); ++checks;
    const char *bad_paths[] = {NULL, "", "index", "//index", "/a//b", "/../admin", "/./admin", "/a/..", "/a/.", "/%2e%2e/admin", "/a\\b", "/a\r\nb", "/?q", "/#x"};
    for (const char *uri : bad_paths) {
        assert(UrlRouting::resolve("https://x", uri, "", &argument)==UrlRouting::INVALID); ++checks;
    }
    std::printf("routing: %u checks passed (base URLs, root/subpath routes, collision and invalid paths)\n", checks);
}
