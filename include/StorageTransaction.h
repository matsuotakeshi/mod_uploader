// SPDX-License-Identifier: Zlib
// Altered source: durable staging and reversible eviction under the manager lock.
#ifndef UPLOADER_STORAGE_TRANSACTION_H
#define UPLOADER_STORAGE_TRANSACTION_H
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#ifndef UPLOADER_TXN_POINT
#define UPLOADER_TXN_POINT(name) do {} while (0)
#endif

class StorageTransaction {
    struct Operation { char kind; std::string path; };
    std::string directory_;
    std::vector<Operation> operations_;
    int journal_;
    bool committed_;
    static std::string parent(const std::string& p) { return p.substr(0, p.rfind('/')); }
    static void fail() { throw "Storage transaction failed; stop Apache and inspect the recovery journal"; }
    static void write_all(int fd, const void *data, size_t size) {
        const char *p = static_cast<const char *>(data);
        while (size) {
            ssize_t count = ::write(fd, p, size);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) fail();
            p += count; size -= static_cast<size_t>(count);
        }
    }
    static bool exists(const std::string& path) {
        struct stat st;
        if (lstat(path.c_str(), &st) == 0) {
            if (!S_ISREG(st.st_mode) || st.st_nlink != 1) fail();
            return true;
        }
        if (errno != ENOENT) fail();
        return false;
    }
    static void erase(const std::string& path) {
        if (!exists(path)) return;
        if (unlink(path.c_str()) != 0) fail();
        sync_directory(parent(path));
    }
    void record(char kind, const std::string& path) {
        if (path.empty() || path[0] != '/' || path.find('\n') != std::string::npos) fail();
        for (size_t i = 0; i < operations_.size(); ++i)
            if (operations_[i].path == path) fail();
        // Check real directory, and reserve sidecar names before recording any mutation.
        sync_directory(parent(path));
        if (exists(path + ".uploader-new") || exists(path + ".uploader-old")) fail();
        if ((kind == 'C' || kind == 'P') && exists(path)) fail();
        static const char hex[] = "0123456789abcdef";
        std::string row; row += kind; row += ' ';
        for (size_t i = 0; i < path.size(); ++i) {
            unsigned char c = static_cast<unsigned char>(path[i]);
            row += hex[c >> 4]; row += hex[c & 15];
        }
        row += '\n';
        Operation operation = {kind, path}; operations_.push_back(operation);
        write_all(journal_, row.data(), row.size());
        if (fsync(journal_) != 0) fail();
        UPLOADER_TXN_POINT("record");
    }
    void finish_cleanup() {
        for (size_t i = 0; i < operations_.size(); ++i) {
            if (operations_[i].kind == 'P') erase(operations_[i].path);
            erase(operations_[i].path + ".uploader-old");
            erase(operations_[i].path + ".uploader-new");
        }
        if (journal_ >= 0) { close(journal_); journal_ = -1; }
        // Keep the commit marker until the plan is gone: cleanup is idempotent.
        erase(directory_ + "/commit-ready");
        erase(directory_ + "/plan");
        erase(directory_ + "/COMMITTED");
        if (rmdir(directory_.c_str()) != 0) fail();
        sync_directory(parent(directory_));
    }
    void rollback() {
        for (size_t i = operations_.size(); i > 0; --i) {
            const Operation& op = operations_[i-1];
            if (op.kind == 'P') { erase(op.path); }
            else if (op.kind == 'C') {
                erase(op.path); erase(op.path + ".uploader-new");
            } else if (exists(op.path + ".uploader-old")) {
                if (exists(op.path)) fail();
                if (rename((op.path + ".uploader-old").c_str(), op.path.c_str()) != 0) fail();
                sync_directory(parent(op.path));
            }
        }
        finish_cleanup();
    }
public:
    static void sync_directory(const std::string& path) {
        int fd = open(path.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0) fail();
        int status = fsync(fd); close(fd);
        if (status != 0) fail();
    }
    static void require_clean(const char *root) {
        struct stat st; const std::string path = std::string(root) + "/.storage-transaction";
        if (lstat(path.c_str(), &st) == 0 || errno != ENOENT)
            throw "Storage recovery required; stop Apache and run storage_recover.py";
    }
    explicit StorageTransaction(const char *root)
        : directory_(std::string(root) + "/.storage-transaction"), journal_(-1), committed_(false) {
        require_clean(root);
        if (mkdir(directory_.c_str(), 0700) != 0) fail();
        try {
            sync_directory(root);
            journal_ = open((directory_ + "/plan").c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
            if (journal_ < 0) fail();
            const char magic[] = "UPLOADER-TXN-1\n";
            write_all(journal_, magic, sizeof(magic)-1);
            if (fsync(journal_) != 0) fail();
            sync_directory(directory_);
            UPLOADER_TXN_POINT("begin");
        } catch (...) { if (journal_ >= 0) close(journal_); throw; }
    }
    ~StorageTransaction() noexcept {
        try { if (!committed_) rollback(); }
        catch (...) { std::fprintf(stderr, "mod_uploader: storage journal retained; offline recovery required\n"); }
        if (journal_ >= 0) close(journal_);
    }
    void create_bytes(const char *target, const void *data, size_t size) {
        record('C', target);
        const std::string stage = std::string(target) + ".uploader-new";
        int fd = open(stage.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
        if (fd < 0) fail();
        try {
            write_all(fd, data, size);
            if (fsync(fd) != 0) fail();
            if (close(fd) != 0) { fd = -1; fail(); } fd = -1;
            sync_directory(parent(stage)); UPLOADER_TXN_POINT("staged");
        } catch (...) { if (fd >= 0) close(fd); throw; }
    }
    void create_file(const char *target, const char *source) {
        record('C', target);
        const std::string stage = std::string(target) + ".uploader-new";
        int input = open(source, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
        int output = -1;
        try {
            struct stat st;
            if (input < 0 || fstat(input, &st) != 0 || !S_ISREG(st.st_mode) || st.st_nlink != 1) fail();
            output = open(stage.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
            if (output < 0) fail();
            char buffer[65536];
            for (;;) {
                ssize_t count = read(input, buffer, sizeof(buffer));
                if (count < 0 && errno == EINTR) continue;
                if (count < 0) fail();
                if (count == 0) break;
                write_all(output, buffer, static_cast<size_t>(count));
            }
            if (fsync(output) != 0) fail();
            if (close(output) != 0) { output = -1; fail(); } output = -1;
            close(input); input = -1;
            sync_directory(parent(stage)); UPLOADER_TXN_POINT("staged");
        } catch (...) { if (input >= 0) close(input); if (output >= 0) close(output); throw; }
    }
    void remove_file(const char *target) {
        if (exists(target)) record('D', target);
    }
    void temporary_file(const char *target) { record('P', target); }
    void commit() {
        for (size_t i = 0; i < operations_.size(); ++i) {
            const Operation& op = operations_[i];
            if (op.kind == 'P') continue;
            if (op.kind == 'D') {
                if (rename(op.path.c_str(), (op.path + ".uploader-old").c_str()) != 0) fail();
            } else {
                if (exists(op.path)) fail();
                if (rename((op.path + ".uploader-new").c_str(), op.path.c_str()) != 0) fail();
            }
            sync_directory(parent(op.path)); UPLOADER_TXN_POINT("applied");
        }
        int fd = open((directory_ + "/commit-ready").c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
        if (fd < 0) fail();
        int result = fsync(fd); close(fd);
        if (result != 0) fail();
        if (rename((directory_ + "/commit-ready").c_str(), (directory_ + "/COMMITTED").c_str()) != 0) fail();
        committed_ = true; UPLOADER_TXN_POINT("committed");
        // A cleanup failure must never roll back a committed on-disk transaction.
        try { sync_directory(directory_); finish_cleanup(); }
        catch (...) { std::fprintf(stderr, "mod_uploader: committed storage cleanup pending; offline recovery required\n"); }
    }
    StorageTransaction(const StorageTransaction&) = delete;
    StorageTransaction& operator=(const StorageTransaction&) = delete;
};
#endif
