# Validation evidence

The FreeBSD logs were captured on 2026-10-24 in an isolated user workspace.
They contain successful Port stage, check-plist, stage-qa and package runs,
compiler/library versions and native regression test results. No live Apache
configuration was changed, and the package was not installed.

Private workspace paths are replaced with <review-dir>. Some EUC-JP build
messages are decoded with replacement; diagnostic text and exit codes remain.
The package-info log includes SHA-256 hashes for the tested production patch
and origin helper, tying the run to those source bytes.

Port patch and helper hashes must match when claiming these results for a
source tree. Documentation-only changes after testing do not change the module.
