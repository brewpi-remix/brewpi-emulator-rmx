# Operating guide

## Installation

Binary archives support amd64 and ARM64 Linux with the Debian 12 runtime baseline. Use `uname -m` to identify your machine: `x86_64` selects amd64; `aarch64` selects ARM64. Compatible operating-system loader and C/C++ libraries are required, including `libc6`, `libstdc++6`, and `libgcc-s1`. A prebuilt executable needs no compiler or CMake.

Download the matching binary archive, `SHA256SUMS`, and the required license/source companions described in [package contents](release.md). From the download directory, verify the listed files with `sha256sum --ignore-missing --check SHA256SUMS`. Every file must match its listed hash. Obtain missing companion files before treating the complete distribution as verified. The `ignore-missing` option skips unselected release files; confirm that every archive being used reports `OK` and obtain the required companions separately. Checksums detect changed bytes; they are not signatures.

Extract into a new directory, replacing `ARCHIVE.tar.gz` with the downloaded binary archive:

```sh
mkdir package
tar -xzf ARCHIVE.tar.gz -C package
```

The archive's named top-level directory contains `bin/`, `libexec/`, and `share/`. Keep that layout together so the graphical helper can be found. Run its `bin/brewpi-emulator-rmx` directly, or add that bin directory to `PATH`. The archive contains no installer or automatic service activation. For source builds and staged installation, see [development](development.md).

## Start an instance

Run as an unprivileged user. The BrewPi host needs access to the same PTY namespace and paths; using the same account avoids permission changes. Give every instance its own runtime and state directories. Set existing directory permissions explicitly; `umask` affects newly created paths only.

```sh
umask 077
mkdir -p "$HOME/.local/run/brewpi-emulator" "$HOME/.local/state/brewpi-emulator"
chmod 700 "$HOME/.local/run/brewpi-emulator" "$HOME/.local/state/brewpi-emulator"
brewpi-emulator-rmx --serial "$HOME/.local/run/brewpi-emulator/serial" \
  --state "$HOME/.local/state/brewpi-emulator/controller.json" --speed 1
```

The serial path is a symlink to an allocated PTY. It must not already exist. Keep durable controller state outside temporary runtime storage such as `/run`. Do not use a scenario input as an output or lock path; aliases through symlinks or hardlinks are rejected too.

## Connect BrewPi Remix

Configure the host's `port` as the exact `--serial` path, `altport=None`, and optionally `startupDelay=0`. The web panel communicates through the host's socket. Do not run another serial reader while the host owns the `port`; that can consume its responses.

A new absent state file represents erased controller configuration. The `W3` startup warning is expected. Use the panel's factory reset, which sends `E`, then discover and assign virtual probes and outputs. Initialization does not create automatic assignments. The virtual hardware inventory and controller defaults are in the [protocol reference](../engineering/protocol/README.md).

The default RevC physical assignments are:

| Discovered address or pin | Physical role |
| --- | --- |
| `28A10100000001E6` | Beer probe. |
| `28A1010000000204` | Chamber/fridge probe. |
| `28A101000000035A` | Room/ambient probe. |
| Pin 5 | Heater, 25 W. |
| Pin 6 | Cooler, 60 W of heat removal. |
| Pin 2 | Light output; no added heat by default. |
| Pin 19 | Fan output; no added heat by default. |

Choose `--profile revc` (the default) or `--profile i2c` at startup. Both selected prebuilt Uno personalities report firmware revision `da7e14a9`; RevC reports shield `s=2`, and I2C reports `s=5`. This selects the emulated Uno firmware identity and pin map; the local LCD presentation is shared and does not drive a physical display bus.

| Profile | Serial identity `s` | Probe bus | Output discovery order | Default heater / cooler / light / fan |
| --- | --- | --- | --- | --- |
| `revc` | `2` | A4 (`18`) | 2, 5, 6, 19 | 5 / 6 / 2 / 19 |
| `i2c` | `5` | A0 (`14`) | 5, 6, 2, 10 | 6 / 5 / 2 / 10 |

For an I2C bench comparison, add `--profile i2c` to the startup command and use a new dedicated `--state` path. Probe ROMs, control logic, serial grammar, and thermal parameters remain shared. Explicit scenario `physical_loads` replace the profile's default load wiring without being remapped. Assign discovered pins for the selected profile through the host after initialization.

Stores and checkpoints record the selected `profile`. Always supply `--profile i2c` when restarting or resuming an I2C instance; the option defaults to RevC even when reading saved files. A profile mismatch fails locally before opening the serial interface, without rewriting assignments. Existing files without profile metadata are interpreted as RevC. There is no automatic profile conversion: retain existing stores/checkpoints, and initialize a separate state file for another profile. These checks protect emulator files; they do not add Arduino serial diagnostics or stricter digital-pin validation.

RevC controller stores retain format `brewpi-emulator-store-v1`. I2C stores use `brewpi-emulator-store-v2` with an explicit `profile: i2c` tag, so older RevC-only executables reject them. An untagged V2 store is invalid, not a legacy RevC file. Checkpoints embed the corresponding store and record the profile too.

Use the discovered active-low/inverted setting for the default outputs. Function assignments do not move probes or change physical load wiring. Door input uses pin 4, which is not included in ordinary output discovery; local door commands change that modeled physical input. The default contact is asserted LOW for I2C (use inversion `x=1`) and HIGH for RevC (use `x=0`); the configured inversion flag remains effective. Scenarios can change physical loads and the door pin.

After replacing the emulator process, reopen or restart the host against the new serial path. An existing open descriptor still points to the old PTY. USB discovery, USB reset, firmware flashing, and automatic host reconnection are not provided.

## Command-line options

| Option | Meaning |
| --- | --- |
| `--serial PATH` | Published PTY symlink. Default: `/run/brewpi-emulator/chamber1/serial`. |
| `--state PATH` | Persistent controller store. Default: `/var/lib/brewpi-emulator/chamber1/controller.json`. |
| `--profile revc` or `--profile i2c` | Uno shield identity, probe bus, output inventory, and default virtual load wiring. Default: `revc`. Use the same profile for saved state and checkpoint resume. |
| `--scenario PATH` | Read a JSON physical scenario at startup. Mutually exclusive with `--resume`. |
| `--speed FACTOR` | Wall-time pacing factor from 0 through 1000. Default: 1. Zero pauses scheduled simulated time. |
| `--checkpoint PATH` | Write a coherent continuation snapshot during clean shutdown. |
| `--resume PATH` | Start from a checkpoint. Use its matching saved controller state. |
| `--lcd off` | Headless operation; also the default when `--lcd` is omitted. |
| `--lcd terminal` | Unicode terminal LCD with local controls. |
| `--lcd gui` or `--lcd auto` | Try the graphical LCD, then fall back to terminal or headless operation. |
| `--lcd-keep-on` | Disable local LCD dimming. |
| `--help` | Print command-line usage. |
| `--version` | Print application version. Serial `n` identifies the emulated firmware separately. |

## Optional local LCD

The local LCD shows the twenty-column, four-row controller screen. The terminal presentation requires a foreground UTF-8 terminal with a single-cell degree glyph and at least 23 columns by 15 rows. Unsupported terminals display a read-only screen. Headless and terminal operation need no Python or Tcl/Tk.

The equipment strip shows the modeled heater, cooler, fan, and chamber light. A red flame denotes the heater, a pale-blue snowflake denotes the cooler, and a circle/slash over the fan denotes off. Labels distinguish `On`, `Off`, and `N/A` (no modeled load or unavailable display data). These indicators read physical load wiring and electrical latches, including custom `physical_loads` and polarity; they do not infer activation from the controller state or logical function names. Multiple loads of one kind show on when any is active. Indicator reads do not change serial replies, saved state, or thermal behavior.

The encoder has a press symbol in its center, with counterclockwise and clockwise arrow buttons on either side. Hover or keyboard focus exposes the full action names. The door button shows the physical open/closed door icon; clicking it toggles the modeled door. The terminal presents the same equipment and door states as text beneath the unchanged LCD, followed by the existing typed commands. A timestamped read-only terminal shows the equipment states without interactive controls.

The graphical LCD requires the installed `lcd-viewer.py` helper, `python3` on `PATH` selecting Python 3.9 or later, working `tkinter`/`_tkinter`, Tcl/Tk 8.6 or later, and a local graphical session. Check that interpreter's setup with `python3 -m tkinter`. Python, Tcl/Tk, fonts, and desktop software are supplied separately. GUI failure falls back to the terminal, then headless mode. Closing the GUI requests normal emulator shutdown.

## Local rotary and door controls

In an interactive terminal, type a command and press `Enter`:

| Command | Action |
| --- | --- |
| `cw` | Turn the knob clockwise. |
| `ccw` | Turn the knob counterclockwise. |
| `press` | Press the knob/pushbutton. |
| `door open` | Open the modeled physical door. |
| `door close` | Close it. |
| `help` | Display command help. |

`Enter` submits text; only `press` represents a pushbutton action. The GUI provides knob and door controls. Focus the knob and use `Left`/`Right` to turn and `Return`/`Space` to press; the door button is also keyboard accessible. Press opens the menu; turn to select an item, and press to enter or confirm it. Rotating through modes changes and saves the live mode immediately, including disabling targets when off is selected. A mode timeout restores the previous mode but does not restore disabled targets. Entering a beer/fridge temperature editor selects that constant mode immediately; rotation changes its displayed candidate, and confirmation quantizes and saves the target even without rotation. Temperature timeout leaves the previous target and the selected mode. Menu timeout uses ten firmware-clock seconds since the last logical change, with the source tick boundary; acceleration scales it, and at `--speed 0` it remains paused. Serial replies and ordinary sensor/control/output updates wait until the menu exits; the physical plant and firmware clock continue at the selected speed, and existing output levels remain latched. After UI initialization, logical encoder events received during another firmware wait are retained for the next eligible UI boundary. Events during startup display initialization are unavailable. Undefined invalid-mode lookup remains an explicit local fidelity limit rather than a normalized mode. Door input affects controller behavior only through the configured devices and modeled plant.

Text dims after more than sixty wall seconds without interaction. A deliberate turn or press wakes the screen and performs the action. `--lcd-keep-on` disables dimming. The terminal prompt stays readable. Local controls use private IPC and do not open another serial reader. Active menu state, retained logical encoder state, and queued serial bytes survive checkpoints. Presentation failure or close does not silently cancel the firmware menu or revert its live/saved changes. The emulator-only `cancel` action closes the menu without rolling back those changes. Physical encoder bounce, sub-grid blink phase, AVR UART overflow, and electrical display timing remain outside this logical menu comparison.

During a modeled controller wait, decoded serial input retains at most 63 bytes in arrival order; further arrivals are silently dropped as in the retained Uno firmware. Input delivered during startup display initialization is discarded before application RX is enabled. After startup or `R`, retry `n` until `N` arrives before sending dependent commands. Unblocked native batches are not capped at 63 bytes. This models software RX buffering at native ingress, not physical wire timestamps, parity/overrun errors, USB buffering, or timed TX-induced controller stalls; see the [UART evidence and limits](../engineering/protocol/firmware-findings.md#artifact-uart-buffering).

## Scenarios and simulation time

The source tree provides `config/active-fermentation.json` for fermentation heat and `config/room-cycle.json` for a daily room cycle. Binary users can create a JSON scenario using the configuration guide and pass its path with `--scenario`. See [scenario fields](../config/README.md) for the supported physical parameters. Scenario files are read without modification.

`--speed 1` uses real-time pacing. Factors such as 10 or 60 accelerate simulated physics and controller time without changing controller thresholds or the integration step. Zero pauses scheduled simulation while synchronous commands and wall-clock token deadlines continue. Host fermentation profiles, CSV dates, and chart timestamps remain wall-clock based; acceleration does not accelerate the host's profile schedule.

The serial parser follows firmware framing and partial-input behavior rather than a general strict JSON API. Incomplete tokens can wait about one wall second. A slow reader defers input/controller work while replies remain queued in order. Drain existing output before expecting another command's response.

Both personalities' hourly display initialization briefly defers serial commands while simulated time continues. A checkpoint taken during this pause retains its pending input; resuming it at `--speed 0` holds dispatch until simulated time advances. Use positive pacing to finish that pause. See the [qualified behavior and timing limits](../engineering/protocol/firmware-findings.md#shared-control-logic-and-i2c-dispatch-timing-limit).

Startup and serial `R` include the selected display's mandatory initialization waits before normal dispatch. Configured probe reset states can add conditional conversion waits; already initialized probes and DATA-only recovery do not acquire a universal 750 ms delay. Startup advances controller and plant time at the selected positive speed; with `--speed 0`, startup completes at 1x before the runtime clock pauses. Resuming a checkpoint already in ordinary sensor or hourly-display blocking retains the pause until positive pacing resumes. See [probe reset scenarios](../config/README.md#fields).

## Stop, restart, and checkpoints

Use `Ctrl-C` or `SIGTERM` for clean shutdown. The process removes only its unchanged owned serial symlink. Firmware-saved settings and device slots survive. A normal new process starts a fresh physical scenario; the serial `R` command restarts controller state while keeping the running plant, and `E` initializes controller configuration. Live values need not equal saved values after every command.

For continuation, provide `--checkpoint` from startup:

```sh
brewpi-emulator-rmx --serial "$HOME/.local/run/brewpi-emulator/serial" \
  --state "$HOME/.local/state/brewpi-emulator/controller.json" \
  --checkpoint "$HOME/.local/state/brewpi-emulator/checkpoint.json"
```

Before stopping, stop the host/client, finish partial commands, and drain serial output. Resume with the same state file and checkpoint:

```sh
brewpi-emulator-rmx --serial "$HOME/.local/run/brewpi-emulator/serial" \
  --state "$HOME/.local/state/brewpi-emulator/controller.json" \
  --resume "$HOME/.local/state/brewpi-emulator/checkpoint.json" \
  --checkpoint "$HOME/.local/state/brewpi-emulator/checkpoint.json"
```

Stopped time is not added. `--speed` can override resumed pacing; `--scenario` cannot replace resumed history. Native snapshots require matching saved state and compatible formats/runtime assumptions; arbitrary cross-version or cross-ABI migration is not provided.

A snapshot with more than 63 queued RX bytes or queued input before application RX enable is incompatible and rejected without clipping, including snapshots from older versions. A corrupt snapshot, state mismatch, active partial-token parse, or queued output prevents a checkpoint/resume operation and produces a local error rather than a fabricated Arduino reply. Failure before file replacement preserves the previous checkpoint. An error after rename can leave new bytes with uncertain durability; inspect the error and file before retrying. There is no automatic rollback or older-snapshot fallback.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Permission denied | Use private directories writable by the emulator account and accessible to the host. Default `/run` and `/var/lib` paths need provisioning; the home-directory example avoids that. |
| Serial path exists or is locked | Check for a running instance. After `SIGKILL`, a stale symlink can remain. Verify the process is gone and instance locks are free, then remove only that instance's symlink. Never delete the PTY character target or another process's paths. |
| Host stops receiving after a restart | Reopen/restart the host against the newly published PTY. |
| No devices or `W3` | Initialize through factory reset, then discover and assign the virtual hardware. |
| A setting changes after restart | Firmware live values and saved values differ by design. Check the command's persistence behavior in the protocol reference. |
| GUI does not open | Check `python3 -m tkinter`, the helper path, and the graphical session; terminal/headless fallback remains available. |
| Terminal controls do not respond | Bring the process to the foreground and check terminal size/encoding. `Enter` submits a command; `press` is the pushbutton action. |
| Checkpoint fails | Drain serial output, complete partial commands, and use the matching state file. Inspect local errors before replacing data. |
| Replies appear delayed | Check queued output and partial tokens. Do not add a competing serial reader. |

The nonconsuming readiness helper can check a trusted endpoint without consuming startup bytes:

```sh
python3 /usr/local/libexec/brewpi-emulator-rmx/wait-ready.py \
  --serial /path/to/serial --pid EMULATOR_PID --timeout 10
```

Use the actual emulator PID and installed helper path. This checks a live PID and owned raw PTY; it does not authenticate their relationship, initialize configuration, or isolate other same-account code.

## Service example and limits

The inert per-instance systemd example is installed under `share/brewpi-emulator-rmx/systemd`. It assumes a `brewpi` account, private runtime/state directories, shared PTY visibility, and Python for its readiness post-check. Installation does not enable the service or copy it into the live unit directory. It does not automatically resume checkpoints or restart the BrewPi host. Actual service activation, boot ordering, physical Pi operation, USB/GPIO behavior, and undefined Arduino memory/bus outcomes are outside the software support claim.

Original work is MIT. Retain [license and component notices](../THIRD_PARTY_NOTICES.md) and the required GNU source companions when distributing binaries.
