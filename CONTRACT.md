# Project contract

## Purpose and scope

Create an independent native C++ Linux emulator for BrewPi Remix integration testing without an Arduino, physical sensors, relays, or brewing equipment. The initial system is one chamber, a five-US-gallon carboy, the current reference host, and the current reference web panel. The [implementation plan](IMPLEMENTATION_PLAN.md) defines the proposed protocol and acceptance scope.

## Independent implementation and MIT licensing

Original project code, tests, tools, configuration examples, fixtures, and documentation use the [MIT License](LICENSE.md). New original source and executable helper files must identify `SPDX-License-Identifier: MIT` in an appropriate comment and retain applicable contributor copyright notices. Formats without comments may use an adjacent provenance/license record; original documentation is covered by the root license without a mandatory header on every page. Standard license text and required interoperability names and values may be recorded; reference implementation code may not be copied, linked, vendored, translated, or adapted into the project.

The restriction applies to controller logic, filters, protocol handlers, thermal modeling, device management, persistence, test helpers, fixtures, generated artifacts, and assets. Write a behavioral specification from observed/source-backed facts, then author original implementations and tests. Do not port source files or recreate their structure through mechanical rewriting. Source-informed development is not represented as a formally separated clean-room process.

This restriction also applies to automated or AI-assisted transformations: translating or paraphrasing a reference routine does not establish independent authorship. It does not forbid standard scientific equations, conventional algorithms implemented independently, common project-layout conventions, or the exact wire names/values required for interoperability. Reference citations document behavioral evidence and do not make the cited source MIT-licensed. The MIT decision is an authorship and incorporation requirement, not a claim that attaching a license proves provenance.

Unmodified BrewPi host and panel programs may run as separate compatibility clients. This does not make their code part of the emulator. General-purpose third-party dependencies require a recorded source/version, license, notices, purpose, and distribution impact before introduction; they retain their own terms. Do not introduce dependencies that require the original emulator implementation to be distributed under a different license. See [licensing provenance](engineering/licenses/README.md).

Apply the plan's permissive-license requirement to incorporated general-purpose library code. External development tools, operating-system libraries, and separate compatibility clients are recorded according to their actual role and retain their own terms; their execution is not a grant to vendor or redistribute them. Confirm original contributions are submitted under MIT by someone entitled to license them, preserve contributor notices, and distinguish external captures/assets from original MIT material. [Licensing provenance](engineering/licenses/README.md) owns the detailed record and review gate, and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) owns the actual incorporation inventory.

## Current stage

Planning, MIT licensing, repository scaffolding, public GitHub repository creation, local Git initialization, and the initial documentation/scaffolding commit and push to `main` are authorized. Emulator implementation remains pending a subsequent explicit user instruction. Directory README files reserve future locations; they are not implemented modules. There is no runnable program, build, test suite, CI, package, or service to install.

The repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx); the initialized local branch is `main`, and `origin` is `https://github.com/brewpi-remix/brewpi-emulator-rmx.git`. Authorization for this initial baseline does not authorize software releases, deployment, reference-repository changes, or Pi installation. Preserve the historical handoff/setup snapshots and reviewed source revisions.

For conflicts, current explicit user instructions take precedence, followed by this contract for scope/licensing, the implementation plan for proposed behavior and acceptance, and supporting guides for navigation and workflow. HANDOFF.md and SETUP.md are historical snapshots, not instructions to reuse source or restart preparation. A review or milestone checklist does not approve implementation.

## Evidence and compatibility

Distinguish source inference, local checks, native Linux execution, actual host/panel integration, and Raspberry Pi qualification. A planning document or directory structure is not runtime evidence. Never claim firmware arithmetic equivalence or physical controller qualification from plausible simulated behavior.

Protocol field names/types, device identities, framing, and supported workflows require exact compatibility. Independent controller numerics and thermal parameters may approximate the reference where the plan identifies that boundary. Record deliberate deviations and deferred features rather than silently claiming completeness.

## Documentation conventions

Write each prose paragraph and each prose list item on one physical line, with blank lines between paragraphs. Prefer Oxford commas. Use relative links within this repository and revision-pinned GitHub links for external source citations. Historical handoff/setup snapshots may retain machine-specific reference paths. Keep generated outputs and local machine state out of tracked project content.
