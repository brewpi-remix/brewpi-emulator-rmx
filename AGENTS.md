# Repository instructions

Read [CONTRACT.md](CONTRACT.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), and [CONTRIBUTING.md](CONTRIBUTING.md) before working here. The contract records the current scope and supersedes the historical handoff's code-reuse suggestion.

## Current authorization

This is a planning repository with documentation and supporting scaffolding. The owner authorized creation of the public `brewpi-remix/brewpi-emulator-rmx` repository, local initialization on `main`, the HTTPS `origin`, and the initial documentation/scaffolding commit and push to `main`. This records the initial publication scope, not blanket authorization for later commits, pushes, releases, installation, service changes, or reference-repository modifications. Current explicit user instructions control the authorized scope. Do not start emulator implementation until the user explicitly requests it.

## Original implementation

Author emulator code and test helpers independently under MIT. Never copy, vendor, link, translate, or adapt BrewPi/Fuscus implementation code, headers, routines, generated tables, tests, or assets. Required wire identifiers and behavioral facts belong in an independently written specification. Existing host/panel processes are allowed external test clients. Record newly introduced third-party dependencies and notices separately; no dependency is currently incorporated.

Apply the same restriction to automated and AI-assisted rewrites. Standard equations, independently implemented conventional algorithms, and required interoperability values remain permitted. Add MIT SPDX identifiers to new original source/helper files and preserve contributor notices. Follow the [provenance review gate](engineering/licenses/README.md#review-gate) for original work, dependencies, generated outputs, and external captures. Original code remains MIT; third-party material retains its own terms and must be identified separately.

## Layout and changes

Use `src/` for future C++ code, `tests/` for original tests, `cmake/` and `scripts/` for build/development support, `config/` for scenarios/configuration contracts, and `systemd/` for optional service definitions. Keep design in `engineering/` and operator guidance in `docs/`. Preserve unrelated work and historical handoff records. Do not add fake implementation files, executable placeholders, or CI badges that imply a working build.

## Validation and writing

Follow `.editorconfig` and `.clang-format` when applicable. Keep prose paragraphs and prose list items on one physical line. Use Oxford commas and relative documentation links. Validate changed links and whitespace; do not manufacture build/test commands before a build/test system exists. Once implementation is authorized, use meaningful deterministic tests and distinguish host, integration, and Pi evidence. Keep physical controller access outside normal validation.
