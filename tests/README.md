# Development tests

The model suite also covers RevC/I2C identity, discovery order, A4/A0 probe validation, persistence/checkpoint profile isolation, legacy RevC files, and profile-specific thermal load wiring. The process suite exercises the public `--profile` option, restart/resume, and rejection before PTY publication. The 48 original source-defined fixtures remain RevC cases; the nine characterization cases remain unresolved.

LCD regressions check RevC `B0` and I2C `DF` in twenty-byte shadow rows and exact serial replies across unit changes, resets, and checkpoint restoration, while both local presentations receive Unicode degree glyphs. The exhaustive byte-adapter check also verifies the raw shadow is unchanged.

The six CTest suites exercise model arithmetic, dynamics/controller behavior, process pacing/checkpoints, protocol fixtures, edge cases, and real PTY/file ownership. Build and run them using the [development guide](../docs/development.md). Reports distinguish deterministic source-defined cases from unresolved physical/artifact-dependent behavior.

The original [fixture driver](driver.cpp) provides controlled internal state for semantic tests. The shipped executable has no such test interface. PTY/process tests exercise the public executable separately. [Fixture data](../engineering/protocol/test-vectors/README.md) describes byte matching and characterization limits.

Run independent helper regressions from the repository root:

```sh
python3 tests/ci/checks.py
python3 release/checks.py
python3 tests/integration/checks.py
python3 tests/qualification/launcher_checks.py
python3 tests/qualification/checks.py
```

The controls and LCD helpers exercise terminal/IPC behavior, menu confirmation, dimming, GUI fallback, close handling, and installed-helper discovery. They use isolated processes/PTYs; GUI-specific checks need the external graphical toolkit and session. Their command-line entry points identify the executable under test.

The opt-in external-client integration fixture runs the pinned host/panel separately through browser, PHP, socket, and serial interfaces. Prepare the sibling reference repositories listed in [references.json](ci/references.json), Docker, and the external tools image, then run:

```sh
./tests/integration/run-isolated.sh "$PWD/runs/integration-check"
```

Use a new output directory. The launcher owns its container and verifies cleanup; it does not import reference clients into the emulator. Its Dockerfile and requirements lock define external test dependencies. [Runtime checks](qualification/README.md) inspect installed files, readiness, recovery, and inert service commands. Generated state, raw client captures, logs, and screenshots are ignored development outputs, not package contents or original MIT assets.

On native macOS ARM64, [macos_serial.py](macos_serial.py) exercises the real PTY with separately installed pySerial `3.5`, including startup purges, flush/drain, readiness, binary LCD bytes, parser waits at `1x`/`10x`/`60x`, close/reopen, and 100 process/client lifecycles. It requires a private test environment and bounds the complete worker process group; its report is endpoint regression evidence, not final signed-package qualification. Use an external virtual environment containing pySerial and a new report path:

```sh
python3 tests/macos_serial.py build/brewpi-emulator-rmx --output runs/macos-serial.json
```

[macos_runtime.py](macos_runtime.py) checks a retained signed macOS review package for 300 wall seconds at each of `1x` and `60x`, including real terminal controls, query latency, pacing, resident memory, and exact paused checkpoint continuation. It verifies the complete package before and after execution. Its fixed qualification budgets are one second per ordinary identity query, pacing within 15% of the requested factor, RSS below 128 MiB, and an RSS range below 32 MiB. These are test budgets, not controller policy or emulator memory limits. A shorter `--seconds` run is explicitly classified as a smoke check and does not close the duration gate. It requires an external Python environment with pySerial `3.5` and a session permitting private controlling terminals:

```sh
python3 tests/macos_runtime.py /path/to/macOS-review-output --source-snapshot SOURCE_SNAPSHOT_SHA256 --output runs/macos-runtime.json
```

The standalone [Windows boundary build](windows/CMakeLists.txt) exercises native COM I/O, Windows storage, and the private LCD message channel. It requires native Windows, an MSVC-compatible C++17 toolchain, CMake with support for the installed Visual Studio generator, Python `3.9` or later, and an explicitly provisioned HHD virtual COM pair. The following example uses `Visual Studio 18 2026`:

```powershell
cmake -S tests/windows -B build-windows-boundaries -G "Visual Studio 18 2026" -A x64 "-DRMX_SERIAL_PAIR=C:/path/to/approved-pair.json"
cmake --build build-windows-boundaries --config Release
Push-Location build-windows-boundaries
ctest -C Release --output-on-failure
Pop-Location
```

`RMX_SERIAL_PAIR` names an operator-provisioned JSON record in format `brewpi-emulator-serial-pair-v1`, with `provider` set to `hhd-vspt`, `provider_version` set to `7.35.01.1760`, and two `endpoints`. Each endpoint records `port`, `instance_id`, `hardware_id`, `driver_provider`, and `driver_version`; the supported identity profile uses `HHDVIRT\UniversalSerial4`, `HHD Software Ltd.`, and `7.35.0.1753`. Supply the actual canonical `COMn` names and device instance IDs of the approved virtual pair. Checks reject missing, reassigned, unsupported, or busy devices. The operator supplies the opposite-end association; device checks do not discover provider wiring. A missing record fails the COM test. The tests neither provision devices nor select a replacement port.

The storage suite creates disposable files under its build directory, including a directory symlink for reparse-point rejection; that fault setup requires Windows symlink permission. The message-channel test launches a separate Python client and checks packet boundaries, binary bytes, nonblocking reads, and launched-process binding. These are development boundary checks; full Windows application, desktop-control, and package qualification remain separate. External compiler/runtime and provider terms are described in [third-party notices](../THIRD_PARTY_NOTICES.md).

Original tests are MIT. No reference helper, routine, or test is copied or translated. Physical Arduino/Pi behavior and system-manager activation are outside these regression claims.

The opt-in [physical Uno I2C characterization helper](arduino_characterization.py) requires explicit owner authorization, an identified serial port, pySerial 3.5, and a new external evidence directory. It changes settings and assignments, resets the controller, and toggles bench outputs; restoration preserves the original probe roles and adds the documented bench outputs and inverted D4 door input with control off. Read its [preconditions, evidence policy, and observed quirks](../engineering/protocol/i2c-characterization.md) before use. It is separate from normal regression validation; raw hardware captures stay outside source and package inputs.

The native Windows [application lifecycle check](windows_application.py) exercises the actual executable and the approved pair with Unicode state paths, readiness, raw replies, parser waits, client reopening, cooperative shutdown, and checkpoints. The [package runtime check](windows_runtime.py) binds the verified unsigned package and runs the declared pacing, resource, and paused-continuation checks. Both require separately supplied pySerial `3.5`; neither installs a driver. Use each helper's `--help` for explicit paths and finite budgets. [Windows build/core CI](ci/native_windows.py) produces its own execution receipt and does not imply provider or desktop acceptance.

The [native public-protocol adapter](native_protocol.py) replays 30 reviewed cases whose initialized, paused preconditions can be established through ordinary serial commands. It uses the original fixture matcher, binds the fixture/helper/executable hashes, and maps the other 18 deterministic cases to the constructed-state source driver. The nine Arduino characterization cases remain unresolved. This public subset supplements the complete 48-case native core run; it neither seeds engine state nor adds a production test API.

The [Session 0 regression](windows_session0.py) runs hidden consoles through SSH on native Windows x64, using the explicit approved virtual pair and separately installed pySerial `3.5`. It checks headless and terminal modes plus missing-Python GUI fallback, complete identity/LCD replies, repeated queries, cooperative shutdown, checkpoints, inactive readiness, and endpoint reacquisition. It requires `--pair`, `--ready-helper`, `--directory` (a new private test directory), and `--output` (a new report path outside the case directory). A supervisor-owned Windows job bounds the worker and all of its descendants. Reads assemble complete lines one byte at a time; the supported HHD driver's finite total timeout does not reliably complete a bulk read after a short reply. This is a provider limitation, not a change to Arduino wire behavior.

Run `python tests/windows_session0_checks.py` for reader failure checks and, on Windows, a fault-injected supervisor timeout that verifies termination of both the worker and its descendant. The Session 0 execution receipt binds the executable, pair record, and original reader/readiness/lifecycle helpers before and after execution.
