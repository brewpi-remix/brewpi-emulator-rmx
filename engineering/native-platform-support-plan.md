# Native Windows COM-port and macOS PTY implementation plan

Status: reviewed plan awaiting implementation authorization. This task changes planning prose only. No implementation, provisioning, compilation, qualification, commit, push, tag, or publication is authorized. Original prose is copyright Lee Bussy under the root [MIT License](../LICENSE.md).

## 1. Intent and limits

Deliver a native Windows emulator using an explicitly provisioned virtual COM pair and a native macOS emulator using the existing PTY mechanism. Preserve the [Arduino behavioral contract](protocol/behavioral-contract.md), [documented firmware quirks](protocol/firmware-findings.md), and independently authored MIT implementation. This work adds operating-system support to existing emulator functions; it adds no controller policy or new simulation feature.

The source baseline is `903116877621f994117bf07b1d0828766daa61b9`, whose [CI attempt 2 passed](https://github.com/brewpi-remix/brewpi-emulator-rmx/actions/runs/43932899709/attempts/2). That includes macOS development tests, not complete native macOS host/panel qualification. Keep this plan outside [the shipping source allowlist](../release/source-files.txt).

Before execution, record the development checkout and target release. Do not automatically add this runtime work to the pending `0.0.1` release, alter accepted/public artifacts, or reuse their identities for changed inputs. Reassess affected Linux evidence when platform boundaries change; the metadata-only conditional R3 route does not automatically cover runtime changes. Historical Linux evidence remains associated with its original source and binaries.

Excluded: a new kernel driver, automatic driver installation, driver bundling, a shipping TCP/RFC2217 server, porting BrewPi's host/panel, new GUI features, installers/application bundles, native services or service activation, additional CPU targets, physical Pi qualification, and Arduino characterization. The nine unresolved Arduino cases remain unresolved. WSL, Cygwin, Wine, and Linux containers do not satisfy native Windows acceptance.

## 2. Initial targets and existing features

| Target | Proposed initial scope | Required environment |
| --- | --- | --- |
| Windows 11 x64 | Native PE executable with a qualified virtual COM pair. | Native x64 Windows and one approved external COM provider; record exact OS build, security policy, compiler, runtime, and driver identities. |
| Apple Silicon macOS ARM64 | Native Mach-O executable using an explicit PTY symlink. | Native ARM64 macOS 27 for both the release minimum and qualification target. |
| Linux amd64/ARM64 | Preserve existing behavior and distribution contracts. | Retain existing native regression requirements and rerun affected checks. |

Windows ARM64 and Intel macOS require separate authorization. Rosetta or CPU emulation provides supplemental evidence, not native qualification. A matching-architecture Windows VM is a native Windows software environment; a Linux guest is not.

Carry forward headless operation, terminal controls, and the existing optional graphical LCD/control helper. “Optional GUI” means optional for the user, not permission to skip its port and advertise full existing-feature support. Any reduced-feature delivery requires a separate scope decision. No display redesign or additional control is included.

## 3. Evidence and necessary portability work

| Boundary | Source-backed starting point | Bounded change |
| --- | --- | --- |
| Serial/scheduling | [main.cpp](../src/main.cpp) uses `posix_openpt()`, raw PTYs, `poll()`, and POSIX signals. | Keep one shared scheduling policy; supply a Windows COM/wait/shutdown adapter and retain the POSIX implementation. |
| Persistence | [storage.cpp](../src/storage.cpp) uses file locks, no-follow reads, same-directory replacement, and `fsync()`. | Supply equivalent Windows ownership, path-identity, replacement, and failure handling. |
| Local display | [lcd.cpp](../src/lcd.cpp) and [the viewer](../scripts/lcd-viewer.py) use POSIX terminal/process/IPC operations, with existing macOS branches. | Adapt only OS operations needed for current terminal and GUI behavior. |
| Readiness | [wait-ready.py](../scripts/wait-ready.py) inspects an owned PTY without consuming data. | Retain POSIX behavior and provide a nonconsuming Windows equivalent without opening an occupied COM port. |
| Build/package/CI | [CMakeLists.txt](../CMakeLists.txt), [packaging](../release/artifacts.py), [payload validation](../tests/ci/payload.py), and [CI validation](../tests/ci/gate.py) assume particular compilers, Linux inventories, or ELF. | Add explicit native target profiles and receipts without weakening existing profiles. |

Keep controller, thermal-model, clock, parser, and menu algorithms shared. Add only the small platform interfaces required by these boundaries; a general plugin framework or unrelated refactoring is excluded.

The pinned BrewPi host passes explicit `port` values to [pySerial's factory](https://github.com/brewpi-remix/brewpi-script-rmx/blob/d183fb5319b928f78b4c0eb6f05fe3620610ffff/BrewPiUtil.py#L376-L415). Its [Unix-specific imports](https://github.com/brewpi-remix/brewpi-script-rmx/blob/d183fb5319b928f78b4c0eb6f05fe3620610ffff/brewpi.py#L35-L40) prevent assuming unmodified native Windows host execution. This plan qualifies emulator endpoints; it does not silently take ownership of that external application's portability.

## 4. Endpoint contract and prerequisite gate

### Windows

Select one externally supplied virtual null-modem provider before substantial Windows porting. Record its origin, version/hash, license, cost, OS/security-policy compatibility, and documented pair-management and device-identification method. No provider is selected or qualified by this plan. Ordinary Windows APIs open existing endpoints; they do not create a virtual pair. See [Microsoft's communications-handle contract](https://learn.microsoft.com/en-us/windows/win32/devio/communications-resource-handles).

Use opposite endpoints, for example:

```text
Windows client COM7 <--> approved virtual COM pair <--> COM8 emulator
```

The proposed emulator invocation selects `--serial COM8`; the client's configuration selects:

```ini
port = COM7
altport = None
```

These are illustrative names, not ports to open during planning. Require explicit selection and exclusive ownership. Support canonical `COMn` device names, including numbers above `COM9`, without opening physical serial ports or guessing another port when one is missing or busy.

Use an explicit operator-provisioned pair record, as authorized by the owner. The record identifies both opposite COM names and their approved HHD virtual-device identities. Before opening the selected endpoint, check that both names still resolve to those virtual-device identities and reject missing, reassigned, physical, or busy endpoints without fallback. A friendly `COM7` name alone is insufficient evidence. Peer association comes from the operator's provisioned record; runtime device checks do not independently discover or prove the provider's current wiring. Document that limitation and require the operator to replace the record after reprovisioning. Do not add a provider SDK, inspect undocumented driver state, or silently treat a recorded peer as an automatically verified live association.

Use a private ownership/publication record separate from the COM name; do not create a relative `COM7.lock` file. The runtime runs unprivileged after external provisioning. Driver installation or pair creation needs authorization for the exact provider and target; it is not an emulator startup action.

Qualify `57600`/8N1 operation, the client's actual DTR/RTS/break behavior, startup with an unopened peer, finite buffers, explicit purges, slow readers, and close/reopen. Client purges may deliberately discard bytes; distinguish that from provider loss. Opening or closing a port must not invent USB resets, startup messages, or controller commands. A provider that cannot meet the declared byte-stream behavior fails its gate.

### macOS

Retain the existing raw PTY and stable symlink, supported by [Apple's PTY APIs](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/posix_openpt.3.html). Configure the host explicitly, for example:

```ini
port = /Users/example/.local/run/brewpi-emulator/serial
altport = None
```

Pass the same absolute path with `--serial`, replace the example username, and provide an explicit writable `--state` path. No new macOS default-path policy is needed for this scope. Keep current Linux defaults unchanged. Configuration files do not gain shell-variable or `~` expansion. The host must reopen after process replacement because the underlying PTY changes. `port = auto` is not virtual-endpoint discovery.

## 5. MIT authorship and platform signing

All new implementation, adapters, helpers, tests, and prose must be independently authored MIT with contributor notices and SPDX identifiers where applicable. Follow the [provenance gate](licenses/README.md#review-gate). Never copy, vendor, link, translate, adapt, or mechanically/AI-rewrite BrewPi/Fuscus implementation, tests, tables, or assets. Use OS/API documentation as behavioral facts, not copied driver or application implementation. Reference clients run separately and remain unchanged.

Keep the COM provider, Python/Tk, and platform runtimes external. Record their identities, terms, and prerequisites; do not incorporate a driver, proprietary SDK, interpreter, toolkit, or installer by default. Any paid dependency or redistribution change requires its own decision. Original MIT licensing does not relabel external material or every contribution to a compiled executable.

Keep Windows application artifacts publisher-unsigned, with no Authenticode certificate. The separate driver must satisfy the selected Windows policy; do not require disabled Secure Boot, disabled Memory Integrity, or test-signing mode as the normal supported setup. Consult [Microsoft's driver policy](https://support.microsoft.com/en-us/windows/hardware/drivers/the-windows-driver-policy) when qualifying the chosen package. An unavailable compliant provider is a blocker, not a reason to ship a different transport under the COM claim.

Use the owner-approved Developer ID signing and Apple notarization for macOS artifacts. Record the signing identity, team, notarization submission, and acceptance bound to the exact archive and executable. Keep credentials in the operator's Keychain, outside source and evidence. Qualify the final signed bytes; timestamped signatures are not a claim of byte-identical independent signing. Compare complete pre-signing executables from the independent build roots, then bind qualification to the retained signed artifact. Windows and Linux remain publisher-unsigned.

Use SHA-256 for integrity and describe it accurately. Test normal downloaded-artifact handling under the declared OS policy, documenting supported per-application consent. Do not add security-policy bypass scripts or automatic quarantine removal. If enforced policy prevents unsigned execution, bound the support statement accordingly rather than changing policy silently.

## 6. Implementation order

### A. Confirm prerequisites

Record the target release, approved support matrix, exact COM provider and pair-identification mechanism, native qualification hosts, client versions, platform signing policy, and test budgets. Existing approved environments may be used; do not provision machines or install drivers through this planning task. If the Windows provider gate fails, stop that track without expanding into driver development or substituting TCP-only support. macOS work can proceed independently after its own prerequisites are met.

### B. Preserve shared behavior while isolating OS calls

Capture existing event-loop and storage behavior in meaningful regression tests before changing their boundaries. Advance wall-derived physics at the existing points; preserve fractional milliseconds, restart ordering, and parser deadlines based on data actually fed to the engine.

The `65536`-byte pending-output threshold is the current backpressure trigger, not a hard queue limit. Preserve the existing handling of completed input chunks, partial writes, and controller/LCD gating. Do not truncate responses, add a new transaction rule, or replay trailing input discarded by the current restart path. A preposted Windows read may complete into a bounded staging buffer but must not feed commands through the application gate. Keep the existing ordering of timeout checks, completed reads/writes, and model advancement.

Acceptance: existing native Linux and macOS suites retain their semantics, fixtures, and exclusions. Review the exact production delta before carrying any release evidence forward.

### C. Implement Windows platform operations

Use independently written Win32 code for exclusive communications handles, bounded asynchronous reads/writes, and cancellable waits. Track partial completions and buffer ownership until cancellation/completion finishes; keep engine mutations on the shared loop. [Microsoft documents the overlapped I/O model](https://learn.microsoft.com/en-us/windows/win32/devio/overlapped-operations). Preserve binary bytes, CRLF, raw `B0`, fixed-point artifacts, diagnostic interleaving, and one-wall-second parser waits independently of simulation speed.

Implement private store locking, bounded regular-file reads, same-directory replacement, and native flushing with documented failure semantics. Cover Unicode/spaced paths, aliases, hard links, reparse points, busy/read-only files, and input/output collisions. Preserve failures before replacement and uncertain durability after replacement; add no whole-command transaction or universal power-loss guarantee. Use an explicit writable `--state` path initially; do not add automatic state migration or install-directory writes.

Map console interruption to cooperative main-loop shutdown. Preserve abrupt-termination recovery and checkpoint conditions. Account for outstanding or partially completed application writes before applying the existing drained-output checkpoint guard, and finish/cancel owned I/O before releasing its buffers. OS-buffer acceptance is not proof of peer consumption; retain the operator drain/stop procedure without adding an unbounded COM/PTY flush barrier. Provide nonconsuming readiness using the already-owned endpoint and process-lifetime/publication information; never open either COM end for a readiness probe or claim authentication from a PID alone.

### D. Carry existing local controls to native targets

Preserve `cw`, `ccw`, `press`, door controls, menu confirmation, expiry, dimming, fallback, GUI-close intent, and checkpoint exclusion of drafts. `Enter` submits terminal text; it is not a substitute for `press`. Adapt Windows console/process/IPC operations using the smallest mechanism that preserves the existing bounded, versioned action protocol. Select that mechanism from a focused proof; a named pipe is an option, not a preapproved protocol redesign or network service.

Restrict handle inheritance, keep private IPC local to the user, handle paths without shell execution, and prevent duplicate/stale actions. Adapt the Python helper's transport rather than assuming a POSIX descriptor can be reused on Windows. Preserve external optional Python/Tk dependencies and Python-free headless/terminal operation. Keep macOS's existing path unless a reproduced defect requires a scoped change.

### E. Validate macOS's existing PTY path

Run native pySerial checks through the configured symlink, covering ownership, raw attributes, startup bytes, deadlines, acceleration, backpressure, readiness, and reopen/restart. Pin the tested Python/pySerial versions.

Exercise `flushInput()`, `flushOutput()`, and `flush()`. The pinned host calls `flush()` at [startup](https://github.com/brewpi-remix/brewpi-script-rmx/blob/d183fb5319b928f78b4c0eb6f05fe3620610ffff/brewpi.py#L764-L775); [pySerial issue 625](https://github.com/pyserial/pyserial/issues/625) reports a macOS PTY drain hang. Establish whether it occurs on the selected matrix; do not assert a reproduced emulator bug or patch the reference host. A required dependency or transport change must be reviewed before accepting that matrix.

### F. Package and validate exact native artifacts

Keep C++17 and the current build floor unless a demonstrated requirement needs a separately reviewed change. Add compiler/platform-specific options for MSVC/Windows SDK and Apple Clang/SDK. Audit the selected external MSVC runtime, Apple runtime, startup/header contributions, and any redistributed bytes. Use native sanitizers that actually exist; do not claim Windows UBSan coverage by substituting another OS.

Produce a Windows ZIP and a macOS archive containing the native executable, applicable existing helpers, standalone guide, and required notices. Exclude the Linux systemd unit from these profiles. No MSI or `.app` bundle is required. Extend manifests only as needed to bind OS, CPU, executable format, dependency closure, helper capabilities, inventory, and permissions/ACL expectations; preserve version-bound Linux verification and explicitly version incompatible schema changes.

Compare builds from two independent roots per new target with pinned tools and all required transformations completed before final hashes and tests. Investigate nondeterminism before acceptance; do not hide arbitrary differing regions. Validate extraction, moved directories, OS/CPU rejection, prerequisites, helper discovery, and installed inventories against actual package bytes.

## 7. Bounded native qualification

Run these checks on Windows x64 and macOS ARM64 using exact package/source identities. Native COM tests need the real approved virtual pair. PTY tests need the actual macOS PTY. Mocks, relays, GUI simulations, emulation, and cross-compilation do not substitute for those checks.

- Run all 48 deterministic fixture cases through the source-bound test driver and retain the nine unresolved cases as exclusions. Map which cases can also be established through the public endpoint; exercise that transport subset without adding a production test API or claiming constructed preconditions came from serial traffic.
- Check native public traffic at `1x`, `10x`, and `60x`, plus paused time, split/malformed tokens, raw bytes, ordered bursts, slow readers, state/store behavior, restart, and reconnect. Set numeric timing/resource limits and measurement definitions before qualification; retain existing applicable deadlines and justify OS-specific metrics.
- Run existing clock/controller/filter boundary cases separately from public transport tests. Exercise endpoint and storage faults, cancellation, duplicate ownership, and at least 100 process/client lifecycle cycles with cleanup verification.
- Run at least 300 wall seconds each at `1x` and `60x` on the final packages, including controls and checkpoint continuation. This is focused platform qualification, not a new steady-hour or endurance claim. Additional soak duration requires an agreed release requirement or a concrete finding; this plan does not automatically introduce another 24-hour/6-hour campaign.
- Validate real terminal and desktop GUI behavior, unavailable-toolkit fallback, Unicode/quoting, clean close, abrupt termination, and owned-resource cleanup. Mocked GUI checks support but do not establish desktop acceptance.
- Run the actual pinned Linux BrewPi host/panel's 17 existing workflows through each native endpoint using a test-only byte relay if needed. The relay listens on a private TCP endpoint; Linux pySerial's `socket://` client connects to it, and the relay opens the selected native COM peer or PTY. It preserves raw bytes and one-reader ownership. It is isolated test infrastructure, never a shipping listener or evidence of native Windows/macOS BrewPi-host execution. Independently test the native endpoint without the relay.
- Retain existing required Linux/macOS CI checks and add native Windows build/core checks. Provider-backed acceptance is also required: use an approved native self-hosted CI runner or a separate native qualification target; do not assume hosted CI permits driver installation. External qualification receipts remain a separate release gate and must never impersonate GitHub Actions receipts or turn missing CI green. Bind each evidence set to exact source, package, OS/CPU, provider/tool identity, its actual producer/run/attempt, and cleanup. Missing execution is pending/blocked, never success, and CI receipts from different attempts are not combined.

A full native BrewPi-stack port remains excluded. Advertising emulator COM/PTY support must accurately identify the tested client and deployment topology. If the owner requires the complete stack to run natively, obtain a separate scope decision rather than making that requirement implicit here.

## 8. Completion and handoff

Before calling either new target supported, close its provider/dependency prerequisites, relevant native checks, existing-feature presentation checks, package reproducibility, exact-source association, provenance audit, and required execution receipts. Keep unresolved environment prerequisites visible; they are not completed tests. Cross-OS/ABI checkpoint migration, additional architectures, and extended endurance remain outside the default claim.

Update current operator guidance only after implementation is validated. Include opposite COM-end selection, explicit macOS paths, permissions, dependencies, controls, readiness, shutdown/reopen, checkpoint limits, platform signature and notarization status, checksums, and troubleshooting. Validate platform-specific verification commands and generate matching standalone guides. Keep this plan and private captures outside distributions.

Retain a handoff binding source, artifacts/hashes, platform/provider configuration, real-client topology, test/CI results, signature state, dependency notices, limitations, and original Linux evidence dispositions. Review source, behavior, artifacts, and evidence together; fix authorized findings and repeat affected validation until no release-blocking issue remains. Stop for owner review before committing or pushing unless later authorization explicitly includes those actions. Tagging, publication, service activation, driver installation, physical Pi work, and Arduino characterization are separate actions requiring their own authorization.
