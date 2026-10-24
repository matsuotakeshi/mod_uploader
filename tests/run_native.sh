#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
testdir=$(mktemp -d)
trap 'rm -rf "$testdir"' EXIT HUP INT TERM
for name in safety buffer reader origin security throttle; do
    "${CXX:-c++}" -std=c++11 -pthread -Wall -Wextra -Werror \
        -Itests/native_stubs -Iinclude "tests/${name}_test.cpp" -lcrypto -o "$testdir/$name"
    "$testdir/$name"
done
