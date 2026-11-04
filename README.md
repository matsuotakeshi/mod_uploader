# mod_uploader 3.2.0: altered FreeBSD / Enterprise Linux / Apache 2.4 version

Original software by Tetsuya Kimata: https://github.com/kimata/mod_uploader

This repository contains an altered version based on upstream commit
`31632a29138b18b7adbf533416a0ec660f1b07ac`. It is not an official upstream
release. Copyright and zlib license notices are retained in [COPYING](COPYING).
See [MODIFICATIONS](MODIFICATIONS) for attribution and modification notice.

The user reported successful operation on their FreeBSD / Apache setup
following the build correction. The Port has now built and passed stage, check-plist, stage-qa and package
on FreeBSD 15.1 amd64 / Clang 19.1.7 / Apache 2.4.69 (THUMBNAIL off).
Isolated real Apache HTTP/HTTPS, concurrent requests, migration and rollback tests
also pass; their coverage and limits are recorded in docs/validation.
Production package installation and exhaustive HTTP behavior remain unverified.
See the [dependency and poudriere report](docs/DEPENDENCY-PORT-VALIDATION-ja.md)
for the additional package validation and remaining dependency warnings.

## Enterprise Linux

Rocky Linux / AlmaLinux support includes GCC builds, optional ImageMagick 6/7
thumbnails, RPM packaging, root/subpath samples and SELinux setup instructions.
See [the Linux guide](docs/LINUX-ja.md) and [validation results](docs/LINUX-VALIDATION-ja.md).
The UI and version-4 storage format are shared with the FreeBSD version.

## Build (FreeBSD)

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
Downloads use attachments. Password metadata now uses version 4 and salted
PBKDF2-HMAC-SHA256 (600,000 iterations). Existing version 2/3 data requires an
offline, verified-backup-first migration; the new module refuses legacy data.
Signed, session-bound CSRF tokens protect Apache POST in addition to origin
checks. See [the migration and rollback guide](docs/SECURITY-MIGRATION-ja.md).
No production data is automatically migrated by installing or loading this module.

Validation logs are checked in under `docs/validation/`.

Port revision 6 supports VirtualHost root (`/`) and subpath (`/up`) deployments.
Base URLs with or without a trailing slash are normalized, and bundled templates
use canonical static-resource URLs. See [the root/subpath configuration guide](docs/ROOT-DEPLOYMENT-ja.md)
for static handlers, administration, TLS, migration and rollback, and
[the revision 6 validation report](docs/ROOT-VALIDATION-ja.md) for measured coverage.

Port revision 7 adds verified offline backup/restore and recovery tools, journaled
upload/eviction, bounded raster thumbnail processing, dependency/capacity audits,
and meaningful error HTTP statuses. See [the operations guide](docs/OPERATIONS-ja.md)
and [revision 7 validation](docs/OPERATIONS-VALIDATION-ja.md) before upgrading.

Port revision 8 declares Perl for the patch phase and supplies the FreeBSD
pkg-config search path for ImageMagick 7 thumbnail builds. The module source,
templates and password storage format are unchanged from revision 7.

管理画面はApacheでの独立した認証が必須です。Portの初期設定では閉鎖しています。IP別のパスワード処理回数と、プロセス間の同時実行数も制限します。設定・制限値は[セキュリティと移行手順](docs/SECURITY-MIGRATION-ja.md)を参照してください。

Revision 9 adds Enterprise Linux support and accounts for inherited glibc arena
reservations when limiting thumbnail children. Tighter administrator limits and
ImageMagick cache/decoder limits remain enforced. FreeBSD retains its absolute
address-space limit. The Port passes ImageMagick pkg-config paths at configure time.
