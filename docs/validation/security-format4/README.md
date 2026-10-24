# Password-format-4 and CSRF validation

FreeBSD 15.1-RELEASE amd64, Clang 19.1.7, Apache 2.4.69, THUMBNAIL off.
All runs used isolated user-owned storage and separate loopback Apache
processes; production storage and the existing Apache were not changed.

- stage-final.log: successful Port build/staging, including the native converter.
- security-results.log: successful check-plist, stage-qa and package.
- security-repackage.log: description-only package metadata refresh.
- security-package-info.log: environment, package SHA-256, source patch/converter hashes.
- security-native.log: C++ core and mock-API regression tests.
- migration-final.log: 38 offline conversion/backup/failure/restore checks.
- migration-python311.log: the same checks under the package runtime Python.
- http-security-final.log: 44 real HTTP checks, including previous-module rollback.
- https-security-final.log: 6 real TLS checks with a verified local test certificate.
- security-source-hashes.log: exact source bytes transferred to and used by the test host.
- installed-migration-help.log: staged installed script executes with its Python shebang.

Workspace paths are redacted as <review-dir>. Build ANSI escape sequences
are removed, and undecodable legacy EUC-JP build text is replaced when
converting logs to UTF-8. No actual site data or backup is published.
