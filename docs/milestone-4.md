# Isolated host/panel integration

Milestone 4 runs the pinned BrewPi Remix host and panel as separate external clients of the original emulator. The fixture builds inside a disposable Linux container, uses private runtime copies/configuration/data, drives real browser controls, and records which supplemental operations use HTTP or the host socket. See the [review](../engineering/development/milestone-4-review.md) for results and limits and the [provenance record](../engineering/licenses/milestone-4.md) for independent MIT authorship and external components.

## Run the fixture

Docker and Bash must be available, with the prepared sibling reference repositories at their reviewed revisions. The original [launcher](../tests/integration/run-isolated.sh) builds the [tool image](../tests/integration/Dockerfile) from a digest-pinned public Debian base and installs the [pinned external test packages](../tests/integration/requirements.txt). Image construction requires network access to Debian/Python package sources; application testing runs with network disabled. This is an explicit development test, separate from the dependency-free native CTest suites.

```sh
tests/integration/run-isolated.sh
```

Optional arguments select the reference directories and a new ignored evidence directory. The path must not already exist; the launcher reserves it atomically and refuses reuse without modifying previous evidence:

```sh
tests/integration/run-isolated.sh ../brewpi-script-rmx ../brewpi-www-rmx "$PWD/runs/milestone4/review"
```

The tested host revision is d183fb5319b928f78b4c0eb6f05fe3620610ffff, and the panel revision is f79631830a99575e250403f08a19be8bf944596c. The harness refuses different HEADs. Sources are mounted read-only; clones inside the container provide runtime settings, logs, data, and Git metadata expected by the unmodified applications. Runtime configuration supplies a private explicit serial path, startupDelay=0, a ten-second logging interval, a test beer name, and the private web root. The host's ordinary log-file option supplies the panel's log viewer. Container-local brewpi/www-data identities support the reference applications' ownership operations.

The launcher publishes no network ports and passes through no physical devices. The emulator and a byte-transparent PTY relay supply only virtual serial endpoints. PHP listens on container loopback, the host uses its private UNIX socket, and Chromium runs headlessly inside that same network-disabled container. Applications, browser, build products, and controller state live in disposable container filesystems; raw evidence alone is copied to the chosen ignored directory. The launcher records its own exit status, uses a private container ID for cleanup, and bounds execution to 900 seconds with a termination grace period. Interrupted or failed runs cannot retain a passing primary result. Container removal follows completion; the local tool image remains available for another test.

## Exercised interfaces

The browser clicks the real panel's reset, device-assignment, mode/target, temperature-unit, default-setting, profile-open/apply, chart, and log-viewer controls. Original CSV profile input is saved through the panel's real PHP endpoint rather than claiming use of its profile editor. Calibration, deactivation, and manual output are explicit host UNIX-socket checks because the selected device editor does not expose those fields. Reading state files and the serial trace provides additional assertions, not substitute controller responses.

The host optimistically changes some cached settings before reading a controller response. Target acceptance therefore checks saved controller values as well as the real host cache; off mode also waits for disabled targets. Polling leaves room for the host's socket timeout to service its serial queue. The relay records/forwards bytes without generating protocol replies or intercepting application logic. Each emulator process has a distinct capture session; heating/cooling assertions require new state records from the correct session and target-change window. Incomplete trailing capture records/frames are retried, while malformed completed records fail validation.

The legacy panel renders a profile preview while its tab is hidden. In this Chromium environment that can leave chart content over the Open button. The fixture waits for the panel's pending five-second Apply refresh, reveals the profile tab, then performs an ordinary browser-window resize before clicking Open. The panel's own resize handler restores the chart layout. There is no forced click, injected handler, patched reference asset, or emulator behavior change.

Initial panel workflows and the disabled/resumed profile run at speed 1 against the real host wall clock. A separate constant-beer-target phase stops the host, checkpoints/resumes the emulator at speed 60, and reopens the host to observe heating, cooling, and evolving temperatures. The final ordinary process restart uses a fresh external plant and checks firmware-saved configuration. Host profile time, log dates, and chart timestamps remain wall time throughout. A single brew retains records written during the Fahrenheit phase after the display returns to Celsius, so that mixed-unit chart is rendering evidence rather than a single-unit thermal trajectory; dynamic assertions use Celsius device readbacks.

## Evidence and limits

A successful integration-results.json reports individual workflow outcomes and interfaces. Acceptance also requires launcher-results.json and cleanup-results.json to pass. Launcher failures invalidate the primary result, preserving any earlier child report/traceback in integration-before-launcher-failure.json. Cleanup continues through later stages even if a relay, artifact copy, or audit fails; an abnormal host/emulator exit prevents a pass. Other ignored artifacts include image/package/tool versions, raw serial and HTTP captures, native CTest results, all-tracked-file integrity hashes with the active host profile CSV explicitly allowlisted as mutable input, per-session host logs, test-batch host/web data, a checkpoint, and browser screenshots. These are local external-client evidence and are not automatically MIT material or redistribution inputs. Keep them out of tracked source.

The reviewed setup passed 17 integration checks, all six native suites, and eight negative evidence/isolation regressions. These regressions can also run without Docker or external Python packages using the original [helper checks](../tests/integration/checks.py):

```sh
python3 tests/integration/checks.py
```

Exact slot/ROM/pin/function/polarity fields are checked against the unchanged reviewed original defaults fixture. Unit testing checks numerical C→F→C readings and saved units. Deactivation must read null, reactivation must restore calibrated readings, and manual writes require confirmed test mode. The actual browser chart response must contain heating/cooling states and changing chamber values; canvas existence alone is insufficient.

The fixture verifies this specific host/panel pair and Linux/browser environment. It does not qualify another panel, a physical Arduino, Raspberry Pi installation, USB reset/discovery/flashing, Bluetooth peripherals, software releases, or distribution contents. The nine reviewed firmware characterization cases remain unresolved. No firmware/Fuscus implementation, reference test helper, or reference asset is incorporated into the emulator or its original test sources.

The owner authorized committing and pushing the reviewed milestone 4 setup, tests, and supporting docs to main. Milestone 5 and deployment remain unapproved.
