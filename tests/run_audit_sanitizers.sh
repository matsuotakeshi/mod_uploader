#!/bin/sh
set -eu
build=$(realpath "$1")
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
review=$(mktemp -d)
trap 'rm -rf "$review"' EXIT HUP INT TERM
aprconf=${APR_CONFIG:-apr-1-config}
apuconf=${APU_CONFIG:-apu-1-config}
sources=""
for name in MultipartMessageParserBuffer BasicFileWriter FileWriter File TemporaryFile MessageDigest5 DirectoryCleaner Auxiliary SourceInfo UploadItemList; do
    if [ -f "$build/src/$name.cpp" ]; then sources="$sources $build/src/$name.cpp"; fi
done
${CXX:-c++} -std=c++11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
    -ffunction-sections -fdata-sections -I"$build/include" -I"$build/src" $("$aprconf" --includes) $("$apuconf" --includes) \
    "$root/tests/audit_sanitizer.cpp" $sources -Wl,--gc-sections \
    $("$apuconf" --link-ld --libs) $("$aprconf" --link-ld --libs) -lcrypto -o "$review/audit"
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$review/audit" "$review"
