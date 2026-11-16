# Operating BrewPi Emulator Remix

This development executable is an independently authored MIT replacement for the selected Arduino controller's serial behavior. It models external brewing equipment without connecting physical sensors, GPIO, USB reset circuitry, or an Arduino. Firmware behavior, including documented bugs, is defined by the [behavioral contract](../engineering/protocol/behavioral-contract.md). The [milestone 5 review](../engineering/development/milestone-5-review.md) records qualification of the owner-selected isolated Debian 12 ARM64 Linux environment; physical Raspberry Pi, Arduino-artifact parity for unresolved cases, and actual systemd boot activation are separate evidence boundaries.

## Dependencies

### Build and test dependencies

Building from source needs a C++17 compiler, CMake 3.16+, Make or another supported build tool such as Ninja, and the C++/POSIX development headers and libraries. CMake configures the build and stages the installation; it is not linked into the emulator. The default CMake configuration enables BUILD_TESTING and requires Python 3.9+ with its standard library even if you do not subsequently run CTest. The six native suites need no Tcl/Tk. Opt-in real graphical LCD tests additionally need the GUI runtime below; host/panel integration has separate external test dependencies described in the [integration guide](milestone-4.md).

To build only the executable without requiring a Python test interpreter, configure with -DBUILD_TESTING=OFF. This does not remove the optional helpers' own runtime requirements when you choose to use them.

### Installed runtime dependencies

A compatible prebuilt executable needs the operating system's loader and C/C++ runtime libraries for its architecture and ABI. For the recorded Debian 12/GCC 12 baseline, these include libc6, libstdc++6, and libgcc-s1; use the artifact's recorded runtime/library requirements rather than assuming any Linux system is compatible. The install tree does not bundle these system libraries.

| Installed feature | Additional runtime requirements |
| --- | --- |
| Core executable, headless (--lcd off or no LCD option) | No Python, Tcl/Tk, compiler, CMake, Make, or Ninja is required. |
| Unicode terminal LCD (--lcd terminal) | A foreground controlling terminal, UTF-8 locale, a single-cell ° glyph, and at least 23 columns by 8 rows. Python and Tcl/Tk are unnecessary. |
| Optional graphical LCD (--lcd gui or --lcd auto) | The original lcd-viewer helper, python3 on PATH resolving to Python 3.9+, working tkinter and its compiled _tkinter binding, a compatible Tcl/Tk installation with Tk 8.6+, and a local graphical session with a degree-capable font. |
| Optional wait-ready.py readiness helper | Python 3 and its standard library; Tcl/Tk is unnecessary. Installing the helper file does not make Python a requirement for running the core executable directly. |
| Optional systemd service example | systemd and the readiness helper's Python 3 runtime, because ExecStartPost invokes wait-ready.py. This remains true for the example's headless emulator mode; no Tcl/Tk is needed unless a GUI is separately requested. |

CMake is supplied by Kitware, but the installed emulator uses no Kitware runtime library, service, account, or network connection. Build dependencies belong on the machine building/staging the source; a machine running a compatible prebuilt executable needs only its selected runtime features. Existing BrewPi host/panel applications have their own independently supplied dependencies.

### Checking the optional GUI runtime

Python distributions may supply tkinter/_tkinter separately. Install the Tk binding and matching Tcl/Tk runtime for the same interpreter selected by python3 on PATH; installing them for a different Python version will not make that interpreter's GUI work. Run the following in the graphical session where the emulator will run:

```sh
python3 -c 'import sys, tkinter; print(sys.executable); print("Tk", tkinter.TkVersion)'
python3 -m tkinter
```

The first command should import successfully and report Tk 8.6 or later. The second should open a Tk demonstration window. A missing binding/toolkit or unavailable desktop causes --lcd gui/auto to fall back to the terminal, then headless mode when no suitable terminal exists. Neither the Python interpreter nor Tcl/Tk is bundled by the optional lcd-viewer component; see [component staging](#optional-local-lcd).

## Build, test, and stage

```sh
cmake -S . -B build-release -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build-release -j 4
(cd build-release && ctest --output-on-failure)
DESTDIR="$PWD/stage" cmake --install build-release
```

For a source build without the Python-based tests:

```sh
cmake -S . -B build-core -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build build-core -j 4
```

Use a fresh stage directory for each inspection; install does not remove stale files from an older staging tree. Keep the configured install prefix unchanged at installation time because the service paths are generated at configure time. The internal original protocol library is linked statically even if BUILD_SHARED_LIBS is set, so the executable has no uninstalled project-library dependency. Staging writes only below stage. Inspect install_manifest.txt and the staged tree before an explicitly authorized deployment. The tree contains the executable, original readiness helper, optional generated service example, original MIT license/notices, and the standalone operation.txt runbook. No reference host/panel, reference implementation, test dependencies, or system libraries are installed. The separately inventoried local rc.1 packages remain unpublished; no automatic installer, service activation, or firmware flasher is supplied. The CLI --version identifies the development application; serial n retains the selected firmware identity and is unrelated to that application version.

## Foreground startup and access

Use a private writable directory and an explicit endpoint while testing:

```sh
umask 077
mkdir -p runs/chamber1 state/chamber1
chmod 700 runs/chamber1 state/chamber1
./build-release/brewpi-emulator-rmx --serial "$PWD/runs/chamber1/serial" --state "$PWD/state/chamber1/controller.json" --speed 1
```

Run the emulator and the serial-reading BrewPi host as the same dedicated account. Existing directories must already be owned by that account; umask affects newly created files and does not tighten an existing directory. After replacing an emulator process/PTY, stop and reopen or restart the host against the new path; a previously open descriptor still refers to the old PTY. No automatic host reconnect or dependency unit is supplied. The private directories, state file, and lock files limit access; a symlink's mode does not grant access to its PTY target. The web panel talks to the host's socket rather than opening the emulator PTY. Point the isolated host configuration at that explicit serial path, set altport=None, and use startupDelay=0 when USB startup delay is unnecessary. The [milestone 4 guide](milestone-4.md) contains the tested external-client setup.

A newly absent store represents erased firmware configuration, emitting W3. Initialize it with the panel's factory reset, which sends E, before discovering and assigning virtual devices. The native identity, inventory, defaults, calibration behavior, and EEPROM-like write side effects remain those in the reviewed fixtures. Settings C/S resets can leave saved and live values different; do not infer restart state from the last displayed value alone.

The original wait-ready.py helper checks that a PID exists and a same-account character endpoint has raw terminal flags without reading or writing serial bytes. It leaves the initial W3 and subsequent stream available to the real client:

```sh
scripts/wait-ready.py --serial "$PWD/runs/chamber1/serial" --pid EMULATOR_PID --timeout 10
```

EMULATOR_PID must be the actual running emulator's positive PID, and the endpoint must be in its trusted private directory. The helper does not authenticate a PID-to-PTY relationship or protect against another process running as the same account. Readiness is a process/endpoint check, not controller initialization, a temperature-control promise, or a replacement for the host's n/s/c/v handshake. A missing, nonraw, or inaccessible endpoint, or a PID that no longer exists, fails outside the serial protocol. It checks descriptor ownership/identity and raw input/output/local/control flags without changing them.

## Optional local LCD

The local LCD is opt-in. Add --lcd terminal for a Unicode console panel, or --lcd gui (equivalently --lcd auto) to prefer a Python graphical LCD with automatic terminal fallback. --lcd off and an omitted option preserve headless operation. Both presentations display the retained twenty-by-four controller screen with the proper °C/°F symbol; the serial L reply retains its raw B0 byte. The viewer never opens the host serial endpoint; explicit confirmed local control actions reach the C++ engine through private IPC, while browsing alone does not commit controller settings. Room/Fridge alternation, state phrases, timers, paused histories, and unit repaints remain those of the engine.

The console needs a foreground controlling terminal and a UTF-8 locale with a single-cell degree glyph. ANSI/VT terminals require at least 23 columns by 8 rows for the six-line LCD and one reusable command/status line with wrap protection. Commands are cw, ccw, press, door open, door close, and help; Enter submits text, while only press represents the encoder pushbutton. Command acknowledgments remain on the same line for 750 wall milliseconds, then the prompt returns; new typing dismisses the acknowledgment immediately. Input supports Backspace and Ctrl-U, rejects an entire invalid/overlong line through its terminator, and deduplicates CR/LF submission. The display rewrites in place without scrolling per command. Unknown/dumb terminals retain read-only snapshots and explain that interactive controls require cursor rewriting.

Terminal controls use a separate nonblocking /dev/tty description, temporarily disable canonical input/echo while retaining signals, and restore owned modes on handled exit and before job-control suspension. Redirected standard streams and the controller serial PTY remain separate. Small/background terminals suspend interaction and discard drafts; buffered input from the suspended control session is discarded only after foreground control ownership returns. No alternate screen or cursor hiding is installed. A revoked/lost terminal and SIGKILL cannot guarantee mode restoration. macOS revokes a terminating session leader's private PTY, so test post-exit inspection differs from Linux.

The graphical LCD needs python3 on PATH, Python 3.9+, Tk 8.6+, and a working local graphical session with a font containing °. Python is not linked into the emulator and is unnecessary for terminal/headless operation. Older Tk, missing modules/helper, a failed or timed-out window, failed private IPC, and a hung or unread GUI channel automatically select the terminal. Without a usable controlling terminal, execution continues headless. GUI availability never changes the emulator's exit status; genuine application failures remain errors. Deliberately closing the graphical window (or using macOS Quit) requests normal emulator shutdown, including the existing checkpoint decision. Unexpected viewer exit still selects fallback. There is no automatic GUI restart. A process suspension exceeding the helper's ten-second parent lease can close the GUI and select terminal fallback on resume.

Development builds copy the original Python helper adjacent to the executable. Installed executables first look for it relative to their configured bindir/libexec layout and then adjacent to the executable; neither lookup searches the caller's working directory. The standard install remains the six-file headless/terminal core. The separately selected lcd-viewer install component adds one original helper. To inspect both components in a new local staging tree, keeping the configured prefix unchanged:

```sh
DESTDIR="$PWD/stage-lcd" cmake --install build-release
DESTDIR="$PWD/stage-lcd" cmake --install build-release --component lcd-viewer
```

This stages seven original project files and no Python/Tcl/Tk/font binaries. It does not activate a service or install anything onto the live host. Older core-v1 six-file manifests and saved packages omit this helper; the final rc.1 local-controls-v1 candidate explicitly includes it as the seventh file and retains its exact reviewed hash. Keep generated install prefixes fixed when validating installed helper discovery, just as with the service example.

Viewer diagnostics are bounded and best effort: they go to the foreground terminal, an independently opened nonblocking Linux stderr descriptor, or a safe existing log destination. A full output sink can drop a diagnostic instead of stopping emulation. On macOS, a blocking redirected pipe without a controlling terminal cannot safely receive extra viewer diagnostics, so those optional messages are suppressed. Existing startup/fatal application diagnostics retain their destinations and semantics. New display work never changes inherited stream flags. Arbitrary nonprintable or unsupported shadow cells are shown as ? locally, with the raw controller/serial image retained.

The local frame is a sampled presentation, not a new timing oracle: rapid accelerated updates are coalesced, and a GUI that initializes slowly may first paint a newer frame than the initial resume shadow. Display queues and GUI process state are outside checkpoints. SIGINT/SIGTERM applies the existing checkpoint decision before best-effort viewer cleanup; undrained serial output or incomplete commands still reject a checkpoint. A terminal driver or OS process teardown can impose its own behavior outside the emulator's nonblocking display writes; a test terminal must consume output while reaping its session leader on macOS. See the [implementation/review record](../engineering/development/lcd-review.md) for actual software evidence and unchanged physical/Arduino qualification limits.

## Local rotary and door controls

The GUI provides an original rotary knob with center press, Counterclockwise/Press/Clockwise buttons, and a door button labeled with its next action. Focused encoder controls accept Left/Right and Enter/Space; the door button's Enter/Space acts only on the door. Held keys do not repeatedly confirm. Virtual steps are already decoded; hs does not multiply a GUI/CLI cw event. No physical GPIO or contact-bounce input is added.

Press opens Mode, Beer, Fridge selection. Rotation wraps through those items or the bfpo modes. Constant-mode selection opens its target editor; the final target press commits both mode and target in firmware setter order. Profile/Off confirms at the mode selection press. Editing is a draft: browsing Off does not disable targets, and timeout writes nothing. An unrotated finite in-range target retains exact internal precision. Rotating uses tenths of the current C/F unit and wraps at the representable in-range endpoints; an initially invalid/disabled target starts at bounded 20 C, and an out-of-range selection starts at the nearest exact endpoint. Reversed/invalid bounds refuse editing. A range with no representable tenth permits exact bounded confirmation but rejects increments. Serial writes retain their existing unrestricted firmware behavior; range changes cancel local drafts rather than silently rewriting serial settings.

Menus expire after ten wall seconds without encoder activity, with approximately 384 ms blink phases; typing/help/door interaction wakes the display without extending menu timeout. Background plant/controller/serial processing continues under its existing pause, token-wait, and backpressure rules. External changes to the editable mode/target/units/bounds cancel drafts, including a serial change followed by restoration in the same object. Controller reset, lost control ownership, viewer failure, deliberate closure, and checkpoint resume also discard drafts. Busy partial serial input or backpressure refuses local encoder operations with retry feedback. Invalid serial/saved modes remain unchanged until a valid local choice is confirmed.

Both GUI and interactive ANSI terminal dim LCD text after strictly more than 60 wall seconds without interaction. Input wakes and acts; the first press opens the menu. Add --lcd-keep-on to disable dimming in either interface. The terminal prompt and GUI controls remain readable. Dimming is presentation metadata and never changes serial LCD bytes. The local menu overlay is also returned by l while active, but base controller shadow history is retained separately in checkpoints; S/T and saved targets never expose uncommitted previews.

Door commands change the physical plant door input, not a controller state or relay. Device assignment, pin inversion, controller evaluation, light logic, annotations, and configured thermal conductance determine the resulting effects; an unassigned door does not magically become a configured sensor. Feedback reports actual modeled physical state, and repeated open/close requests are no-ops. A paused simulation accepts the input state without inventing a scheduled controller evaluation. Controller R preserves the plant door; checkpoint continuation uses its existing plant state.

Private local IPC version 2 carries bounded frames, explicit session/action IDs, state revisions, and action acknowledgments. The GUI permits one outstanding action, with a five-second acknowledgment deadline and no blind retry. Duplicate/malformed input fails the viewer and cancels its draft; a stale revision returns retry feedback without applying the action. Actual GUI failure still falls back; deliberate close/Quit requests normal emulator shutdown. Channel failure first allows up to 250 wall milliseconds to observe a natural reserved child exit, so cleanup cannot mask close intent with SIGTERM; queued close messages have priority over discarded action input. A remaining child then receives SIGTERM and has two seconds before forced termination. Terminal activation discards pre-prompt buffered input only after foreground ownership is established. See the [controls review](../engineering/development/rotary-controls-review.md) and [approved plan](../engineering/development/rotary-controls-plan.md) for approved departures and evidence limits.

## Optional service example

CMake generates a per-instance unit using the configured binary/helper install prefix. Its installed location is share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service, deliberately outside the live system unit directory. It assumes the ordinary brewpi account exists, uses private /run/brewpi-emulator/INSTANCE and durable /var/lib/brewpi-emulator/INSTANCE directories, starts at 1x, and runs the nonconsuming readiness gate after execution. It does not enable itself or automatically resume a checkpoint. Restart is an explicit operator action.

Type=exec checks execution; ExecStartPost adds the endpoint gate before dependent units proceed. RuntimeDirectory and StateDirectory give the service private runtime and persistent state locations, respectively. These are standard systemd semantics, documented by [systemd.service 252](https://www.freedesktop.org/software/systemd/man/252/systemd.service.html) and [systemd.exec 252](https://www.freedesktop.org/software/systemd/man/252/systemd.exec.html); the original unit is not copied from a reference repository. The selected container validates unit syntax and its command/readiness lifecycle, not system-manager activation, namespace behavior, or boot ordering. Validate those on any later deployment target before claiming a working installation. Keep the PTY visible in the serial client's devpts namespace; the example does not add a private device namespace.

## Clock, response, and backpressure

Default speed is 1. --speed 0 pauses scheduled simulated time while preserving synchronous command actions and wall-clock serial-token deadlines. Factors 10 and 60 change pacing, not controller timer widths, thresholds, filter arithmetic, or the fixed physical integration step. Host profiles, CSV timestamps, and chart clocks remain real wall time. --scenario accepts the original [configuration examples](../config/README.md); repeatability requires the same input, seed, and event history.

Sampled n identity requests are checked against the host's one-second serial window in the qualified workload. An incomplete token can intentionally wait about a wall second, and real bus conversion/undefined artifact behavior is not covered by a blanket response bound. A slow reader causes buffering and input/controller deferral; it does not authorize dropped bytes or an invented firmware error. Drain queued replies before expecting the next command's response. The review records measured rates and latencies for its exact workload, not a universal performance guarantee or accelerated host-profile equivalence.

## Stop, restart, and checkpoints

SIGINT or SIGTERM requests normal shutdown and removes only the process's unchanged owned endpoint link. Firmware-saved settings/slots survive a process restart. Ordinary process restart starts a fresh physical scenario and new controller volatile state; R resets controller volatile state while retaining the running physical plant, and E has its documented smaller reset scope. A client closing/reopening the port is not a USB reset.

Scenario inputs must not alias runtime output files or their lock paths, including through normalized paths, symlinks, or hardlinks; startup rejects those collisions before creating locks or publishing a PTY. Use separate paths for authored scenarios and generated state/checkpoints.

For coherent continuation, explicitly start with --checkpoint PATH, stop the host/client, complete any partial command, and drain serial output before signaling the emulator. A clean checkpoint captures live versus saved controller state, plant/history/random state, counters/timers/display, and fractional time. Resume it with --resume PATH and the same saved store; stopped downtime is not added. --speed may override resumed pacing, while --scenario cannot override an existing resumed history. See the [clock/checkpoint guide](milestone-3.md) for complete examples.

If a command is incomplete, output remains queued, the checkpoint is corrupt, or its saved store no longer matches, the operation fails outside serial rather than inventing an Arduino acknowledgment or silently rolling state back. Failures before atomic file replacement retain the previous checkpoint. A host filesystem error reported after rename, such as directory-sync failure, may leave the new file in place with uncertain durability; inspect the error and file rather than assuming the old bytes survived. Inspect the error and choose whether to finish/retry the checkpoint or start a fresh physical scenario from the current saved store; there is no automatic fallback to older data.

SIGKILL cannot run cleanup or create a new checkpoint. A stale symlink can remain and intentionally prevents automatic replacement. Confirm the old process is gone, verify the private path and store/serial locks belong to this instance and are free, then remove only that owned symlink before restarting. Never unlink the PTY character target or substitute another active instance's paths. The qualified isolated tests exercise this stale-link recovery sequence; actual power-loss/filesystem durability is not inferred from it.

## Evidence and licensing

Use the [target qualification launcher](../tests/qualification/run-isolated.sh) to reproduce the selected Linux checks in a disposable, network-disabled environment. Its [setup and evidence guide](../tests/qualification/README.md) describes image preparation, fresh evidence directories, exact invocation, and the required passing reports. Its reports separate measured throughput/response/ownership/checkpoint observations, unit syntax checks, native fixture results, and installed-file/library inventories. No agreed physical Pi is implied by ARM64 container execution. Nine exact firmware-characterization obligations remain unresolved; the review makes no affected Arduino parity claim.

Original project work uses MIT. External reference applications, build tools, and operating-system libraries retain their own terms. No system library or client is bundled by the install rules; inspect the actual dynamic closure and staged contents before future redistribution. The [milestone 5 provenance](../engineering/licenses/milestone-5.md) and [third-party notices](../THIRD_PARTY_NOTICES.md) record the material boundary. The owner reviewed milestone 5 and authorized committing and pushing its qualification, guidance, tests, and supporting docs to main; this guide does not authorize a release or deployment.
