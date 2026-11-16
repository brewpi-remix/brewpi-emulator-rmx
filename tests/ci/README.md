# Regression CI

The [workflow](../../.github/workflows/regression.yml) runs static specification/link/provenance checks, helper regressions, native Linux amd64/ARM64 Release and sanitizer suites, macOS ARM64 development checks, and isolated ARM64 host/panel integration. The completion validator requires executed receipts from every lane and verifies source/run identity; skipped or missing jobs do not pass.

[references.py](references.py) prepares separate pinned compatibility references listed in [references.json](references.json). Native CTest builds require neither Git nor those references; specification citation checks and real-client integration do.

[native.py](native.py) configures/builds/runs the native suites and inspects their reports. [payload.py](payload.py) binds packaged checks to declared file hashes/modes and source identities. [checks.py](checks.py) tests rejection of incomplete, forged, or mismatched execution records. Linux wrappers use disposable native guests; emulated execution is not native evidence. External tool versions and inputs are pinned in the Dockerfiles and helper configuration.

Use the [development commands](../../docs/development.md) for local checks. Keep candidate/runtime evidence separate from ordinary CI summaries. This workflow does not tag, upload releases, deploy, activate services, or access physical controllers.
