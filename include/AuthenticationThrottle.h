// SPDX-License-Identifier: Zlib
#ifndef UPLOADER_AUTHENTICATION_THROTTLE_H
#define UPLOADER_AUTHENTICATION_THROTTLE_H
#include <sys/file.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <openssl/sha.h>
#include <cstdint>
#include <ctime>
#include <cerrno>
#include <string>

// Fixed-size persistent state and kernel-held slots shared by all httpd workers.
// Hash bucket collisions conservatively share an IP budget; memory/disk use is bounded.
class AuthenticationThrottle {
public:
    static const unsigned LIMIT = 10, WINDOW = 60, CONCURRENT = 2, BUCKETS = 4096;
    AuthenticationThrottle(const char *directory, const char *ip, bool needed = true,
                           uint64_t now = static_cast<uint64_t>(std::time(NULL)))
        : slot_(-1), allowed_(!needed), retry_(1) {
        if (!needed) return;
        if (!ip || !*ip) return;
        const std::string prefix = std::string(directory) + "/.auth-";
        for (unsigned i = 0; i < CONCURRENT; ++i) {
            int fd = safe_open(prefix + "slot-" + char('0' + i));
            if (fd < 0) return;
            if (flock(fd, LOCK_EX | LOCK_NB) == 0) { slot_ = fd; break; }
            close(fd);
        }
        if (slot_ < 0) return;
        int state = safe_open(prefix + "attempts");
        if (state < 0) return;
        if (flock(state, LOCK_EX | LOCK_NB) != 0) { close(state); return; }
        struct stat st;
        const off_t size = static_cast<off_t>(BUCKETS * sizeof(Bucket));
        bool good = fstat(state, &st) == 0;
        if (good && st.st_size == 0) good = ftruncate(state, size) == 0;
        else if (good) good = st.st_size == size;
        unsigned char digest[SHA256_DIGEST_LENGTH];
        SHA256(reinterpret_cast<const unsigned char *>(ip), std::char_traits<char>::length(ip), digest);
        const off_t offset = ((static_cast<unsigned>(digest[0]) << 8 | digest[1]) % BUCKETS) * sizeof(Bucket);
        Bucket bucket = {0, 0};
        if (good) good = pread(state, &bucket, sizeof(bucket), offset) == sizeof(bucket);
        if (good && bucket.count <= LIMIT && now != UINT64_MAX) {
            if (bucket.start == 0 || (now >= bucket.start && now - bucket.start >= WINDOW)) {
                bucket.start = now; bucket.count = 0;
            }
            if (now >= bucket.start && bucket.count < LIMIT) {
                ++bucket.count;
                allowed_ = pwrite(state, &bucket, sizeof(bucket), offset) == sizeof(bucket);
            } else {
                retry_ = now < bucket.start ? WINDOW : static_cast<unsigned>(WINDOW - (now - bucket.start));
            }
        }
        // No passwords, raw IP addresses or tokens are written to state files.
        close(state);
        if (!allowed_) { close(slot_); slot_ = -1; }
    }
    ~AuthenticationThrottle() noexcept { if (slot_ >= 0) close(slot_); }
    bool allowed() const { return allowed_; }
    unsigned retry_after() const { return retry_; }
private:
    struct Bucket { uint64_t start, count; };
    static int safe_open(const std::string& path) {
        int fd = open(path.c_str(), O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK, 0600);
        if (fd < 0) return -1;
        struct stat st;
        if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) || st.st_uid != geteuid() ||
            (st.st_mode & 077) != 0 || st.st_nlink != 1) { close(fd); return -1; }
        return fd;
    }
    AuthenticationThrottle(const AuthenticationThrottle&) = delete;
    AuthenticationThrottle& operator=(const AuthenticationThrottle&) = delete;
    int slot_;
    bool allowed_;
    unsigned retry_;
};
#endif
