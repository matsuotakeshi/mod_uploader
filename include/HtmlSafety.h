// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_HTML_SAFETY_H
#define UPLOADER_HTML_SAFETY_H
#include <string>
namespace HtmlSafety {
inline std::string escape(const char *input) {
    std::string out;
    for (; *input; ++input) {
        switch (*input) {
        case '&': out += "&amp;"; break;
        case '<': out += "&lt;"; break;
        case '>': out += "&gt;"; break;
        case '"': out += "&quot;"; break;
        case 39: out += "&#39;"; break;
        default: out += *input;
        }
    }
    return out;
}
}
#endif
