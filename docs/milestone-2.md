# Milestone 2 development operation

This is the historical milestone 2 operating record. Current controller/thermal/clock operation is documented in the [milestone 3 guide](milestone-3.md); its implementation supersedes the limits that were pending at milestone 2.

This is a transport/registry/persistence review build, not a complete brewing controller. It has no autonomous controller/filter/thermal ticks, fermentation dynamics, acceleration, checkpoint resume, or changing LCD display. Assigned probes currently present the fixed 20 C external baseline plus calibration. Command-side target derivation supports the reviewed persistence scenarios; repeated PID/integral/state histories remain milestone 3 work. Do not use this stage to claim complete host/panel compatibility or control trajectory fidelity.

## Build and validate

Use CMake 3.16 or newer, a C++17 compiler, and Python 3.9 or newer for tests. No downloaded/vendored library or Python package is required. Linux ARM64 and x86-64 and macOS ARM64 development builds were exercised; Raspberry Pi hardware and actual host/panel integration were not.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j 4
ctest --test-dir build --output-on-failure
```

For address/undefined-behavior sanitizers with GCC or Clang:

```sh
cmake -S . -B build-sanitize -DCMAKE_BUILD_TYPE=Debug -DRMX_SANITIZERS=ON
cmake --build build-sanitize -j 4
ctest --test-dir build-sanitize --output-on-failure
```

CTest runs the reviewed fixture data through the C++ engine, supplementary behavioral/codec regressions, and actual PTY/process/store tests. Reports are written to the build's ignored test-results directory. All 57 reviewed cases are accounted for: 44 pass at this milestone, four are explicitly deferred to milestone 3, and nine remain unresolved reference-characterization obligations. Deferred/unresolved cases are not passing conformance evidence. [Review evidence](../engineering/development/milestone-2-review.md) records exact environments and limits.

## Isolated process

Select private development paths that do not touch a working BrewPi installation:

```sh
./build/brewpi-emulator-rmx --serial "$PWD/runs/chamber1/serial" --state "$PWD/state/chamber1/controller.json"
```

The default Linux paths are /run/brewpi-emulator/chamber1/serial and /var/lib/brewpi-emulator/chamber1/controller.json; a normal user may not be able to create their parents. No service, system directory, installer, host configuration, or privilege change is performed automatically. --help and --version report local program information; serial n retains the reviewed firmware personality.

The process announces its stable path and PTY slave on stderr. Open the stable path as raw serial, conventionally 57600 baud. A fresh/wrong-controller-version store starts with W3 safe mode; send E to initialize it before assignments. All controller commands use the reviewed firmware grammar and CRLF responses, including incremental j, first-character device/query aliases, discovery order/leaks, and diagnostic ordering. Opening/closing the slave does not reset the controller. R reloads saved state without an acknowledgment; a process restart also reconstructs volatile state. Future host/panel checks must explicitly configure the stable path; there are no USB descriptors or automatic USB reset.

SIGINT/SIGTERM removes the unchanged symlink owned by that process. An existing serial-path file or symlink is never silently replaced. After an unclean termination, inspect the path and lock ownership and remove a verified stale symlink before restarting; never remove a live/foreign path automatically. Lock files may remain, but kernel locks release when descriptors close. Exclusive locks prevent two processes from owning the same state or serial path. Output is buffered without dropping bytes, and input pauses under output backpressure.

## Storage and fidelity boundaries

The emulator's original host-file format is brewpi-emulator-store-v1, containing controller-version validity, raw saved settings/constants, and 16 saved device records. It is not a firmware EEPROM binary or imported header layout. Hardware ROM identities are independent of the saved controller record set. E clears controller slots while retaining those identities. Volatile C and intermediate S stores, strict profile save thresholds, reload validation, and per-field j saves follow the contract. Each individual host-file save uses a checked replacement and fsync; an entire j object remains incremental, with no rollback of earlier saved fields.

Missing storage means erased controller state; an incompatible controller_version means W3 safe mode. Malformed/unrecognized/incomplete emulator host-file formats, nonregular or oversized state files, and host I/O failures are fatal environment errors on stderr, with no invented Arduino diagnostic or success acknowledgment. Such failures are distinct from firmware-side slot validation. Store files/locks are private by default, no reference binary is serialized, and no native AVR memory layout is assumed.

Reference-dependent memory/arithmetic/bus/duplicate-history outcomes remain unqualified. Detected unsafe cases such as slot 16, U before E, odd-length/excessive/malformed ROM input, scalar long overflow, and noncanonical boolean representation stop outside the serial protocol with a fidelity-gap error; this is an explicit limitation, not a faithful Arduino rejection or a passing test. Some electrical/duplicate histories cannot yet be detected or modeled reliably. Do not use these paths to claim reference parity. See the [findings register](../engineering/protocol/firmware-findings.md) and [clarifications](../engineering/protocol/milestone-2-details.md).
