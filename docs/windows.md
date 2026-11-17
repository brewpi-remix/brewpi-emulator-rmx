# Windows operation and source builds

The native Windows target is Windows 11 x64. The emulator opens one existing virtual COM endpoint; the serial client opens its paired endpoint. The emulator does not create ports or install drivers. Its controller, simulation, serial protocol, and local controls use the same independently authored MIT implementation as the POSIX executable. This does not provide a native Windows port of the BrewPi host or panel.

## Prerequisites

Use an operator-provisioned virtual null-modem pair. The supported identity profile is HHD Free Virtual Serial Ports `7.35.01.1760`, with HHD virtual-device hardware ID `HHDVIRT\UniversalSerial4`, provider `HHD Software Ltd.`, and driver version `7.35.0.1753`. HHD is a separate proprietary prerequisite, excluded from the emulator archive. Its free edition prohibits commercial, government, and military use; obtain suitable external licensing before those uses. Do not disable Secure Boot, Memory Integrity, antivirus, or driver-signing policy to run the emulator.

The executable uses the external Microsoft Visual C++ v14 x64 runtime. Install it separately from Microsoft's official distribution when required. Python is unnecessary for headless or terminal operation. Readiness checks require Python `3.9` or later; the optional graphical LCD also requires a working `tkinter` extension and Tcl/Tk. Python, Tk, the COM provider, and runtime DLLs are not bundled.

## Build and launch

Use Visual Studio 2026 with its x64 C++ tools and Windows SDK, CMake `4.2` or later for that generator, and Python `3.9` or later for development tests:

```powershell
cmake -S . -B build-windows -G "Visual Studio 18 2026" -A x64
cmake --build build-windows --config Release
Push-Location build-windows
ctest -C Release --output-on-failure
Pop-Location
```

For a binary archive, extract it into a private directory. Extracted files inherit that directory's Windows permissions. The executable is `bin\brewpi-emulator-rmx.exe`, helpers are under `libexec\brewpi-emulator-rmx\`, and the standalone guide and notices are under `share\doc\brewpi-emulator-rmx\`. The Windows executable is unsigned. Compare `Get-FileHash -Algorithm SHA256` with the accompanying `SHA256SUMS` before extraction; checksums establish integrity, not publisher authentication. Windows or organizational policy can require per-application consent or prohibit unsigned execution. Follow that policy; the package does not weaken it.

Provide explicit `--serial`, `--serial-pair`, and writable `--state` arguments. COM names are canonical uppercase names such as `COM1` or `COM12`. Paths containing spaces or Unicode characters must be quoted. The application decodes its command line as Unicode and does not expand shell variables or `~` inside configuration values.

| Argument | Meaning |
| --- | --- |
| `--serial COMn` | Required selected emulator endpoint from the pair record. |
| `--serial-pair PATH` | Required operator-provisioned pair record. |
| `--state PATH` | Required writable local-drive controller store. |
| `--profile revc` or `--profile i2c` | Controller personality; default `revc`. See the [profile pin map and saved-state rules](operation.md#connect-brewpi-remix). |
| `--scenario PATH` | Read-only physical scenario input, excluded when resuming. |
| `--speed FACTOR` | Simulated pacing from `0` through `1000`; default `1`, or the scenario/checkpoint value. |
| `--checkpoint PATH` | Save a checkpoint on eligible orderly shutdown. |
| `--resume PATH` | Restore a checkpoint with its matching controller store. |
| `--lcd MODE` | Local presentation; default `off`. |
| `--lcd-keep-on` | Disable presentation dimming. |
| `--help`, `--version` | Show usage or the application version. |

The pair record is an ordinary UTF-8 JSON file with these fields. Replace both COM names and instance IDs with those of the operator-provisioned pair; the other identity fields must match the supported profile:

```json
{
  "format": "brewpi-emulator-serial-pair-v1",
  "provider": "hhd-vspt",
  "provider_version": "7.35.01.1760",
  "endpoints": [
    {"port": "COM1", "instance_id": "ROOT\\PORTS\\0000", "hardware_id": "HHDVIRT\\UniversalSerial4", "driver_provider": "HHD Software Ltd.", "driver_version": "7.35.0.1753"},
    {"port": "COM2", "instance_id": "ROOT\\PORTS\\0001", "hardware_id": "HHDVIRT\\UniversalSerial4", "driver_provider": "HHD Software Ltd.", "driver_version": "7.35.0.1753"}
  ]
}
```

The application checks both recorded devices against standard Windows device properties and opens only the selected verified virtual interface, exclusively. Missing, reassigned, physical, unsupported, and busy endpoints fail without scanning or falling back to another port. The peer relationship is operator-provisioned information: matching device identities do not prove that the provider currently wires those devices together. Replace and review the record after reprovisioning the pair.

For example, from the extracted directory:

```powershell
.\bin\brewpi-emulator-rmx.exe --serial COM1 --serial-pair "C:\Users\example\pair.json" --state "C:\Users\example\AppData\Local\brewpi-emulator\controller.json" --lcd terminal
```

Configure the external serial client for the opposite endpoint:

```ini
port = COM2
altport = None
```

Use `57600` baud, eight data bits, no parity, and one stop bit. Client open/close and control-line changes do not invent controller resets or serial replies. `R` remains an explicit controller restart. A client's input purge can intentionally discard queued startup bytes.

## Readiness, controls, and shutdown

Use `--lcd off`, `--lcd terminal`, `--lcd gui`, or `--lcd auto`. Terminal controls require an attached Windows console with at least 23 columns and 15 rows. Type a command and press `Enter` to submit it; `press` is the rotary pushbutton action. GUI modes show the four-by-twenty LCD, physical heater/cooler/fan/light indicators, and an open/closed door icon. Counterclockwise and clockwise buttons flank the green encoder ring, with the press button in its center; full action names appear in tooltips. Indicators show physical load activation (`On`, `Off`, or `N/A` when no load is modeled), including custom wiring and polarity. Terminal presentation shows the same equipment and door states as text. GUI modes fall back to terminal presentation, then headless operation, when unavailable. See the [control reference](operation.md#local-rotary-and-door-controls).

The readiness helper uses the state path, selected COM endpoint, and actual process PID:

```powershell
python .\libexec\brewpi-emulator-rmx\wait-ready.py --serial COM1 --state "C:\Users\example\AppData\Local\brewpi-emulator\controller.json" --pid 1234 --timeout 10
```

It opens neither COM endpoint. The state path's `.ready` publication is private to the current account and names a private local message pipe. A fresh challenge verifies the live publication generation and endpoint; the PID alone is not authentication. A stale record after abrupt termination cannot answer the challenge. Ownership sidecars and the final inactive readiness record can remain beside state files; do not edit them while an instance owns them.

Stop client traffic, consume pending replies, and use `Ctrl+C`, `Ctrl+Break`, or the graphical window's close control for orderly shutdown. Closing a console window, ending the process in Task Manager, or terminating its process abruptly does not guarantee a checkpoint. Use explicit writable paths with `--checkpoint` and `--resume`; checkpoint continuation requires the matching saved controller store and drained application output. OS-buffer acceptance does not prove peer consumption. Cross-OS checkpoint migration and universal power-loss durability are not claimed.

## Troubleshooting

The supported HHD driver can leave a timed bulk read pending when fewer bytes arrive than the requested count, despite a finite total read timeout. External serial clients should read one byte at a time while assembling a bounded protocol line, or consume only bytes already reported as available. With pySerial, use `read(1)` with a finite `timeout` and an overall response deadline; do not use an arbitrary `read(4096)` to wait for a short reply. This provider limitation also occurs without the emulator; it does not require an LCD fallback.

If device checks fail, verify the provider profile, both instance IDs, COM names, and the actual pair wiring. Close other users of the selected endpoint. Do not substitute a physical port or disable security policy. State-file errors can indicate an existing owner, a read-only or busy file, a hard link, a reparse point, an ambiguous path, or a missing writable directory. Use an explicit local-drive state path outside the installed package. If GUI startup fails, check the external Python interpreter and its native Tk installation; headless and terminal operation do not require Python.
