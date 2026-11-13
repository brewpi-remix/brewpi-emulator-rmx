# BrewPi Emulator Remix

BrewPi Emulator Remix (`brewpi-emulator-rmx`) is a planned native C++ Linux emulator for hardware-free integration testing of BrewPi Remix. It will expose a stable pseudo-terminal serial path and simulate a fermentation chamber containing a carboy with five US gallons of beer, responding to the existing host and web panel.

**Status: milestone 1 specification and original fixtures completed for review.** No emulator executable, build system, executable test suite, CI workflow, installer, or release exists yet. Implementation remains unapproved. See the [milestone review](engineering/development/milestone-1-review.md) for deliverables and evidence limits.

The public repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx). The local repository is initialized on `main`, with `origin` set to `https://github.com/brewpi-remix/brewpi-emulator-rmx.git`. The initial `main` baseline contains the reviewed plan and scaffolding; publishing it does not approve implementation.

## Project direction

The emulator will independently implement the observed communications and relevant controller characteristics of BrewPi. Firmware and historical Fuscus source are behavioral references only; their implementation code, translated routines, tables, and assets must not be incorporated. Existing BrewPi host and panel processes may be used as external compatibility clients.

When a question arises, Arduino firmware action/reaction is authoritative, including bugs. The [behavioral contract](engineering/protocol/behavioral-contract.md) and [findings register](engineering/protocol/firmware-findings.md) replace earlier proposed improvements with firmware-faithful expectations. Undefined/hardware-dependent cases are explicit characterization obligations, not invented passing results.

Planned capabilities include device discovery and assignment, stable virtual sensor identities, reactive beer/chamber/room temperatures, fermentation heat, heater/cooler behavior, persistent settings, repeatable scenarios, and optional accelerated simulation time. Host fermentation profiles and chart timestamps continue to use wall time.

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
| `src/` | Future original C++ implementation. |
| `tests/` | Future independently authored tests and fixtures. |
| `cmake/` | Future build configuration helpers. |
| `config/` | Future configuration schemas and scenario examples. |
| `scripts/` | Future development and validation helpers. |
| `systemd/` | Future optional Linux service templates. |
| `engineering/` | Design, development, protocol, and provenance documentation. |
| `docs/` | Future operator and integration guidance. |
| `.github/` | Contribution templates; no active CI or publication automation. |

## License and provenance

Original project code and documentation are licensed under the [MIT License](LICENSE.md), copyright 2026 Lee Bussy, with contributor notices retained as applicable. [Third-party notices](THIRD_PARTY_NOTICES.md) distinguish behavioral references from incorporated dependencies, and the [provenance review gate](engineering/licenses/README.md#review-gate) covers original contributions, dependencies, generated material, and external captures. No reference implementation or third-party runtime dependency has been incorporated. The license identifies the terms for original work; it does not relicense referenced software or substitute for an authorship review.

[HANDOFF.md](HANDOFF.md) and [SETUP.md](SETUP.md) preserve historical preparation snapshots and machine-specific reference paths. The handoff's suggestion to reuse firmware code is superseded by the contract and revised plan. Repository creation and Git initialization occurred after those snapshots. No software release has been created.
