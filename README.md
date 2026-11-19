# BrewPi Emulator Remix

BrewPi Emulator Remix replaces an Arduino controller with a native Linux, macOS, or Windows process for hardware-free BrewPi Remix use. It provides a serial PTY on Linux/macOS or uses an externally provisioned virtual COM pair on Windows, virtual probes and outputs, a fermentation chamber model, persistent controller settings, and optional local LCD controls.

Run it alongside BrewPi Remix's host and web panel. The host connects to the emulator's serial path just as it connects to a controller. No Arduino, USB serial adapter, GPIO, sensors, or relays are needed.

The default Uno/RevC personality is retained. Select `--profile i2c` for the Uno I2C identity and A0 probe bus; see the [profile pin maps and saved-state rules](docs/operation.md#connect-brewpi-remix).

## Quick start

Use the binary archive for your Linux architecture from the [downloads](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases). The supported binary baseline is 64-bit Debian 12 on amd64 or ARM64, with its C/C++ runtime libraries. See [installation](docs/operation.md#installation) for archive verification, dependencies, and source builds.

Create private directories and start a foreground instance:

```sh
umask 077
mkdir -p "$HOME/.local/run/brewpi-emulator" "$HOME/.local/state/brewpi-emulator"
chmod 700 "$HOME/.local/run/brewpi-emulator" "$HOME/.local/state/brewpi-emulator"
brewpi-emulator-rmx --serial "$HOME/.local/run/brewpi-emulator/serial" \
  --state "$HOME/.local/state/brewpi-emulator/controller.json" --lcd terminal
```

Set the BrewPi host's `port` to that serial path and `altport` to `None`. Use the panel's factory reset to initialize a new controller store, then discover and assign the virtual devices. Keep the emulator running while the host uses it. Both processes need access to the same PTY and private paths; using the same unprivileged account is simplest.

## Documentation

- [Operating guide](docs/operation.md): installation, host setup, displays, controls, checkpoints, and troubleshooting.
- [macOS guide](docs/macos.md): Apple Silicon builds and packages for macOS 27.
- [Windows guide](docs/windows.md): Windows 11 x64, virtual COM pair records, and platform prerequisites.
- [Scenarios](config/README.md): temperatures, fermentation, room cycles, and virtual hardware.
- [Package contents](docs/release.md): files, integrity, and license/source companions.
- [Development](docs/development.md): source builds, regression tests, and architecture.
- [Protocol reference](engineering/protocol/README.md): wire behavior, defaults, diagnostics, and compatibility limits.

The controller follows the selected Arduino firmware's observable behavior, including its quirks. Host profiles and serial deadlines use wall time even when simulation time is accelerated. Undefined-memory and physical-bus outcomes are not fully reproduced; the emulator is not a physical Pi or Arduino hardware qualification tool. A separately identified source build passed [native Pi host/panel and systemd lifecycle/boot checks](engineering/qualification.md) on a Raspberry Pi 5 with Debian 13.7 ARM64; this does not qualify other configurations or binary release archives.

Original code and documentation use the [MIT License](LICENSE.md). Compiler/runtime contributions retain their separate terms; keep the [third-party notices](THIRD_PARTY_NOTICES.md) and required distribution companions with the software.
