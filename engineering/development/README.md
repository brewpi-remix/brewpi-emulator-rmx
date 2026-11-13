# Development guide

Read the [contract](../../CONTRACT.md), [plan](../../IMPLEMENTATION_PLAN.md), and [architecture](../architecture.md) before changes. The current repository contains scaffolding only; there are no build/test commands to run yet.

The public repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx). Local Git is initialized on `main` with `origin` set to `https://github.com/brewpi-remix/brewpi-emulator-rmx.git`. `main` is the base/target for the initial documentation baseline; CI, branch protection, and release policies remain to be established. The initial commit/push does not authorize implementation.

## Planned tooling and layout

The proposed baseline is C++17, CMake, POSIX/Linux APIs, and a system compiler. Linux x86_64 supports host validation; the agreed Raspberry Pi/Linux architecture requires separate qualification. No compiler, CMake, dependency, or CI version has been pinned or installed by this scaffolding task.

Future source belongs in `src/`, independently authored tests in `tests/`, build helpers in `cmake/`, development tooling in `scripts/`, configuration contracts/examples in `config/`, and optional service templates in `systemd/`. Use ignored build/local/run directories for generated outputs. Follow root formatting files.

## Validation

For documentation/scaffolding changes, inspect relative links, source citations where present, whitespace, file inventory, and claims of completion. Do not present these checks as emulator tests. Once implementation is authorized, add meaningful deterministic tests, then actual host/panel integration checks and Pi qualification as specified by the plan.

Future ordinary validation must stay hardware-free and isolate its PTYs, state files, sockets, logs, and web data from a working BrewPi installation. Do not change services, attach physical controllers, or deploy as a side effect of a test command.

## Licensing

Record behavioral facts before authoring original MIT implementation. No reference source or translated test helper may enter the build. Complete the [provenance record](../licenses/README.md) for every introduced dependency and keep [third-party notices](../../THIRD_PARTY_NOTICES.md) accurate.
