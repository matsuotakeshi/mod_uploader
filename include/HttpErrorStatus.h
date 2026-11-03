// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_HTTP_ERROR_STATUS_H
#define UPLOADER_HTTP_ERROR_STATUS_H
#include <cstring>
#include "Message.h"
namespace HttpErrorStatus {
inline bool matches(const char *message, const char *code) {
    const size_t length = std::strlen(code);
    return std::strncmp(message, code, length) == 0 && (message[length] == '\0' || message[length] == ' ');
}
inline int get(const char *message) {
    if (!message) return 500;
    if (matches(message, MESSAGE_HANDLER_COMMAND_INVALID) || matches(message, MESSAGE_LIST_ID_INVALID)) return 404;
    if (matches(message, MESSAGE_DOWNLOAD_PASS_MISMATCH) || matches(message, MESSAGE_REMOVE_PASS_MISMATCH)) return 403;
    if (matches(message, MESSAGE_POST_INTERVAL_TOO_SHORT)) return 429;
    if (matches(message, MESSAGE_DOWNLOAD_SESSION_LIMIT_EXCEEDED) || std::strstr(message, "Shared storage lock timed out") ||
        std::strstr(message, "Storage recovery required") || std::strstr(message, "Storage transaction failed")) return 503;
    const char *large[] = {MESSAGE_RFC1867_DATA_SIZE_TOO_LARGE, MESSAGE_RFC1867_FILE_SIZE_TOO_LARGE,
        MESSAGE_RFC1867_TEXT_SIZE_TOO_LARGE, MESSAGE_RFC1867_ITEM_COUNT_EXCEEDED,
        MESSAGE_RFC2822_FILE_SIZE_TOO_LARGE, MESSAGE_RFC2822_TEXT_SIZE_TOO_LARGE, MESSAGE_RFC2822_ITEM_COUNT_EXCEEDED};
    for (size_t i=0; i<sizeof(large)/sizeof(*large); ++i) if (matches(message, large[i])) return 413;
    const char *invalid[] = {MESSAGE_ARGUMENT_INVALID, MESSAGE_FILE_EXT_INVALID, MESSAGE_FILE_MIME_INVALID,
        MESSAGE_POST_DATA_INVALID, MESSAGE_POST_FILE_EXT_INVALID, MESSAGE_POST_FILE_MIME_INVALID,
        MESSAGE_POST_FILE_NAME_INVALID, MESSAGE_POST_IMAGE_SIZE_INVALID, MESSAGE_RFC1867_CONTENT_TYPE_INVALID,
        MESSAGE_RFC1867_FORMAT_INVALID, MESSAGE_RFC2822_CONTENT_TYPE_INVALID, MESSAGE_RFC2822_FORMAT_INVALID,
        MESSAGE_RFC2822_HEADER_INVALID, MESSAGE_HANDLER_PATH_INFO_TOO_LONG, MESSAGE_ICONV_ENCODING_INVALID,
        MESSAGE_POST_COMMENT_EMPTY, MESSAGE_POST_COMMENT_TOO_LONG, MESSAGE_POST_FILE_EXT_EMPTY,
        MESSAGE_POST_FILE_EXT_TOO_LONG, MESSAGE_POST_FILE_MIME_EMPTY, MESSAGE_POST_FILE_MIME_TOO_LONG,
        MESSAGE_POST_FILE_NAME_EMPTY, MESSAGE_POST_FILE_NAME_TOO_LONG, MESSAGE_POST_FILE_SIZE_ZERO,
        MESSAGE_POST_REMOVE_PASS_TOO_LONG, MESSAGE_POST_DOWNLOAD_PASS_TOO_LONG,
        MESSAGE_RFC1867_CONTENT_SIZE_ZERO, MESSAGE_RFC2822_CONTENT_SIZE_ZERO};
    for (size_t i=0; i<sizeof(invalid)/sizeof(*invalid); ++i) if (matches(message, invalid[i])) return 400;
    if (matches(message, MESSAGE_DOWNLOAD_GZIP_NEEDED)) return 406;
    if (matches(message, "Password exceeds 127 bytes")) return 400;
    return 500;
}
}
#endif
