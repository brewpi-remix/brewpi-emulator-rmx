# Installed-runtime checks

These original MIT development helpers exercise installed-file integrity, dynamic dependencies, PTY/readiness, acceleration, blocking/backpressure, storage/checkpoint recovery, and inert service commands. They do not enable a service or qualify physical hardware.

The isolated Docker launcher uses an ARM64 tools image built from the external-client Dockerfile:

```sh
docker build --platform linux/arm64 -t brewpi-emulator-test-tools:portable tests/integration
./tests/qualification/run-isolated.sh "$PWD/runs/runtime-check"
```

Run from the repository root with Docker and Python 3.9+ available. Use a new output directory. Image preparation downloads separately licensed tools; the runtime container has no network. RMX_QUALIFICATION_IMAGE selects the tools image, and the launcher verifies its architecture and records its immutable local identity. A Mac/ARM64 guest does not establish physical Pi qualification.

Source-build mode is the default. Packaged-input mode uses RMX_EXECUTION_MODE=packaged-input, RMX_PAYLOAD_ROOT, and RMX_PAYLOAD_MANIFEST to select an already extracted payload and exact declared hashes/modes; optional RMX_CANDIDATE_COMMIT/RMX_CANDIDATE_SNAPSHOT bind its source identity. Native-package helpers additionally support explicitly selected amd64 execution. Do not label emulated amd64 as native.

The native-package staging request must include candidate_version. It must match the staged cmake/version.cmake, SOURCE.json version, and candidate.json candidate_version, in addition to the required source, manifest, and wrapper hashes. The isolated CTest shim remains usable without the source helper modules.

Missing/failed/incomplete child reports or unverified container cleanup fail the launcher. Raw evidence remains private/ignored. The helper regressions can run without launching a qualification environment:

```sh
python3 tests/qualification/checks.py
python3 tests/qualification/launcher_checks.py
```
