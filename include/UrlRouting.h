// SPDX-License-Identifier: Zlib
// Altered mod_uploader: one mount-relative route for root and subpath installs.
#ifndef UPLOADER_URL_ROUTING_H
#define UPLOADER_URL_ROUTING_H

#include <string>
#include <cstring>
#include "RequestOrigin.h"

namespace UrlRouting {
// Apache supplies a decoded path without the query. Never decode it a second time.
inline bool safe_path(const char *path) {
    if (!path || *path != '/') return false;
    const char *segment = path + 1;
    for (const char *p = segment; ; ++p) {
        const unsigned char c = static_cast<unsigned char>(*p);
        if (c && (c < 32 || c == 127 || std::strchr("\\%?#\"'<>\x20", c))) return false;
        if (c == '/' || c == 0) {
            const std::size_t size = static_cast<std::size_t>(p - segment);
            if ((size == 0 && c == '/') ||
                (size == 1 && segment[0] == '.') ||
                (size == 2 && segment[0] == '.' && segment[1] == '.')) return false;
            segment = p + 1;
        }
        if (c == 0) return true;
    }
}

inline std::string normalize_base(const char *base) {
    const std::size_t origin_size = RequestOrigin::length(base);
    if (!origin_size) throw "UploaderBaseUrl requires an absolute http(s) URL";
    std::string result(base);
    // Remove only trailing path separators; preserve the scheme's :// delimiter.
    while (result.size() > origin_size && result[result.size()-1] == '/') result.resize(result.size()-1);
    if (result.size() > origin_size && !safe_path(result.c_str()+origin_size))
        throw "UploaderBaseUrl has an invalid path (query, fragment or ambiguous path)";
    for (std::size_t i = 0; i < origin_size; ++i)
        if (std::strchr("\"'<>&", result[i])) throw "UploaderBaseUrl has an invalid authority";
    return result;
}

// Static resources retain their historical location beside the uploader mount.
inline std::string asset_base(const char *base) {
    std::string result(base);
    const std::size_t origin_size = RequestOrigin::length(base);
    if (result.size() > origin_size) result.resize(result.rfind('/'));
    return result;
}

enum Status { ROUTE, REDIRECT, COLLISION, INVALID };
inline Status resolve(const char *base, const char *uri, const char *path_info,
                      const char **argument) {
    *argument = NULL;
    if (!safe_path(uri)) return INVALID;
    const std::size_t origin_size = RequestOrigin::length(base);
    if (!origin_size) return INVALID;
    const char *mount = base + origin_size;
    const std::size_t mount_size = std::strlen(mount);
    if (std::strncmp(uri, mount, mount_size) != 0 ||
        (mount_size && uri[mount_size] && uri[mount_size] != '/')) return INVALID;
    *argument = uri + mount_size;
    if (**argument == 0) return REDIRECT; // /up -> /up/; root always has '/'.
    // Preserve the historical physical-directory collision check for subpaths.
    // The VirtualHost's DocumentRoot is necessarily a directory at the root mount.
    if (mount_size && (!path_info || !*path_info) && uri[std::strlen(uri)-1] == '/')
        return COLLISION;
    return ROUTE;
}
}
#endif
