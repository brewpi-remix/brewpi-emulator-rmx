# Architecture

Status: milestones 1–3 are published; milestone 4 isolated host/panel integration is reviewed and authorized for commit and push to main. The [implementation plan](../IMPLEMENTATION_PLAN.md) owns design details and acceptance criteria.

| Boundary | Planned responsibility |
| --- | --- |
| Serial transport | Linux PTY, stable path, buffering, backpressure, and connection lifecycle. |
| Protocol adapter | Compatible command parsing, response schemas, and unsolicited messages. |
| Device registry | Stable virtual inventory, assignments, raw/calibrated readings, and pin routing. |
| Controller | Independently implemented modes, filters, control demand, timed states, and diagnostics. |
| Thermal plant | Beer/chamber energy balances, room conditions, physical loads, and fermentation heat. |
| Simulation clock | Deterministic simulated ticks, wall-clock pacing, pause, and acceleration. |
| Persistence/scenarios | Durable configuration, stable identities, repeatable initial conditions, and coherent checkpoints. |

The implemented foundation is original C++17 with a CMake build, suitable for Linux and exercised on macOS for development. Engine token events/state and saved maps live in src/engine.cpp; src/main.cpp owns the PTY lifecycle; src/storage.cpp owns host-file integrity/locking; src/json.cpp serves only strict local store/test envelopes. src/controller.cpp owns controller transitions, PID/peak actions, LCD, scheduling, and full-state checkpoint reconstruction; src/dynamics.cpp owns the independent delay-state filter realization and external energy/probe model. The modules use original native maps/delay matrices/state snapshots without importing reference structures. Arduino/AVR components and Fuscus modules are behavioral references only. Actual BrewPi host and panel processes are separate integration clients.

The completed [milestone 1 contract](protocol/behavioral-contract.md) freezes firmware-faithful action/reaction, including bugs; no module may correct a documented quirk by default. Persistence mirrors the firmware's actual partial/write side effects rather than promising every live change is durable. The [findings register](protocol/firmware-findings.md) separates deterministic requirements from hardware/artifact characterization. The external thermal plant remains independent physical modeling. No incorporated third-party JSON/controller library is selected for the initial foundation.

The original opt-in milestone 4 harness stays outside the native executable and standard CTest entry points. It launches external reference clients in a disposable network-disabled Linux environment, drives their real interfaces, and retains raw captures in ignored evidence directories. The [integration review](development/milestone-4-review.md) labels interface coverage and preserves the boundary between application compatibility, source-informed firmware behavior, and future physical/Pi qualification.
