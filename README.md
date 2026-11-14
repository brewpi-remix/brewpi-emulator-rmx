# BrewPi Emulator Remix

BrewPi Emulator Remix (`brewpi-emulator-rmx`) is an independent native C++ Linux emulator under development for hardware-free integration testing of BrewPi Remix. It exposes a stable pseudo-terminal serial path and models a fermentation chamber containing a carboy with five US gallons of beer, responding to the existing host and web panel.

**Status: milestones 1–5 published; cross-milestone fixes are reviewed and authorized for commit and push to main.** The owner selected isolated Debian 12 ARM64 Linux software qualification. The [operating guide](docs/operation.md) covers staged installation, readiness, private paths, lifecycle, and recovery; the [milestone 5 review](engineering/development/milestone-5-review.md) separates native/runtime evidence from unqualified physical Pi, actual systemd activation, and nine firmware-characterization cases. No release, live deployment, or CI workflow exists.

The public repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx). The local repository is initialized on `main`, with `origin` set to `https://github.com/brewpi-remix/brewpi-emulator-rmx.git`. The owner authorized publication of the reviewed milestone 2 implementation, tests, fixtures, and supporting documentation to `main`. After milestone 3 implementation and review, the owner authorized committing and pushing its reviewed implementation, tests, and supporting documentation to `main`. The owner subsequently authorized milestone 4 in an isolated host/panel test setup, with a stop for review before committing or pushing. After review and fixes, the owner authorized committing and pushing the reviewed milestone 4 setup, tests, and supporting docs to `main`. The owner subsequently authorized milestone 5 using the isolated Debian 12 ARM64 Linux environment, stopping for review before committing or pushing. After review and fixes, the owner authorized committing and pushing the reviewed milestone 5 target qualification, operating guidance, tests, and supporting docs to main, preserving Arduino behavior and independent MIT licensing.

## Project direction

The emulator will independently implement the observed communications and relevant controller characteristics of BrewPi. Firmware and historical Fuscus source are behavioral references only; their implementation code, translated routines, tables, and assets must not be incorporated. Existing BrewPi host and panel processes may be used as external compatibility clients.

When a question arises, Arduino firmware action/reaction is authoritative, including bugs. The [behavioral contract](engineering/protocol/behavioral-contract.md) and [findings register](engineering/protocol/firmware-findings.md) replace earlier proposed improvements with firmware-faithful expectations. Undefined/hardware-dependent cases are explicit characterization obligations, not invented passing results.

Implemented development capabilities include device discovery and assignment, stable virtual sensor identities, reactive beer/chamber/room temperatures, fermentation heat, heater/cooler behavior, persistent settings, repeatable scenarios, and optional accelerated simulation time. Host fermentation profiles and chart timestamps continue to use wall time.

## Start here

- [Project contract](CONTRACT.md): scope, independent implementation, MIT licensing, and authorization boundaries.
- [Implementation plan](IMPLEMENTATION_PLAN.md): source-backed compatibility review, architecture, milestones, risks, and proposed acceptance checks.
- [Protocol contract and fixtures](engineering/protocol/README.md): defaults/units, diagnostic metadata, firmware quirks, and original specification vectors.
- [Engineering index](engineering/README.md): architecture, development, protocol, and licensing records.
- [Operator documentation](docs/README.md): documentation status and planned coverage.
- [Contributing](CONTRIBUTING.md) and [security reporting](SECURITY.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/` | Original C++17 transport, controller, sensor histories, thermal model, clock, and persistence. |
| `tests/` | Independent protocol, model arithmetic, controller/thermal/clock, regression, and real PTY/process tests. |
| `cmake/` | Future build configuration helpers. |
| `config/` | Original active-fermentation and daily-room scenario examples. |
| `scripts/` | Original nonconsuming endpoint-readiness helper. |
| `systemd/` | Original optional per-instance service example; no activation. |
| `engineering/` | Design, development, protocol, and provenance documentation. |
| `docs/` | Build, integration, staged-install, and operating guidance. |
| `.github/` | Contribution templates; no active CI or publication automation. |

## License and provenance

Original project code and documentation are licensed under the [MIT License](LICENSE.md), copyright 2026 Lee Bussy, with contributor notices retained as applicable. [Third-party notices](THIRD_PARTY_NOTICES.md) distinguish behavioral references from incorporated dependencies, and the [provenance review gate](engineering/licenses/README.md#review-gate) covers original contributions, dependencies, generated material, and external captures. No reference implementation or third-party runtime dependency has been incorporated. The license identifies the terms for original work; it does not relicense referenced software or substitute for an authorship review.

[HANDOFF.md](HANDOFF.md) and [SETUP.md](SETUP.md) preserve historical preparation snapshots and machine-specific reference paths. The handoff's suggestion to reuse firmware code is superseded by the contract and revised plan. Repository creation and Git initialization occurred after those snapshots. No software release has been created.

The [milestone 4 guide](docs/milestone-4.md) and [review record](engineering/development/milestone-4-review.md) cover isolated real host/panel workflows and their limits.

The [cross-milestone review](engineering/development/cross-milestone-review.md) records end-to-end findings, fixes, validation, and remaining qualification limits. After review, the owner authorized committing and pushing the reviewed cross-milestone fixes, tests, and supporting docs to main, preserving Arduino behavior and independent MIT licensing. This source publication does not authorize a release or deployment.
