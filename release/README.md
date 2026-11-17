# Package utilities

These original MIT tools build and inspect archives without committing, publishing, activating services, or changing reference clients.

| File | Purpose |
| --- | --- |
| `artifacts.py` | Allowlisted source snapshots, deterministic archives, safe extraction, source identity, native builds, and installed inventories. |
| `source-files.txt` | Explicit source archive inputs; excludes private/generated state and obsolete collateral. |
| `local.py` | Isolated reproducible builds and verification of saved local package sets. |
| `runtime.py` | Clean packaged-runtime checks without a compiler/build tree. |
| `audit_binary.py` | Compiler/header/startup/archive and shared-library inspection for component notices. |
| `macos.py` | Native ARM64 builds from an exact source snapshot, pre-signing reproducibility, Developer ID signing, ZIP verification, and separate Apple notarization receipts. |
| `windows.py` | Native x64 two-root builds, complete PE reproducibility, source-bound unsigned ZIPs, and Microsoft compiler/SDK input inventories. |
| `checks.py` | Archive, mode, identity, reproducibility, and payload-boundary regressions. |
| `runbook.py` | Generate or check the installed text guide from the operating and scenario guides. |
| `build.Dockerfile`, `runtime.Dockerfile` | Separate build/runtime environments. |

Run `python3 release/checks.py` for helper regressions. Invoke each utility with `--help` for its arguments. Use new output directories and exact source/payload identities; never overwrite accepted/public artifacts. No ignored directory, reference repository, tool image, raw capture, or credential belongs in a source archive.

`macos.py` uses the `macos-arm64-local-controls-v2` profile with manifest schema `4`. Its archive includes the native executable, current helpers, macOS standalone guide, original MIT license, component notices, and retained LLVM legal text. It excludes the Linux service unit. Existing GNU/Linux schemas and validators remain distinct. An explicit certificate fingerprint and team are required for `build`; `verify`, `notarize`, and `status` require the expected `--source-snapshot` digest. The notarization commands use an existing Keychain profile without accepting passwords as arguments. The retained canonical source record binds original payload files to that snapshot; external legal text has its own origin, terms, and hash rather than an MIT authorship label.

`notarize` checks credential access before reserving an upload attempt. Once submission starts, it retains a request marker even if the result is uncertain. Inspect the retained submission and Apple account history before resolving an interrupted attempt; do not delete its marker to retry blindly. `status` records Apple's response separately from native runtime qualification and does not change the archive or its manifest.

The macOS builder compares complete linker-produced files from two independent roots before Developer ID signing. Secure timestamps make publisher signatures nondeterministic, so final signed bytes receive their own hashes, archive identity, and qualification. Diagnostic link-map generation must reproduce the same pre-signing executable. Compiler/SDK header hashes and external system libraries are retained for provenance review. Notarization acceptance is recorded separately from native package qualification and never implies release publication or hosted CI.

`cmake/version.cmake` is the application version authority. An empty prerelease field produces a final version without a trailing hyphen. Source archives, binary archive names, manifests, and executable `--version` output must agree with it. Saved-input verification defaults to that version; `local.py verify` and `artifacts.py repack-source` accept `--expected-version` to select a different saved input explicitly. Verification never relabels the saved files or grants qualification acceptance.

The version file uses exactly one canonical `set` declaration for each of `MAJOR`, `MINOR`, `PATCH`, and `PRERELEASE`, as shown in the file, with optional blank lines and single-line comments. Packaging rejects other CMake commands, alternate declaration syntax, duplicates, missing declarations, and source snapshots that omit this file.

After editing `docs/operation.md` or `config/README.md`, run `python3 release/runbook.py`. The specification checker verifies that `docs/operation.txt` matches these inputs, including installed license filenames and explicit source-only references.

The [package guide](../docs/release.md) describes shipped files. [Component notices](component-notices.md) and the [GNU source guide](glibc-source.md) describe required external companions. Compiler/startup/library terms remain separate from the original MIT implementation; inspect actual final outputs rather than assuming every compiler contribution is MIT.

`windows.py` uses the `windows-amd64-local-controls-v1` profile with manifest schema `4`. It requires native Windows 11 x64, Visual Studio 2026, and explicit source/output/work paths. `verify` requires the expected `--source-snapshot`. Windows ZIPs retain the original MIT license, external STL legal text, platform guide, and existing helpers, including the private readiness and GUI transport modules. No driver, interpreter, toolkit, runtime DLL, Linux service unit, or publisher signature is included. Actual provider, desktop, and package execution remains separate from build/core CI.
