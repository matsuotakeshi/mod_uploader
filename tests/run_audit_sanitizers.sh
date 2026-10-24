#!/bin/sh
set -eu
build=$(realpath "$1")
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
review=$(mktemp -d)
trap 'rm -rf "$review"' EXIT HUP INT TERM
sources=""
for name in MultipartMessageParserBuffer BasicFileWriter FileWriter File TemporaryFile MessageDigest5 DirectoryCleaner Auxiliary SourceInfo UploadItemList; do
    if [ -f "$build/src/$name.cpp" ]; then sources="$sources $build/src/$name.cpp"; fi
done
${CXX:-c++} -std=c++11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -ffunction-sections -fdata-sections -I"$build/include" -I"$build/src" -I/usr/local/include/apr-1 \
    "$root/tests/audit_sanitizer.cpp" $sources -Wl,--gc-sections \
    -L/usr/local/lib -lapr-1 -laprutil-1 -lcrypto -o "$review/audit"
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$review/audit" "$review"
