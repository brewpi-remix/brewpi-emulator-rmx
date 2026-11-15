# Provisional 0.0.1-rc.1 packages

The local R4 package is an unsigned review candidate for later qualification. It is not a public release, qualified physical Pi installation, activated systemd service, or proof of the nine unresolved Arduino characterization cases. Original emulator code, helpers, configuration, and prose remain MIT; external system/compiler/runtime material retains its own terms. No BrewPi/Fuscus code, assets, implementation routines, or translated tests are incorporated.

Application metadata is defined in [cmake/version.cmake](../cmake/version.cmake): numeric version 0.0.1 and prerelease rc.1. The command --version prints brewpi-emulator-rmx 0.0.1-rc.1. Serial n still returns the reviewed firmware identity 0.2.13/8f1fa12, shield 2, simulation 0, board s, and logging 3. Store/checkpoint schemas and all Arduino action/reaction rules remain unchanged.

## Source identity before a commit

The owner requires review before committing or pushing R4. Consequently, these provisional bytes cannot truthfully name the current baseline commit as their complete source. SOURCE.json records the baseline Git commit, fixed source timestamp, explicit original-file allowlist, modes, SHA256 hashes, and a canonical source-snapshot hash. source_commit remains null. Schema 2 payload manifests require the independently supplied RMX_CANDIDATE_SNAPSHOT; passing a candidate-commit expectation instead is refused. Existing schema 1 R2 fixtures retain their original commit-based semantics.

Owner review and an exact reviewed commit association remain gates before starting R3. That association must prove the committed original input files equal this saved allowlist and snapshot; a documentation-only association receipt may remain outside the saved payload. Changing code, notices, version, inputs, executable, helper, or archive bytes after formal freeze requires a new candidate under the [release policy](../engineering/development/software-release-policy.md). Setup failures before a successful save use separate attempt directories and do not imply accepted artifacts. The owner explicitly authorized fixing this unaccepted local R4 review while preserving 0.0.1-rc.1. Reviewed local inputs use a distinct destination and new snapshot/hash identities without replacing the earlier copy; this narrow instruction does not permit replacement of accepted or public packages.

## Archives and inert staging

The source archive is brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz. Binary archives are brewpi-emulator-rmx-0.0.1-rc.1-linux-amd64.tar.gz and brewpi-emulator-rmx-0.0.1-rc.1-linux-arm64.tar.gz. Each contains one matching top-level directory. Binary contents underneath it are relative to the configured /usr/local prefix: bin/brewpi-emulator-rmx, libexec/brewpi-emulator-rmx/wait-ready.py, share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service, and the project LICENSE.md, THIRD_PARTY_NOTICES.md, and operation.txt under share/doc/brewpi-emulator-rmx. Exactly these six project files are shipped; no external library, test driver, browser, host/panel, or compiler is bundled.

Extract into a fresh directory and inspect the manifest before choosing an installation prefix. The top-level archive directory is not the installation prefix. The service example embeds /usr/local paths, so relocating the extracted tree does not relocate those commands. There is no package manager, auto-installer, service activation, or live-host modification. Use the [operating guide](operation.md) and included standalone runbook for explicit private runtime/state paths and safe lifecycle behavior.

### Build dependencies versus installed runtime

Building the source archive needs a C++17 compiler (GCC 12 for the recorded Debian 12 baseline), CMake 3.16+, Make or another supported build tool, and the C++/POSIX development headers/libraries. The default BUILD_TESTING=ON configuration and native suites additionally need Python 3.9+ with its standard library; a core-only source build can use -DBUILD_TESTING=OFF. Standard native tests do not require Tcl/Tk. Static source-citation checks additionally require Git and the prepared external references; ordinary native tests do not.

Running a compatible extracted executable does not require a compiler, CMake, Make, Ninja, or any Kitware service/library. It needs its recorded Linux architecture/ABI, operating-system loader, and C/C++ runtime libraries, including libc6, libstdc++6, and libgcc-s1 on the Debian 12 baseline. Python 3 is needed only when invoking the included wait-ready.py helper or using the service example that invokes it. The core executable itself is not linked to Python.

The saved six-file R4 archives predate the later optional LCD addition and do not contain its GUI helper; newer source documentation does not retroactively add that feature to saved artifacts. For an LCD-capable build from current source, headless and Unicode terminal operation need no Python/Tcl/Tk, while the optional graphical LCD needs Python 3.9+, working tkinter/_tkinter, compatible Tcl/Tk with Tk 8.6+, a local desktop/font, and the separately selected lcd-viewer component. See the [runtime dependency matrix](operation.md#installed-runtime-dependencies) and [GUI runtime checks](operation.md#checking-the-optional-gui-runtime). These documentation clarifications do not rebuild, replace, or change any saved package.

## Local construction and validation

The original release helpers use a saved explicit source-file allowlist, not an unrestricted working-tree archive. Tar/gzip metadata fixes ordering, owner/group, modes, and SOURCE_DATE_EPOCH; unsafe paths, links, duplicate/extra members, and privileged modes are rejected. Pinned Debian base/snapshot recipes produce architecture-specific build/runtime image IDs, exact package versions, downloaded package SHA256 inventories, compiler/linker flags, baseline ISA selection, and loader/symbol records. Images and external notices stay outside the payload.

Prepare local tool images from the repository root (downloads occur only during provisioning):

```sh
for arch in arm64 amd64; do
    docker build --platform "linux/$arch" -t "brewpi-emulator-r4-build:$arch" -f release/build.Dockerfile release
    docker build --platform "linux/$arch" -t "brewpi-emulator-r4-runtime:$arch" -f release/runtime.Dockerfile release
done
```

 Run python3 release/local.py prepare NEW_ATTEMPT. Preparation creates a provisional source snapshot, canonicalizes its archive using the pinned Linux tools, and builds/tests twice in fresh differently located roots for each architecture. It requires identical source/binary archive bytes and deterministic manifests; no post-hash stripping or binary transformation occurs.

Run python3 release/local.py runtime ATTEMPT arm64 (and amd64) to exercise the exact extracted executable/helper under an unprivileged user in a read-only, toolchain-free runtime guest with networking disabled. The existing nine runtime checks exercise PTY/default/init/persistence/checkpoint/readiness behavior. Separate native drivers validate all 48 source-defined semantic fixtures; the nine characterization obligations remain unresolved. Full native ARM64 host/panel and qualification workflows use schema 2 manifests and the source archive's own launchers, with new evidence paths under the attempt directory. No earlier build-tree executable may substitute for the extracted candidate.

The development Mac supplies native ARM64 Linux guests and emulated amd64 guests. Emulated results are supplemental and are explicitly labeled; minimum-tool checks for the candidate source, native amd64 packaged client/qualification, the reviewed source commit association, R3 sustained workloads, final R4 artifact gates, R5 actual-archive/license acceptance, and R6 owner handoff remain separate. No emulated result satisfies a required native release gate.

After all local checks and the preliminary component/notice inventory pass, python3 release/local.py seal ATTEMPT NEW_DESTINATION creates the read-only saved candidate with exact archive hashes, build/payload/source manifests, environment identities, and detached checksum files. It refuses an existing destination and does not publish or tag anything. Validation logs, raw external-client captures, and live host/timing observations remain in ignored evidence rather than entering reproducible payloads. Separately attributed external package copyright copies accompany the archives as sidecars; they are not inside the source or six-file binary archives. Saving rechecks both build roots and CTest XML, complete file modes/inventories, runtime input/receipt identities, and archive/sidecar consistency. Use python3 release/local.py verify DESTINATION to recheck the saved set. Checksums identify content and do not authenticate it. The original R4 working record under engineering/development records the actual local results and remaining gates separately from the saved source snapshot.

The packaging regression suite is python3 release/checks.py. It is included in the existing CI helper and macOS development lanes; local execution does not establish a new hosted CI pass. Native amd64 workflows, candidate minimum-tool results, and R3 remain required even when local emulated checks pass.
