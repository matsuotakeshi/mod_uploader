#!/bin/sh
# SPDX-License-Identifier: Zlib
# Run as an ordinary user: permission-failure checks must not bypass DAC.
set -eu
if [ "$(id -u)" = 0 ]; then
    echo "Run integration tests as a non-root user." >&2
    exit 1
fi
build=$(realpath "$1")
work=$(realpath "$2")
thumbnail=${3:-off}
case "$thumbnail" in on) thumb_arg=--thumbnail ;; off) thumb_arg= ;; *) exit 2 ;; esac
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
mkdir -p "$work/logs"
cd "$root"
run_test() {
    name=$1; shift
    if "$@" > "$work/logs/$name.log" 2>&1; then
        printf '%s: PASS\n' "$name"
        tail -n 1 "$work/logs/$name.log"
    else
        printf '%s: FAIL (see %s)\n' "$name" "$work/logs/$name.log"
        tail -n 20 "$work/logs/$name.log"
        exit 1
    fi
}
run_test native sh tests/run_native.sh
run_test handler python3 tests/handler_test.py
run_test storage python3 tests/storage_test.py --workdir "$work"
run_test migration python3 tests/migration_test.py --tool "$build/src/password_tool" --workdir "$work"
for name in security_http security_https hardening_http audit_http; do
    run_test "$name" python3 "tests/${name}_test.py" --build-root "$build" --workdir "$work"
done
run_test root_http python3 tests/root_http_test.py --build-root "$build" --workdir "$work" $thumb_arg
run_test operations_http python3 tests/operations_http_test.py --build-root "$build" --workdir "$work" $thumb_arg
run_test freebsd_samples python3 tests/root_sample_test.py --build-root "$build" --workdir "$work"
run_test linux_samples python3 tests/root_sample_test.py --build-root "$build" --workdir "$work" --samples-dir "$root/packaging/rpm"
