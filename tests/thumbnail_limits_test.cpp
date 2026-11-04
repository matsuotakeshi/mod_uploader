// SPDX-License-Identifier: Zlib
#include "ThumbnailLimits.h"
#include <cassert>
#include <cstdio>
#include <sys/mman.h>
#include <sys/wait.h>

int main()
{
    unsigned checks = 0;
    for (int restricted = 0; restricted != 2; ++restricted) {
        const pid_t child = fork();
        assert(child >= 0);
        if (child == 0) {
            const rlim_t tighter = 384UL * 1024 * 1024;
            if (restricted) {
                struct rlimit limit = {tighter, tighter};
                assert(setrlimit(RLIMIT_AS, &limit) == 0);
            }
#ifdef __linux__
            if (!restricted) {
                // Reproduce inherited glibc arena reservations without using RAM.
                assert(mmap(NULL, 1024UL * 1024 * 1024, PROT_NONE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) != MAP_FAILED);
            }
#endif
            assert(ThumbnailLimits::apply_address_space_limit());
            struct rlimit limit;
            assert(getrlimit(RLIMIT_AS, &limit) == 0);
            assert(limit.rlim_cur == limit.rlim_max && limit.rlim_cur != RLIM_INFINITY);
            if (restricted) assert(limit.rlim_cur == tighter);
            void *small = mmap(NULL, 4096, PROT_READ | PROT_WRITE,
                               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
            assert(small != MAP_FAILED);
            static_cast<char *>(small)[0] = 1;
            assert(munmap(small, 4096) == 0);
            // A single reservation greater than the remaining budget must fail.
            assert(mmap(NULL, ThumbnailLimits::ADDRESS_BUDGET + 64UL * 1024 * 1024,
                        PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED);
            _exit(0);
        }
        int status = 0;
        assert(waitpid(child, &status, 0) == child);
        assert(WIFEXITED(status) && WEXITSTATUS(status) == 0);
        ++checks;
    }
    std::printf("thumbnail-limits: %u process scenarios passed (inherited VM, stricter limit)\n", checks);
}
