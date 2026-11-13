# Planned architecture

Status: proposed; no modules have been implemented. The [implementation plan](../IMPLEMENTATION_PLAN.md) owns design details and acceptance criteria.

| Boundary | Planned responsibility |
| --- | --- |
| Serial transport | Linux PTY, stable path, buffering, backpressure, and connection lifecycle. |
| Protocol adapter | Compatible command parsing, response schemas, and unsolicited messages. |
| Device registry | Stable virtual inventory, assignments, raw/calibrated readings, and pin routing. |
| Controller | Independently implemented modes, filters, control demand, timed states, and diagnostics. |
| Thermal plant | Beer/chamber energy balances, room conditions, physical loads, and fermentation heat. |
| Simulation clock | Deterministic simulated ticks, wall-clock pacing, pause, and acceleration. |
| Persistence/scenarios | Durable configuration, stable identities, repeatable initial conditions, and coherent checkpoints. |

All implementation will be original C++17 suitable for Linux, with CMake proposed for the build. Arduino/AVR components and Fuscus modules are behavioral references only. Actual BrewPi host and panel processes are separate integration clients.

The completed [milestone 1 contract](protocol/behavioral-contract.md) freezes firmware-faithful action/reaction, including bugs; no module may correct a documented quirk by default. Persistence mirrors the firmware's actual partial/write side effects rather than promising every live change is durable. The [findings register](protocol/firmware-findings.md) separates deterministic requirements from hardware/artifact characterization. The external thermal plant remains independent physical modeling. No incorporated third-party JSON/controller library is selected for the initial foundation.
