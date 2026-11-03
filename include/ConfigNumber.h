// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_CONFIG_NUMBER_H
#define UPLOADER_CONFIG_NUMBER_H
#include <cstdint>
namespace ConfigNumber {
inline bool parse(const char *text, uint64_t maximum, uint64_t& number) {
    number=0;
    if (!text || !*text) return false;
    for (; *text; ++text) {
        if (*text<'0' || *text>'9') return false;
        const unsigned digit=static_cast<unsigned>(*text-'0');
        if (digit>maximum || number>(maximum-digit)/10) return false;
        number=number*10+digit;
    }
    return number!=0;
}
}
#endif
