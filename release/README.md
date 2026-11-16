# Package utilities

These original MIT tools build and inspect archives without committing, publishing, activating services, or changing reference clients.

| File | Purpose |
| --- | --- |
| `artifacts.py` | Allowlisted source snapshots, deterministic archives, safe extraction, source identity, native builds, and installed inventories. |
| `source-files.txt` | Explicit source archive inputs; excludes private/generated state and obsolete collateral. |
| `local.py` | Isolated reproducible builds and verification of saved local package sets. |
| `runtime.py` | Clean packaged-runtime checks without a compiler/build tree. |
| `audit_binary.py` | Compiler/header/startup/archive and shared-library inspection for component notices. |
| `checks.py` | Archive, mode, identity, reproducibility, and payload-boundary regressions. |
| `runbook.py` | Generate or check the installed text guide from the operating and scenario guides. |
| `build.Dockerfile`, `runtime.Dockerfile` | Separate build/runtime environments. |

Run `python3 release/checks.py` for helper regressions. Invoke each utility with `--help` for its arguments. Use new output directories and exact source/payload identities; never overwrite accepted/public artifacts. No ignored directory, reference repository, tool image, raw capture, or credential belongs in a source archive.

`cmake/version.cmake` is the application version authority. An empty prerelease field produces a final version without a trailing hyphen. Source archives, binary archive names, manifests, and executable `--version` output must agree with it. Saved-input verification defaults to that version; `local.py verify` and `artifacts.py repack-source` accept `--expected-version` to select a different saved input explicitly. Verification never relabels the saved files or grants qualification acceptance.

The version file uses exactly one canonical `set` declaration for each of `MAJOR`, `MINOR`, `PATCH`, and `PRERELEASE`, as shown in the file, with optional blank lines and single-line comments. Packaging rejects other CMake commands, alternate declaration syntax, duplicates, missing declarations, and source snapshots that omit this file.

After editing `docs/operation.md` or `config/README.md`, run `python3 release/runbook.py`. The specification checker verifies that `docs/operation.txt` matches these inputs, including installed license filenames and explicit source-only references.

The [package guide](../docs/release.md) describes shipped files. [Component notices](component-notices.md) and the [GNU source guide](glibc-source.md) describe required external companions. Compiler/startup/library terms remain separate from the original MIT implementation; inspect actual final outputs rather than assuming every compiler contribution is MIT.
