// Altered mod_uploader port: bounded multipart helpers, independent of APR.
#ifndef UPLOAD_SAFETY_H
#define UPLOAD_SAFETY_H
#include <cstddef>
#include <cstring>
namespace UploadSafety {
inline const char *boundary(const char *data, std::size_t size,
                            const char *token, std::size_t length) {
    if (length > size || size - length < 6) return NULL;
    for (std::size_t i = 4; i <= size - length - 2; ++i) {
        if (std::memcmp(data+i-4, "\r\n--", 4) == 0 &&
            std::memcmp(data+i, token, length) == 0 &&
            (std::memcmp(data+i+length, "\r\n", 2) == 0 ||
             std::memcmp(data+i+length, "--", 2) == 0)) return data+i;
    }
    return NULL;
}
inline bool allowed(std::size_t current, std::size_t extra, std::size_t limit) {
    return current <= limit && extra <= limit-current;
}
}
#endif
