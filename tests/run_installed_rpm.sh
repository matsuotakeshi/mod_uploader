#!/bin/sh
# SPDX-License-Identifier: Zlib
# Validate installed RPM binaries, templates, assets and operational tools.
set -eu
test "$(id -u)" != 0 || { echo 'Run as a non-root test user' >&2; exit 1; }
work=$(realpath "$1")
case "${2:-off}" in on) thumb_arg=--thumbnail ;; off) thumb_arg= ;; *) exit 2 ;; esac
source=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
rpm -q mod_uploader
adapter=$(mktemp -d "$work/installed-rpm-XXXXXX")
mkdir "$adapter/src" "$adapter/logs"
ln -s "$("${APXS:-apxs}" -q LIBEXECDIR)/mod_uploader.so" "$adapter/src/mod_uploader.so"
ln -s /usr/libexec/mod_uploader/password_tool "$adapter/src/password_tool"
for dir in tmpl img css js; do cp -R "/usr/share/mod_uploader/$dir" "$adapter/"; done
# The source regression suite also checks the legacy SWF static-handler exception.
# Flash assets are intentionally not shipped in the RPM; this is only a fixture.
cp -R "$source/swf" "$adapter/"
python3 "$source/tests/root_http_test.py" --build-root "$adapter" --workdir "$work" $thumb_arg > "$adapter/logs/root_http.log" 2>&1
python3 "$source/tests/operations_http_test.py" --build-root "$adapter" --workdir "$work" --tools-root /usr/libexec/mod_uploader $thumb_arg > "$adapter/logs/operations_http.log" 2>&1
python3 "$source/tests/root_sample_test.py" --build-root "$adapter" --workdir "$work" --samples-dir /etc/mod_uploader > "$adapter/logs/samples.log" 2>&1
tail -n 1 "$adapter/logs/root_http.log"
tail -n 1 "$adapter/logs/operations_http.log"
tail -n 1 "$adapter/logs/samples.log"
printf 'Installed RPM tests passed; logs: %s/logs\n' "$adapter"
