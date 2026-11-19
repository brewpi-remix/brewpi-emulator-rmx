# Native Pi and systemd qualification

This is a configuration-specific runtime qualification record for the source-built emulator on the physical Raspberry Pi `wspr5`. It records deployment compatibility, not physical Arduino equivalence or general Raspberry Pi hardware qualification. Original summary prose uses the root [MIT License](../LICENSE.md); external clients, tools, and private captures retain their own terms.

## Tested inputs

| Input | Qualified identity |
| --- | --- |
| Target | Raspberry Pi 5 Model B Rev 1.0; native AArch64 userspace; Debian 13.7 (trixie). |
| Kernel | `6.18.60+rpt-rpi-2712`. |
| Emulator source | Clean commit `764b4118be4b504a9c12363a477d6ebcf71a155a`. |
| Source inventory SHA-256 | `6aa8395e0548fa80acfdd5d5d43ae9209672ae07afb9eb1e08407bba8aa9cf2e`. |
| Installed executable SHA-256 | `c3764958e355826113953e52a798c71e50a1e5030b3e109158e79a7378121921`. |
| Build | Native Release build; GCC `14.2.0` (Debian `14.2.0-19`); CMake `3.31.6`. |
| Service manager | systemd `257.13-1~deb13u1`. |
| BrewPi host | `brewpi-script-rmx` revision `d183fb5319b928f78b4c0eb6f05fe3620610ffff`. |
| BrewPi panel | `brewpi-www-rmx` revision `f79631830a99575e250403f08a19be8bf944596c`. |
| Client tools | Python `3.13.5`; pySerial `3.5`; GitPython `3.1.40`; NumPy `2.2.4`; psutil `7.0.0`; configobj `5.0.9`; simplejson `3.19.2`. |
| Browser and PHP | Playwright `1.56.0`; Chromium `156.0.8078.79`; PHP `8.4.27`, with privately extracted matching mbstring package `8.4.27-1~deb13u1`. |

The source inventory digest is SHA-256 over the UTF-8 JSON object mapping tracked file paths to content SHA-256 values, serialized with sorted keys and compact separators. The private evidence retains the inventory and transfer hashes. These identities bind the observed artifact; other revisions and binary release archives do not automatically inherit this qualification.

## Execution topology

The installed emulator, unchanged pinned host/panel implementations, PHP server, and headless Chromium ran directly on the Pi, without a container or emulated CPU. The native workflow adapter reused the project's original MIT test orchestration with private paths and a separate loopback-only panel listener. It replaced container preparation instead of running the disposable-container account/path setup on the host.

The service ran as `brewpi:brewpi`; the isolated host/panel checks ran as `brewpi`, with `www-data` as their primary group and `brewpi` as a supplementary group. Clients used the explicit virtual PTY path and `altport=None`, with one serial reader. Runtime configuration, controller stores, sockets, logs, and client data were separate from working services. Python dependencies and the PHP extension were supplied privately; the existing Apache website was not replaced or reconfigured.

## Qualified observations

| Check | Result and boundary |
| --- | --- |
| Native core | Passed all six Linux CTest suites: model, dynamics, process, protocol fixtures, protocol edges, and PTY. The 48 source-defined fixture cases and nine nonpassing characterization placeholders retain their existing classifications. |
| Native RevC clients | Passed all 17 [host/panel workflows](../tests/integration/run.py), including initialization, discovery/assignment, modes, LCD/units, persistence quirks, profile resumption, calibration/deactivation/manual virtual output, reset, simulated heating/cooling, process replacement, logs/charts, maintenance logs, and browser execution. |
| I2C profile | Passed a separate direct-PTY smoke check of identity, A0 probe bus and output discovery order, initialization, assignment, saved gain, and clean restart. This is not the full 17-workflow I2C matrix or a physical I2C bus test. |
| Installed files | Installed and build executable hashes matched; ELF architecture, dynamic dependencies, helper presence, and installed ownership/modes were recorded. |
| Service activation | A uniquely named copy of the configured [supplied unit](../systemd/brewpi-emulator@.service.in), compared byte-for-byte, passed syntax verification, actual activation, readiness, stop/start, and explicit restart. The installation was root-owned and outside protected home directories. |
| Service policy and cleanup | Verified `Restart=no`, `brewpi` ownership and private `0700` runtime/state directories, clean shutdown, and removal of the owned PTY link, including the dangling-link check. |
| Service clients | Native host/panel checks passed initial panel initialization and assignment, then explicit host reopening after start and restart, retaining seven device assignments, the saved gain, mode, and target. |
| Enabled boot | Passed one owner-authorized whole-machine reboot. A changed boot ID, current-boot journal, successful readiness post-check, and active enabled unit established emulator startup during that boot. Explicitly started native clients then verified communication and saved settings/assignments. |
| Isolation and restoration | Source and external-client implementation hashes remained unchanged. Website/configuration hashes and existing service enablement matched their baselines; Apache, WsprryPi, and GPS services were active, and the existing website returned HTTP 200. |

Ordinary deployment checks used `--speed 1`; the existing bounded dynamics workflow used declared `60x` simulation pacing while host scheduling and timestamps remained on wall time. That workflow deliberately resumed its own checkpoint when changing pacing; the service did not automatically resume checkpoints. Host connections were explicitly reopened after emulator replacement. Clean process restart restored firmware-saved configuration and began a fresh simulated plant.

## Evidence and disposition

The private evidence set is identified as `bpq-20261119-063126/evidence.tar.gz`, SHA-256 `da295f2fb90e30f6197303c2065e4faf58e1e455e50fb357bb467a3c0359ba7c`. It contains `results.json`, the source inventory, executable/helper identities, native reports, workflow results, client/reference integrity checks, service configuration/journals, pre/post-boot identity, and cleanup checks. The archive and matching result record were retained on the qualification host and retrieved locally with their digest verified. Raw captures, machine-local paths/configuration, external client files, and the archive itself are not source/package inputs.

Helper regressions passed for CI, release, integration, readiness, and the qualification launcher. The release-helper fixtures initially failed under inherited `umask 0002`; a complete rerun with explicit `umask 022` passed all 42 checks without relaxing assertions. A service-runner evidence read initially failed on private evidence permissions before activation; an authorized supervisor read corrected that gate. Both initial failures and the successful reruns are retained. The specification/link/whitespace check passed locally against the same frozen source and pinned references; it is not a native Pi or hosted CI receipt.

The disposable service was disabled and removed after qualification, together with its installation, instance state, temporary account/group, test clients, and private dependencies. Evidence was retained. No operational emulator service remains deployed by this qualification, and no emulator implementation change was required.

## Limits

This result does not qualify other Pi models, 32-bit userspace, other OS/client combinations, a released binary archive, or later source inputs. RevC has the full client workflow run; I2C has only the stated smoke coverage. Native Pi execution and actual systemd activation are separate evidence from ordinary regression tests and GitHub Actions; this record is not a CI receipt.

Automatic BrewPi-host startup/reconnection, host-unit dependency ordering, automatic emulator recovery or checkpoint resume, extended endurance, power-loss durability, desktop GUI operation, USB/GPIO access, physical probes/relays, and physical Arduino behavior remain outside this result. The [accepted firmware limits](protocol/firmware-findings.md#outstanding-limits--will-not-address) and all nine nonpassing characterization placeholders are unchanged. The service still requires deliberate installation/enablement, a suitable account, shared PTY visibility, and explicit host reopening after emulator replacement; see the [operating guide](../docs/operation.md#service-example-and-limits).
