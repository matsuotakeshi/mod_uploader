# mod_uploader 3.2.0: altered FreeBSD / Apache 2.4 version

Original software by Tetsuya Kimata: https://github.com/kimata/mod_uploader

This repository contains an altered version based on upstream commit
`31632a29138b18b7adbf533416a0ec660f1b07ac`. It is not an official upstream
release. Copyright and zlib license notices are retained in [COPYING](COPYING).
See [MODIFICATIONS](MODIFICATIONS) for attribution and modification notice.

The user reported successful operation on their FreeBSD / Apache setup
following the build correction. Exact OS/compiler/server versions and
feature-by-feature test results were not supplied. Ports packaging,
poudriere, concurrency and complete HTTP acceptance tests remain unverified.

## Build

Install Apache 2.4 development tools, APR, GNU make, Perl and GNU libtool.
Use the paths appropriate to your FreeBSD installation:

```sh
./configure --with-apxs=/usr/local/sbin/apxs \
  --with-aprconf=/usr/local/bin/apr-1-config \
  --with-libtool=/usr/local/bin/libtool --with-writer=basic \
  CC=clang CXX=clang++
gmake LANG=ja_JP.eucJP apache-module
```

The Port candidate is in `ports/www/mod_uploader`. It downloads the pinned
original upstream source and applies the bundled patch. It does not fetch
this repository recursively or automatically enable the module.

## Tests and migration report

```sh
sh tests/run_native.sh
python3 tests/handler_test.py
```

Tests substitute APR/httpd interfaces where stated; they are not full
module integration tests. See [the Japanese migration report](docs/FREEBSD-ja.md)
for changes, security limitations, FreeBSD verification steps and layout details.
In particular, downloads now use attachments, password storage remains in
the legacy format, and CSRF checks are partial. Thumbnail decoding requires
an appropriate ImageMagick resource/coder policy.
