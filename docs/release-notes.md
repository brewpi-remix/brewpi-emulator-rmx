# BrewPi Emulator Remix 0.0.1 — Initial Release

Introducing BrewPi Emulator Remix, a native virtual controller for BrewPi Remix on Linux, macOS, and Windows. Run a simulated fermentation chamber alongside the separately installed BrewPi Remix host and web panel. No Arduino, USB serial adapter, sensors, or relays are required.

This initial release provides:

- A serial pseudo-terminal on Linux and macOS, or an operator-provisioned virtual COM pair on Windows. The web panel communicates through the BrewPi host.
- Two Uno controller personalities: default `--profile revc` and optional `--profile i2c`, with their corresponding firmware identities, probe buses, output inventories, and default virtual load wiring.
- Virtual temperature probes and outputs, chamber heating and cooling, fermentation heat, and configurable room-temperature cycles.
- Persistent controller settings and optional checkpoints for continuing a simulation with its matching saved controller state.
- Terminal and graphical LCDs, with simulated rotary, pushbutton, and door controls.
- Real-time or accelerated simulation; host profiles and timestamps continue to use wall time.

Binary packages target 64-bit Debian 12 on amd64 and ARM64, macOS 27 on Apple Silicon, and Windows 11 x64. Linux and Windows distributions are unsigned. The macOS executable uses Developer ID signing and Apple notarization. Verify the supplied checksums and retain the required notice/source companions described in the [package guide](release.md); checksums establish integrity, not publisher authentication.

Windows requires a separately installed compatible virtual COM provider and the Microsoft Visual C++ v14 x64 runtime. The supported HHD provider has its own licensing restrictions. Its virtual-port driver can stall partial bulk reads despite a finite timeout; the [Windows guide](windows.md) explains the supported client read pattern and explicit pair record. Native Windows BrewPi host/panel execution is not included.

The optional graphical LCD requires separately installed Python 3.9 or later with a working `tkinter` extension, Tcl/Tk, and a local graphical session. Headless and terminal emulator operation require neither Python nor Tcl/Tk. The Python readiness helper and separately installed BrewPi host have their own interpreter requirements. No COM driver, interpreter, toolkit, or runtime-library bundle is included.

Select the profile at startup and use a separate `--state` file for each profile. Supply `--profile i2c` on every restart or checkpoint `--resume` for an I2C instance; the default remains RevC even when loading saved files. RevC stores retain `brewpi-emulator-store-v1`, and legacy untagged files are interpreted as RevC. I2C stores use `brewpi-emulator-store-v2` with an explicit `i2c` profile tag, which older RevC-only executables reject. Checkpoints record the profile and embed the matching store. The emulator rejects cross-profile or conflicting metadata locally before opening the serial interface, without automatically converting assignments. See the [profile pin map and saved-state rules](operation.md#connect-brewpi-remix).

Both profiles render a virtual LCD. The Arduino I2C bench guide covers a separate physical setup and its hardware-specific comparison limits. The emulator follows the selected Arduino firmware's documented behavior, including its quirks. The nine nonpassing characterization placeholders retain their documented classifications: covered subclaims are recorded separately, and their remaining compatibility limits are accepted without further investigation. See the [firmware findings](../engineering/protocol/firmware-findings.md#outstanding-limits--will-not-address). A separately identified source-built artifact passed [native Pi host/panel and actual systemd lifecycle/boot qualification](../engineering/qualification.md) on a Raspberry Pi 5 running Debian 13.7 ARM64; that result does not qualify binary release archives, other Pi configurations, or physical Arduino behavior. The supplied Linux systemd example still requires deliberate installation/enablement and explicit host reopening after emulator replacement.

Original emulator code, helpers, tests, and documentation are independently authored under the [MIT License](../LICENSE.md). External compiler/runtime contributions retain their separate terms, described in the [component notices](../THIRD_PARTY_NOTICES.md).

## Further information

- [Installation and operating guide](operation.md)
- [macOS installation and use](macos.md)
- [Windows installation and use](windows.md)
- [Simulation scenarios and configuration](../config/README.md)
- [Protocol reference and compatibility limits](../engineering/protocol/README.md)
- [Building from source and development](development.md)
- [Downloads](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases), [project repository](https://github.com/brewpi-remix/brewpi-emulator-rmx), and [issue tracker](https://github.com/brewpi-remix/brewpi-emulator-rmx/issues).
