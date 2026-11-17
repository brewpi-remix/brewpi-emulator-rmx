# macOS operation and source builds

The native ARM64 release targets macOS 27.

The native Apple Silicon executable uses a raw PTY and a stable symlink for serial clients. A macOS archive contains the executable under `bin/`, helpers under `libexec/brewpi-emulator-rmx/`, and its operating guide and licenses under `share/doc/brewpi-emulator-rmx/`. Extract the archive into a private directory and run commands from that directory. Binary users do not need a compiler or CMake. Original emulator source, helpers, and tests use the [MIT License](../LICENSE.md).

Verify the downloaded archive against its accompanying `SHA256SUMS` with `shasum -a 256 --check SHA256SUMS`. Checksums establish integrity. After extraction, verify the executable's signature with `codesign --verify --strict ./bin/brewpi-emulator-rmx`, and inspect its publisher with `codesign -d --verbose=4 ./bin/brewpi-emulator-rmx`. Compare its `TeamIdentifier` and Developer ID authority with the publisher information accompanying that archive. Apple notarization acceptance is a separate check associated with the exact archive; a valid signature alone does not establish it.

For a source build, use Xcode Command Line Tools, a C++17 compiler, and CMake `3.16` or later. Python `3.9` or later is required for development tests and readiness checks; the optional graphical LCD helper also needs a working `tkinter` extension and Tcl/Tk. These dependencies remain external.

```sh
cmake -S . -B build-macos -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET=27.0 -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build-macos -j2
(cd build-macos && ctest --output-on-failure)
```

The deployment target selects the minimum OS recorded in the executable; it does not establish execution on every macOS version. Run terminal/GUI tests in a session that permits access to their private controlling terminals. A sandbox that denies `/dev/tty` can prevent those presentation tests from running correctly.

Use `./bin/brewpi-emulator-rmx` from an extracted archive, or `./build-macos/brewpi-emulator-rmx` after the source build above. Use explicit writable paths for the PTY symlink and controller store. Replace the username and keep each emulator instance's paths separate:

```sh
./bin/brewpi-emulator-rmx --serial /Users/example/.local/run/brewpi-emulator/serial --state /Users/example/.local/state/brewpi-emulator/controller.json --lcd terminal
```

Headless operation uses `--lcd off`. For graphical controls, use `--lcd gui` or `--lcd auto` with the external GUI dependencies available. The [operating guide](operation.md#local-rotary-and-door-controls) describes the existing rotary, pushbutton, and door controls. These local controls do not change Arduino serial acceptance or replies.

Configure a serial client on the same Mac with the stable symlink rather than the changing `/dev/ttys...` target:

```ini
port = /Users/example/.local/run/brewpi-emulator/serial
altport = None
```

Use `57600` baud, eight data bits, no parity, and one stop bit. Configuration values are literal paths; they do not gain shell-variable or `~` expansion. `port = auto` does not discover virtual PTYs. Restarting the emulator replaces the underlying PTY, so clients must close and reopen the configured symlink. Client close/reopen does not itself reboot the controller; `R` requests an explicit controller restart.

The [readiness helper](../scripts/wait-ready.py) checks the owned raw PTY without reading startup bytes or changing terminal attributes. On Darwin, `IGNBRK` can remain set by raw mode. A serial client may purge startup bytes when opening or explicitly flushing input; this is distinct from emulator byte loss. LCD serial replies retain raw byte `B0`, which BrewPi decodes as CP437, rather than a UTF-8 degree glyph.

For explicit checkpoint continuation, follow the [checkpoint procedure](operation.md#stop-restart-and-checkpoints) with writable absolute paths. Drain replies and stop client traffic before clean emulator shutdown. A successful write to an OS buffer is not proof that the client consumed those bytes.

The optional [native pySerial regression](../tests/macos_serial.py) requires separately installed pySerial `3.5` and exercises startup purges, flush/drain, readiness, parser waits, close/reopen, and process lifecycle cleanup. See [development tests](../tests/README.md). It establishes the tested endpoint behavior, not a native port or qualification of the entire external BrewPi host/panel stack.
