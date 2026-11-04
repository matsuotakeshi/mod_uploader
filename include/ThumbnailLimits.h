// SPDX-License-Identifier: Zlib
// Altered mod_uploader: bounded thumbnail address space after fork.
#ifndef THUMBNAIL_LIMITS_H
#define THUMBNAIL_LIMITS_H
#ifndef WIN32
#include <cerrno>
#include <fcntl.h>
#include <limits>
#include <sys/resource.h>
#include <unistd.h>

namespace ThumbnailLimits {
static const rlim_t ADDRESS_BUDGET = 512UL * 1024 * 1024;

inline bool apply_address_space_limit()
{
    struct rlimit previous;
    if (getrlimit(RLIMIT_AS, &previous) != 0) return false;
    rlim_t ceiling = ADDRESS_BUDGET;
#ifdef __linux__
    // glibc's thread arenas reserve large address ranges in event/worker MPMs.
    // fork inherits those reservations. An absolute 512 MiB ceiling can be below
    // the existing VM size and reject even a 93-byte image mapping with ENOMEM.
    // Bound additional address space; ImageMagick separately bounds pixel caches.
    int fd = open("/proc/self/statm", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    char text[64];
    ssize_t count;
    do { count = read(fd, text, sizeof(text)); } while (count < 0 && errno == EINTR);
    close(fd);
    if (count <= 0) return false;
    const long page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) return false;
    rlim_t pages = 0;
    ssize_t pos = 0;
    for (; pos < count && text[pos] >= '0' && text[pos] <= '9'; ++pos) {
        const unsigned digit = static_cast<unsigned>(text[pos] - '0');
        if (pages > (std::numeric_limits<rlim_t>::max() - digit) / 10) return false;
        pages = pages * 10 + digit;
    }
    if (pos == 0 || pos == count || text[pos] != ' ' ||
        pages > (std::numeric_limits<rlim_t>::max() - ADDRESS_BUDGET) /
                    static_cast<rlim_t>(page_size)) return false;
    ceiling += pages * static_cast<rlim_t>(page_size);
#endif
    // Respect any tighter administrator-provided soft/hard ceiling.
    if (previous.rlim_cur != RLIM_INFINITY && ceiling > previous.rlim_cur)
        ceiling = previous.rlim_cur;
    if (previous.rlim_max != RLIM_INFINITY && ceiling > previous.rlim_max)
        ceiling = previous.rlim_max;
    struct rlimit limit = {ceiling, ceiling};
    return setrlimit(RLIMIT_AS, &limit) == 0;
}
}
#endif
#endif
