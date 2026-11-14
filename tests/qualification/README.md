# Selected Linux target qualification

These original MIT helpers qualify only the owner-selected isolated Debian 12 ARM64 environment. They use Python stdlib, original project tests, CMake, native compiler tools, systemd-analyze, and an existing external tool image. They do not import or mount reference application code. See the [scope](../../engineering/development/milestone-5-scope.md), [operating guide](../../docs/operation.md), [review](../../engineering/development/milestone-5-review.md), and [provenance](../../engineering/licenses/milestone-5.md).

From the repository root, with Docker and host Python 3.9+ available and the ARM64 image prepared:

```sh
./tests/qualification/run-isolated.sh "$PWD/runs/milestone5/new-qualification"
```

The evidence directory must not exist. RMX_QUALIFICATION_IMAGE may name a compatible ARM64 image; the launcher resolves its actual immutable local ID and records inspect metadata. If the existing image is unavailable, build it with the original [milestone 4 recipe](../integration/Dockerfile):

```sh
docker build --platform linux/arm64 -t brewpi-emulator-m4-tools:portable tests/integration
```

Image preparation downloads external Debian/Python tools and needs network; qualification itself runs with no network. The base digest and Python requirements are pinned, but Debian repositories may produce newer packages, so a newly built image is a new environment requiring fresh qualification. The review records the actual tested image ID and versions, not a promise that the tag always denotes those bytes. No reference repository enters the image build context.

The launcher reserves fresh evidence, rejects another architecture, mounts source read-only and evidence writable, uses an owned container ID/init process, imposes a 900-second overall timeout, and cleans up the container on exit. It verifies removal through a successful Docker query; inability to verify cleanup fails the run. Missing, failed, or incomplete child reports fail even if the container exits zero. A failed child/launcher cannot leave a primary passing report; an earlier child report is archived separately. It creates only disposable container paths and ignored local evidence/image data. It does not install or activate a service on the user's host.

prepare.py creates UID/GID 2001 inside the container, builds Release and Debug/ASan/UBSan, executes all six native suites unprivileged, stages and audits six install files, checks that BUILD_SHARED_LIBS=ON still yields a runnable install without an uninstalled project library, inspects the AArch64 ELF/library closure and dynamic search paths, records actual package notices, verifies source-input hashes before and after execution, validates the generated unit syntax, and invokes service.py to exercise the exact configured commands under that account. runtime.py tests ownership/readiness, 1x/10x/60x pacing and partial-input waits, alternating ordered replies with a paused reader, full snapshot continuation, failed-checkpoint preservation, and deliberate SIGKILL/stale-link recovery. No systemd manager runs; namespace policies, boot ordering, physical Pi operation, and nine unresolved exact-firmware outcomes remain unqualified.

Require qualification-results.json and launcher-results.json to pass, including cleanup_verified=true. Inspect source-inventory.json/source-integrity.json, service-results.json, runtime-results, native-release/native-sanitize, tool/image metadata, install-inventory.json, ELF/library output, and individual build/test logs. Raw evidence is ignored and is not an MIT fixture oracle. Runtime thresholds describe the saved workload; they are not a universal latency or acceleration guarantee.

Run the small original negative regressions independently without Docker:

```sh
python3 tests/qualification/checks.py
python3 tests/qualification/launcher_checks.py
```

The six readiness checks verify queued-byte/termios preservation and invalid endpoint/process/limit rejection. The seven launcher checks substitute an original fake docker executable to verify evidence preservation, failure invalidation/owned cleanup, architecture rejection, isolation/image arguments, missing/nonpassing child evidence, unverified cleanup, and repeated termination during finalization. They do not count as actual container/runtime evidence. Their logs remain separate from the final target run.
