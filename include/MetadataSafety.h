// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_METADATA_SAFETY_H
#define UPLOADER_METADATA_SAFETY_H
#include <cstring>
#include <cstddef>
namespace MetadataSafety {
template<size_t N> bool terminated(const char (&s)[N]) { return std::memchr(s, 0, N) != NULL; }
inline bool path_component(const char *s) {
    if (!*s || !std::strcmp(s,".") || !std::strcmp(s,"..")) return false;
    for (; *s; ++s) {
        unsigned char c = static_cast<unsigned char>(*s);
        if (c < 32 || c == 127 || std::strchr("/\\<>\"'&", c)) return false;
    }
    return true;
}
template<class H> bool same_identity(const H& a,const H& b) {
    return a.id==b.id && a.index==b.index && a.mtime==b.mtime && a.file_size==b.file_size &&
        std::strcmp(a.file_digest,b.file_digest)==0 && std::strcmp(a.download_pass,b.download_pass)==0 &&
        std::strcmp(a.remove_pass,b.remove_pass)==0;
}
template<class H> bool valid(const H& h) {
#define TERMINATED(f) if (!terminated(h.f)) return false
    TERMINATED(identifier); TERMINATED(version); TERMINATED(date); TERMINATED(ip_address);
    TERMINATED(file_name); TERMINATED(file_mime); TERMINATED(file_ext); TERMINATED(file_digest);
    TERMINATED(remove_pass); TERMINATED(download_pass); TERMINATED(comment);
#undef TERMINATED
    if ((reinterpret_cast<const unsigned char *>(&h.flags)[0] & ~3U) != 0) return false;
    if (!path_component(h.file_name) || !path_component(h.file_ext) ||
        std::strpbrk(h.file_ext,".") || std::strpbrk(h.comment,"<>") ||
        std::strpbrk(h.date,"<>\"'&") || std::strpbrk(h.ip_address,"<>\"'&") ||
        std::strpbrk(h.file_mime,"<>\"'&\r\n")) return false;
    if (std::strlen(h.file_digest) != 32) return false;
    for (const char *p=h.file_digest;*p;++p)
        if (!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='f')||(*p>='A'&&*p<='F'))) return false;
    return true;
}
}
#endif
