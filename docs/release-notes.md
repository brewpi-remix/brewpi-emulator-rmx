# BrewPi Emulator Remix 0.0.1 — Initial Release

Introducing BrewPi Emulator Remix, a native virtual controller for BrewPi Remix on Linux, macOS, and Windows. Run a simulated fermentation chamber alongside the separately installed BrewPi Remix host and web panel. No Arduino, USB serial adapter, sensors, or relays are required.

This initial release provides:

- A serial pseudo-terminal on Linux and macOS, or an operator-provisioned virtual COM pair on Windows. The web panel communicates through the BrewPi host.
- Virtual temperature probes and outputs, chamber heating and cooling, fermentation heat, and configurable room-temperature cycles.
- Persistent controller settings and optional checkpoints for continuing a simulation with its matching saved controller state.
- Terminal and graphical LCD displays, with simulated rotary, pushbutton, and door controls.
- Real-time or accelerated simulation; host profiles and timestamps continue to use wall time.

Binary packages target 64-bit Debian 12 on amd64 and ARM64, macOS 27 on Apple Silicon, and Windows 11 x64. Linux and Windows distributions are unsigned. The macOS executable uses Developer ID signing and Apple notarization. Verify the supplied checksums and retain the required notice/source companions described in the [package guide](release.md); checksums establish integrity, not publisher authentication.

Windows requires a separately installed compatible virtual COM provider and the Microsoft Visual C++ v14 x64 runtime. The supported HHD provider has its own licensing restrictions. Its virtual-port driver can stall partial bulk reads despite a finite timeout; the [Windows guide](windows.md) explains the supported client read pattern and explicit pair record. Native Windows BrewPi host/panel execution is not included.

The optional graphical LCD requires separately installed Python 3.9 or later with a working `tkinter` extension, Tcl/Tk, and a local graphical session. Headless and terminal emulator operation require neither Python nor Tcl/Tk. The Python readiness helper and separately installed BrewPi host have their own interpreter requirements. No COM driver, interpreter, toolkit, or runtime-library bundle is included.

The emulated firmware personality is Uno/RevC. The Arduino I2C bench guide describes a separate physical setup. The emulator follows the selected Arduino firmware's documented behavior, including its quirks. Nine hardware/build-dependent characterization cases remain unresolved compatibility limits; software validation does not establish physical Pi or Arduino qualification. The supplied Linux systemd example does not activate a service automatically.

Original emulator code, helpers, tests, and documentation are independently authored under the [MIT License](../LICENSE.md). External compiler/runtime contributions retain their separate terms, described in the [component notices](../THIRD_PARTY_NOTICES.md).

## Further information

- [Installation and operating guide](operation.md)
- [macOS installation and use](macos.md)
- [Windows installation and use](windows.md)
- [Simulation scenarios and configuration](../config/README.md)
- [Protocol reference and compatibility limits](../engineering/protocol/README.md)
- [Building from source and development](development.md)
- [Downloads](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases), [project repository](https://github.com/brewpi-remix/brewpi-emulator-rmx), and [issue tracker](https://github.com/brewpi-remix/brewpi-emulator-rmx/issues).
