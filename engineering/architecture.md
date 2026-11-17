# Architecture

The emulator separates controller behavior from the modeled equipment and its POSIX transport. All modules are original MIT work.

| Module | Responsibility |
| --- | --- |
| `main.cpp` and `storage.cpp` | PTY ownership/raw framing, wall pacing, file locks, atomic state/checkpoint writes, and process lifecycle. |
| `engine.cpp` and `controller.cpp` | Firmware-style command parsing, registry/live state, persistent records, control evaluation, clock scheduling, and LCD shadow. |
| `dynamics.cpp` | Independent beer/chamber/room energy model, virtual probes, noise, fermentation heat, and modeled physical inputs/outputs. |
| `controls.cpp` | Staged local menu, confirmation, cancellation, and door input. |
| `lcd.cpp` | Terminal rendering, private viewer IPC, fallback, dimming, and viewer lifecycle. |
| `json.cpp` | Native scenario/store/checkpoint JSON handling, separate from firmware serial parsing. |

The serial host is the sole consumer of the controller PTY. Local display/control traffic uses private IPC; the viewer sends bounded action intents and the engine owns mutations. Draft menu state is transient and excluded from checkpoints. The controller keeps live and saved values distinct according to the firmware semantics.

Simulated time advances physics and controller scheduling. Serial-token deadlines, display activity, and host profile/chart time remain wall-clock based. Process restart loads saved controller state with a fresh external plant; explicit checkpoint continuation restores coherent plant/controller histories. Serial `R` restarts controller state while retaining the running plant.

See the [wire contract](protocol/behavioral-contract.md), [controller reference](protocol/controller.md), and [operating guide](../docs/operation.md).

The local equipment view is a passive projection of modeled physical load kinds, configured pins, polarity, and retained electrical latches. It aggregates multiple loads of one kind without deriving activation from controller state or logical assignments. GUI frames carry the four heater/cooler/fan/light values through private IPC; the serial protocol and controller checkpoint schema are unchanged. The original procedural icon strokes are drawn locally with Tk canvas/native button images; no icon library, image asset, or symbol font is bundled.
