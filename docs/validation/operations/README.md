# Revision 7 validation evidence

These logs were produced on 2026-11-03 in an isolated FreeBSD 15.1 amd64 directory.
`<test-root>` replaces the private temporary working path; trailing whitespace in
build logs is trimmed. Production configuration,
data, credentials, TLS private keys and test-session cookies are not included.

See [the Japanese validation report](../../OPERATIONS-VALIDATION-ja.md) for counts,
build variants, remaining warnings and untested operations. Successful tests do not
mean that the host's dependencies are free of known vulnerabilities.

`port-release.log` is the final default (THUMBNAIL off) Port validation. Earlier
failed build attempts are not included or counted as successes. `package-test.log`
uses the module and Python utilities extracted from the resulting pkg into a new
directory; it is not a system pkg-install/uninstall test.

`zip-build.log` includes configure/compiler output. Static-analysis diagnostic counts
in `static-im7.log` are separate from ordinary compiler warnings.

The archive structure test runs on Windows. Other assertion counts in the report
were obtained on FreeBSD. `validated-inputs.json` contains normalized SHA-256 values
for changed build/tool inputs. Port Python shebangs are normalized for comparison.
