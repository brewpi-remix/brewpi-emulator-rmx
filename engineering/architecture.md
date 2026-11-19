# Architecture

The emulator separates controller behavior from the modeled equipment and native transport: PTYs on Linux/macOS and an operator-provisioned virtual COM pair on Windows. All implementation modules are independently authored MIT work; external compiler/runtime contributions retain their own terms.

| Module | Responsibility |
| --- | --- |
| `main.cpp`, `storage.cpp`, and `storage_windows.cpp` | Platform startup, wall pacing, file ownership/locks, atomic state/checkpoint writes, and process lifecycle. |
| `windows_serial.cpp`, `windows_ready.cpp`, `windows_channel.cpp`, and `windows_console.cpp` | Verified virtual COM access, private readiness/viewer channels, and Windows console handling. |
| `engine.cpp` and `controller.cpp` | Firmware-style command parsing, registry/live state, persistent records, control evaluation, clock scheduling, and LCD shadow. |
| `dynamics.cpp` | Independent beer/chamber/room energy model, virtual probes, noise, fermentation heat, and modeled physical inputs/outputs. |
| `controls.cpp` | Firmware-style menu setters, temperature candidates, confirmation, timeout, cancellation, and door input. |
| `lcd.cpp` | Terminal rendering, private viewer IPC, fallback, dimming, and viewer lifecycle. |
| `json.cpp` | Native scenario/store/checkpoint JSON handling, separate from firmware serial parsing. |

The serial client is the sole reader of the controller's client-side serial endpoint. Local display/control traffic uses private IPC; the viewer sends bounded action intents and the engine owns mutations. Mode rotation applies its setter immediately, while temperature rotation changes a candidate until confirmation. Cancellation retains mutations already performed. Checkpoints preserve active menu and logical encoder state, including timeout origins and queued decoded input, subject to the serial-drain conditions below. The controller keeps live and saved values distinct according to firmware semantics.

The engine models bounded nominal UART receive/transmit queues. Full transmit buffers suspend the synchronous writer while peripheral clocks and the plant advance; menu, display, and sensor waits also suspend ordinary controller work. Native input admission and completed-output backpressure are separate host transport boundaries. Checkpoints require drained wire/transmit state and no suspended writer; they do not serialize a native call stack. See [menu execution and serial buffering](protocol/controller.md#menu-execution-and-serial-buffering) for ordering, checkpoint restrictions, and timing limits.

Simulated time advances physics and controller scheduling. Serial-token deadlines, display activity, and host profile/chart time remain wall-clock based. Process restart loads saved controller state with a fresh external plant; explicit checkpoint continuation restores coherent plant/controller histories. Serial `R` restarts controller state while retaining the running plant.

See the [wire contract](protocol/behavioral-contract.md), [controller reference](protocol/controller.md), and [operating guide](../docs/operation.md).

The local equipment view is a passive projection of modeled physical load kinds, configured pins, polarity, and retained electrical latches. It aggregates multiple loads of one kind without deriving activation from controller state or logical assignments. GUI frames carry the four heater/cooler/fan/light values through private IPC; the serial protocol and controller checkpoint schema are unchanged. Original vector shapes are rasterized into antialiased PNGs in memory using Python's standard library, then displayed as Tk canvas and button images. A bounded cache reuses equipment images across redraws. No icon library, external image asset, or symbol font is bundled.
