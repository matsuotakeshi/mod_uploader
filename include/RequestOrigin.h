// SPDX-License-Identifier: Zlib
// Altered mod_uploader: require a verifiable browser source on Apache POST.
#ifndef REQUEST_ORIGIN_H
#define REQUEST_ORIGIN_H
#include <cstddef>
#include <cstring>
namespace RequestOrigin {
inline unsigned char lower(unsigned char c) {
    return c >= 'A' && c <= 'Z' ? static_cast<unsigned char>(c + ('a'-'A')) : c;
}
inline std::size_t length(const char *url) {
    if (url == NULL) return 0;
    std::size_t scheme = 0;
    if (std::strncmp(url, "https://", 8) == 0) scheme = 8;
    else if (std::strncmp(url, "http://", 7) == 0) scheme = 7;
    else return 0;
    std::size_t end = scheme;
    while (url[end] && url[end] != '/' && url[end] != '?' && url[end] != '#') {
        const unsigned char c = static_cast<unsigned char>(url[end]);
        if (c <= 32 || c >= 127 || c == '@' || c == '\\') return 0;
        ++end;
    }
    return end == scheme ? 0 : end;
}
inline bool matches(const char *base, const char *source, bool referer) {
    const std::size_t a = length(base), b = length(source);
    if (a == 0 || a != b || (!referer && source[b] != 0)) return false;
    for (std::size_t i = 0; i < a; ++i)
        if (lower(static_cast<unsigned char>(base[i])) !=
            lower(static_cast<unsigned char>(source[i]))) return false;
    return true;
}
inline bool allowed(const char *base, const char *origin,
                    const char *referer, const char *fetch_site) {
    if (fetch_site != NULL && std::strcmp(fetch_site, "cross-site") == 0) return false;
    // An invalid Origin must never fall back to a permissive Referer.
    if (origin != NULL) return matches(base, origin, false);
    return referer != NULL && matches(base, referer, true);
}
}
#endif
