# Development

## Build from source

Use a C++17 compiler, CMake 3.16 or later, Make or Ninja, and the platform development headers. See the [Windows guide](windows.md) for native MSVC builds and the five portable Windows core suites; COM, desktop, and package qualification remain separate checks. Native tests require Python 3.9 or later with its standard library. Source builds do not download a controller library or require the reference applications.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build -j2
(cd build && ctest --output-on-failure)
```

Set `-DBUILD_TESTING=OFF` to build without the Python test interpreter. The built executable is `build/brewpi-emulator-rmx`; CMake copies the viewer beside it for local use. Running CTest from the build directory works throughout the supported CMake range.

For a staged installation:

```sh
DESTDIR="$PWD/stage" cmake --install build
DESTDIR="$PWD/stage" cmake --install build --component lcd-viewer
```

The second command adds the optional Python helper. Use a fresh stage directory because install does not remove stale files. Keep the configured prefix: the service example contains configure-time absolute paths. Installation does not activate a service or bundle runtime libraries.

## Regression checks

For Apple Silicon source builds, explicit PTY/state paths, and native serial-client checks, see the [macOS guide](macos.md). macOS installations include its standalone operating guide and the LLVM legal text instead of a Linux service definition. The graphical helper requires a Python interpreter with a working `tkinter` extension; an importable `tkinter` package alone does not establish that the native extension is installed.

CTest runs six native suites covering protocol fixtures, malformed/partial input, PTY ownership/recovery, dynamics, filters, controller behavior, thermal balance, clock arithmetic, and checkpoints. Fixture reports distinguish 48 source-defined cases from nine nonpassing characterization placeholders. The [qualification reconciliation](../engineering/protocol/firmware-findings.md#characterization-reconciliation) separates their covered subclaims from genuinely unqualified outcomes; the nine placeholders do not mean nine wholly untested behaviors. A passing native suite does not establish physical Arduino or Pi equivalence. The separate [native Pi and systemd qualification record](../engineering/qualification.md) binds actual Pi host/panel, service lifecycle, and enabled-boot observations to their tested source-built artifact and environment.

Use `umask 022` when running release-helper regressions: their canonical source-metadata fixtures require mode `0644`. This is a fixture-creation precondition, not a relaxation of package permission validation.

```sh
cmake -S . -B build-sanitize -DCMAKE_BUILD_TYPE=Debug -DRMX_SANITIZERS=ON
cmake --build build-sanitize -j2
(cd build-sanitize && ctest --output-on-failure)
python3 tests/ci/checks.py
python3 release/checks.py
python3 tests/integration/checks.py
python3 tests/qualification/checks.py
```

The specification checker, `python3 tests/specification.py`, validates fixture metadata, links, whitespace, and pinned behavioral citations. It needs a Git checkout and the separately prepared sibling reference repositories in `tests/ci/references.json`. It reads reference source as evidence; it does not import it into the implementation. See [development tests](../tests/README.md) for optional controls and external-client tests.

## Source layout

| Directory | Responsibility |
| --- | --- |
| `src/` | Original JSON/state handling, serial controller engine, thermal model, local controls, LCD, and native process boundaries. |
| `config/` | Independently authored physical scenario examples. |
| `scripts/` | Readiness and graphical LCD helpers. |
| `tests/` | Native and helper regression tests plus isolated external-client checks. |
| `release/` | Archive, payload, build, and component-inspection utilities. |
| `engineering/protocol/` | Current behavioral reference and original fixture data. |

Follow [CONTRIBUTING.md](../CONTRIBUTING.md) and the [independent-authorship contract](../CONTRACT.md). Existing firmware bugs are interoperability requirements. Local GUI validation does not tighten serial acceptance. Undefined outcomes remain disclosed compatibility limits, not fabricated passing tests.
