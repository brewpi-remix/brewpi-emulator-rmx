# Development tests

The six CTest suites exercise model arithmetic, dynamics/controller behavior, process pacing/checkpoints, protocol fixtures, edge cases, and real PTY/file ownership. Build and run them using the [development guide](../docs/development.md). Reports distinguish deterministic source-defined cases from unresolved physical/artifact-dependent behavior.

The original [fixture driver](driver.cpp) provides controlled internal state for semantic tests. The shipped executable has no such test interface. PTY/process tests exercise the public executable separately. [Fixture data](../engineering/protocol/test-vectors/README.md) describes byte matching and characterization limits.

Run independent helper regressions from the repository root:

```sh
python3 tests/ci/checks.py
python3 release/checks.py
python3 tests/integration/checks.py
python3 tests/qualification/launcher_checks.py
python3 tests/qualification/checks.py
```

The controls and LCD helpers exercise terminal/IPC behavior, menu confirmation, dimming, GUI fallback, close handling, and installed-helper discovery. They use isolated processes/PTYs; GUI-specific checks need the external graphical toolkit and session. Their command-line entry points identify the executable under test.

The opt-in external-client integration fixture runs the pinned host/panel separately through browser, PHP, socket, and serial interfaces. Prepare the sibling reference repositories listed in [references.json](ci/references.json), Docker, and the external tools image, then run:

```sh
./tests/integration/run-isolated.sh "$PWD/runs/integration-check"
```

Use a new output directory. The launcher owns its container and verifies cleanup; reference clients are not imported into the emulator. Its Dockerfile and requirements lock define external test dependencies. [Runtime checks](qualification/README.md) inspect installed files, readiness, recovery, and inert service commands. Generated state, raw client captures, logs, and screenshots are ignored development outputs, not package contents or original MIT assets.

Original tests are MIT. No reference helper, routine, or test is copied or translated. Physical Arduino/Pi behavior and system-manager activation are outside these regression claims.
