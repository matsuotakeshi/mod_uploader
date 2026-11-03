// SPDX-License-Identifier: Zlib
#include "HttpErrorStatus.h"
#include <cassert>
#include <cstdio>
#include <string>
int main() {
    const struct { const char *message; int status; } cases[] = {
        {MESSAGE_HANDLER_COMMAND_INVALID,404},{MESSAGE_LIST_ID_INVALID,404},
        {MESSAGE_DOWNLOAD_PASS_MISMATCH,403},{MESSAGE_REMOVE_PASS_MISMATCH,403},
        {MESSAGE_POST_INTERVAL_TOO_SHORT,429},{MESSAGE_DOWNLOAD_SESSION_LIMIT_EXCEEDED,503},
        {MESSAGE_RFC1867_FILE_SIZE_TOO_LARGE,413},{MESSAGE_RFC2822_TEXT_SIZE_TOO_LARGE,413},
        {MESSAGE_POST_FILE_NAME_INVALID,400},{MESSAGE_RFC1867_FORMAT_INVALID,400},
        {MESSAGE_FILE_WRITE_FAILED,500},{MESSAGE_DOWNLOAD_GZIP_NEEDED,406},
        {"Shared storage lock timed out; inspect owner",503},
        {"Storage recovery required; stop Apache",503},{"unexpected error",500}};
    for (size_t i=0;i<sizeof(cases)/sizeof(*cases);++i) {
        assert(HttpErrorStatus::get(cases[i].message)==cases[i].status);
        assert(HttpErrorStatus::get((std::string(cases[i].message)+" (source.cpp:10)").c_str())==cases[i].status);
    }
    assert(HttpErrorStatus::get(NULL)==500);
    assert(HttpErrorStatus::get((std::string(MESSAGE_LIST_ID_INVALID)+"-extra").c_str())==500);
    std::puts("http-status: 32 checks passed");
}
