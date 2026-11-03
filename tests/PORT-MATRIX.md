# FreeBSD Port validation matrix

Use a separate build host/jail and storage, never a running uploader's data.
The results actually obtained are recorded in `docs/OPERATIONS-VALIDATION-ja.md`
and `docs/DEPENDENCY-PORT-VALIDATION-ja.md` (poudriere, both thumbnail options).

For a current Ports tree, with dependencies already available:

```sh
cd ports/www/mod_uploader
make BATCH=yes MAKE_JOBS_NUMBER=2 WRKDIRPREFIX=/private/port-test/build \
  DISTDIR=/private/port-test/distfiles PACKAGES=/private/port-test/packages \
  stage check-plist stage-qa package
```

Use a **different new** WRKDIRPREFIX and PACKAGES directory for THUMBNAIL:

```sh
make BATCH=yes OPTIONS_SET=THUMBNAIL MAKE_JOBS_NUMBER=2 \
  WRKDIRPREFIX=/private/port-test-im7/build \
  DISTDIR=/private/port-test-im7/distfiles PACKAGES=/private/port-test-im7/packages \
  stage check-plist stage-qa package
```

Do not use `NO_DEPENDS` for the release validation. Verify package dependencies and
run `pkg audit` before installing in a disposable jail. Check the loaded ImageMagick
libraries with `ldd`, not only the command-line program's version.

With a separately administered poudriere host, create/select a FreeBSD amd64 jail
and current Ports tree, put this Port in the test tree, and run:

```sh
poudriere testport -j uploader151 -p uploader -o www/mod_uploader
```

Repeat in separately named poudriere option sets for THUMBNAIL off/on. Provisioning
the jail, installing poudriere, and adjusting its options require administrator
access. The command above is a procedure, not evidence that a jail test was run.

For isolated configuration and official binary dependencies, the additional
validation used `poudriere -e /private/poudriere-etc testport -j uploader151
-p uploaderq4 -z thumb -b quarterly -J 1 -I -o www/mod_uploader`.
Set `www_mod_uploader_SET=THUMBNAIL` in `thumb-make.conf`; use a separate set with
`www_mod_uploader_UNSET=THUMBNAIL` for the default build. Inspect each phase log
and verify the target package exists: the tested poudriere version returned zero
with `-I` even after a failed target build and failed interactive installation.

`-I` retains a jail with the installed package for HTTP testing. Run those tests
as an unprivileged user; running as root invalidates permission-failure checks.
Use an adapter pointing at the installed module, password tool, templates and
static assets. The existing root HTTP test also expects a SWF fixture; the Port
does not package SWF. Providing the source fixture tests static routing only,
not a packaged SWF or browser Flash execution. Stop only the test jail afterward
with the matching `poudriere -e ... jail -k -j ... -p ... -z ...` arguments.

For each built module, run loopback tests with disposable directories:

```sh
python3 tests/root_http_test.py --build-root /private/built-source --workdir /private/test-results
python3 tests/operations_http_test.py --build-root /private/built-source --workdir /private/test-results
```

Add `--thumbnail` to both for an ImageMagick build. For a private ImageMagick prefix,
set `LD_LIBRARY_PATH` only for the test processes and set `MAGICK_CONVERT` to its
`bin/magick`. Such a source build verifies API/runtime compatibility, not a normal
system package installation. Exercise the installed backup tools as well as the
source tools. Keep the package, build log, check-plist/stage-qa output and dependency
audit with the report.

For an already built, trusted package, extract it into a new test directory (without
installing it). Point a test build adapter's `src/mod_uploader.so` and
`src/password_tool` at its extracted binaries, and `tmpl` at its extracted templates.
Then use the packaged Python scripts, not source copies:

```sh
python3 tests/operations_http_test.py --build-root /private/package-adapter \
  --tools-root /private/package-extracted/usr/local/libexec/mod_uploader \
  --workdir /private/test-results
```

Use `DEVELOPER=yes` for release validation, and inspect all stage-qa text even when
make exits successfully. Package extraction does not test pkg install/deinstall or
root ownership handling in a clean jail.
