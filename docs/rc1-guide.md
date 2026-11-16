# 0.0.1-rc.1 build, run, staging, and recovery

Original operator guidance copyright 2026 Lee Bussy, MIT. Read the [candidate notes](rc1-release-notes.md) and their support limits first. This guide authorizes no installation or service activation. Use private disposable paths and an account dedicated to the emulator and its isolated serial-reading host. All five qualified archives and their notices/source companions must be retained together; neither the helper/source tooling commit nor a later main checkout substitutes for the selected source archive.

## Verify and stage the candidate

The review handoff directory contains packages/ with the five unchanged R5 archives, R5-AUDIT.json, and its original SHA256SUMS; manifests/ contains original source/build/runtime/acceptance sidecars. The handoff's separate SHA256SUMS covers its own files without changing the original package sums. Verify both checksum inventories before extraction. GNU/Linux provides sha256sum; on macOS use shasum -a 256 instead. A checksum does not authenticate an unsigned download.

```sh
sha256sum -c SHA256SUMS
(cd packages && sha256sum -c SHA256SUMS)
umask 077
mkdir stage-amd64 stage-source stage-notices stage-glibc-source
tar -xzf packages/brewpi-emulator-rmx-0.0.1-rc.1-linux-amd64.tar.gz -C stage-amd64 --strip-components=1
tar -xzf packages/brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz -C stage-source --strip-components=1
tar -xzf packages/brewpi-emulator-rmx-0.0.1-rc.1-NOTICES.tar.gz -C stage-notices --strip-components=1
tar -xzf packages/brewpi-emulator-rmx-0.0.1-rc.1-glibc-source.tar.gz -C stage-glibc-source --strip-components=1
```

Select linux-arm64 and a separate stage-arm64 directory on AArch64; do not execute the other architecture's binary or call emulation native qualification. These archives are prefix-relative. Extraction into a staging directory does not install to /usr/local or activate anything. The source tree's SOURCE.json retains its original construction metadata and null source_commit; manifests/source-association.json separately binds all 185 original files and modes to f717d36364778ad48cd28bb5ae5a221c29c5db49. Generated metadata is not a reason to relabel the candidate as the current branch tip. GitHub-generated source downloads are not the qualified custom source archive and do not replace it.

The executable requires the recorded compatible OS loader/libc/libm/libstdc++/libgcc_s closure; Debian 12 glibc 2.36 alone is not a complete ABI guarantee. Core headless/terminal operation needs no compiler, CMake, Python, or Tcl/Tk. Python is required if using the optional readiness helper. The graphical LCD additionally needs the shipped original helper, Python 3.9+ with matching tkinter/_tkinter, Tk 8.6+, and a local graphical session/font; no such runtime or font is bundled. Linux graphical desktop rendering remains unqualified. Check the selected GUI interpreter with python3 -m tkinter if choosing that optional mode.

## Build the archived original source

After independently provisioning a C++17 compiler, CMake 3.16+, build tool, and Python 3.9+ for tests, build offline without Git or reference repositories:

```sh
cmake -S stage-source -B build-candidate -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build-candidate -j2
(cd build-candidate && ctest --output-on-failure)
DESTDIR="$PWD/stage-install" cmake --install build-candidate
DESTDIR="$PWD/stage-install" cmake --install build-candidate --component lcd-viewer
```

Use new empty build/stage directories. The second install command explicitly selects the original optional helper, yielding the seven-file candidate layout; the ordinary core installation alone has six files. DESTDIR confines inspection to staging, while the configured /usr/local prefix stays fixed for generated absolute service paths. No command here copies the inert unit to a live unit directory. For an executable-only build without the Python test prerequisite, use -DBUILD_TESTING=OFF; that is not a test pass. Exact qualified bytes additionally require the pinned R4 build images/packages, generic ISA/prefix-map flags, SOURCE_DATE_EPOCH, and canonical packaging rules recorded in the build manifests. An arbitrary native rebuild is not the accepted executable simply because --version matches. The complete original work source/build scripts and separately provided matching GNU source package permit the library-source/relink workflow described in the R5 notices.

## Run the staged binary in the foreground

For the selected amd64 stage on its compatible native Linux target:

```sh
umask 077
mkdir -p instance/run instance/state
chmod 700 instance instance/run instance/state
./stage-amd64/bin/brewpi-emulator-rmx --version
./stage-amd64/bin/brewpi-emulator-rmx --serial "$PWD/instance/run/serial" --state "$PWD/instance/state/controller.json" --speed 1 --lcd off
```

The default deployment endpoint is /run/brewpi-emulator/chamber1/serial, but these explicit disposable paths need no root account. The emulator and isolated host must share the intended account and endpoint access; a symlink's permissions do not grant PTY access. Configure that host's port to the explicit PTY path, altport=None, and optionally startupDelay=0. The panel talks to the host's socket. Do not point validation at a live brewery, add another competing serial reader, or use USB discovery/flashing workflows for the PTY.

An absent store represents erased firmware configuration and emits W3. Use the normal panel factory reset, which sends E, before discovery/assignment. Confirm through actual controller readback, rather than relying only on the host's optimistic cache. C/S resets and accepted writes preserve the firmware's volatile-versus-saved quirks; E initializes the controller store, while R is an MCU-like reboot and does not reset the external plant. Do not use E as a filesystem-corruption repair or promise every accepted mutation was persisted.

For the terminal LCD, select --lcd terminal in a foreground UTF-8 controlling terminal at least 23 columns by 8 rows, with a single-cell degree glyph. Commands are cw, ccw, press, door open, door close, and help. Enter submits a command; press is the encoder pushbutton. Browsing changes a draft only; deliberate confirmation applies the local action through the engine. GUI controls use separate private IPC and never open the host serial endpoint. Door actions model physical plant input, not a forced relay/state. Drafts time out after ten wall seconds; display text dims after more than 60 wall seconds unless --lcd-keep-on is selected. Closing the GUI deliberately requests normal shutdown; a failed/missing GUI falls back to terminal or headless mode. No serial parsing, storage, or unrelated firmware bug is corrected by these local controls.

## Deliberate shutdown and recovery

Use handled termination, drain serial output, and stop/reopen the host around emulator replacement. The host's old open descriptor continues to name the old PTY even if the stable path is recreated. No automatic reconnect unit is supplied. The readiness helper checks a live PID and raw same-account endpoint without consuming serial bytes; it is not controller initialization or a substitute for the host n/s/c/v handshake.

A normal process restart loads only firmware-saved controller settings and starts fresh scenario/plant history. To retain coherent runtime state, select an explicit checkpoint output on the original run and later use --resume with that checkpoint and its matching store. Preserve the scenario/identity assumptions; resume checks matching controller/store state and adds no elapsed downtime. Checkpoint creation requires drained output and a successful handled exit; SIGKILL, undrained output, storage failures, and physical power loss do not guarantee a new checkpoint. Keep the actual saved store/checkpoint as evidence on corruption or mismatch; do not replace them silently with defaults. Host filesystem/IO failures are application/environment failures, not invented Arduino diagnostic IDs.

The native formats remain brewpi-emulator-store-v1 and brewpi-emulator-checkpoint-v1. Pre-1.0 forward compatibility and migration are not promised. Acceleration changes simulated/controller/plant time; host profile dates, charts, serial token waits, and local interaction deadlines remain wall-clock based. A 60x constant-target test does not qualify accelerated host-profile equivalence.

The tested legacy panel can lay out a sample-profile chart while its tab is hidden, overlapping Open after reveal; wait for the normal five-second Apply refresh, reveal the profile tab, and perform a normal browser resize so the panel recomputes its layout. Profile selection/application used an original CSV sent through the PHP endpoint; dragging the profile editor was not qualified. Mixed C/F history remains mixed numeric chart data and can show a misleading apparent spike after the current label changes. Preserve these client behaviors rather than modifying the reference applications.

This unsigned candidate makes no physical Pi/peripheral/power, systemd manager/boot, physical Arduino, nine-case characterization, additional undefined-outcome, or power-loss-durability claim. For full source-backed details, use the repository's engineering/development/software-release-rc1-dossier.md, docs/operation.md, and engineering/licenses/software-release-r5.md. Keep the separately retained private evidence outside any future public package or MIT source archive.
