# Third-party notices

The [MIT License](LICENSE.md) covers original BrewPi Emulator Remix code and documentation. It does not relicense external software, source references, or future dependencies.

## Current incorporation inventory

No third-party implementation source, assets, runtime-library files, generated source tables, or vendored dependencies have been added to the original project source tree. Compiler-provided material in provisional executables is addressed separately below. The repository contains original planning/scaffolding documentation, milestone 1 behavioral specifications and original JSON fixtures, project metadata, and standard MIT license text. Original milestone 2 and milestone 3 source/tests/build/scenario files and original milestone 4 integration tooling now exist; no executable or system-library bundle has been publicly released. The [milestone 2 provenance record](engineering/licenses/milestone-2.md) and [milestone 3 provenance](engineering/licenses/milestone-3.md) inventory the external tools and test environments actually used. The [milestone provenance record](engineering/licenses/milestone-1.md) describes numeric metadata, synthetic identities, and fixture authorship; source-derived interoperability facts do not relicense or incorporate the referenced implementation.

Layout and formatting follow the owner's existing repository conventions. This inventory does not claim those conventions or the standard license text are newly invented. No reference application implementation was used to populate the source/test directories, which now contain independently authored milestone 2 code and tests.

## Behavioral references

BrewPi firmware, BrewPi script, BrewPi web UI, BrewPi tools, BrewPi user documentation, and historical Fuscus were reviewed to establish behavioral compatibility requirements. Their inspected revisions and source citations appear in the [implementation plan](IMPLEMENTATION_PLAN.md). These references retain their existing licenses and are not part of this project's MIT-licensed implementation. BrewPi names identify interoperability targets and do not imply endorsement or transferred trademark rights.

The existing host and panel run as separate external compatibility clients for milestone 4. The [milestone 4 provenance](engineering/licenses/milestone-4.md) inventories these GPL clients, external PHP/browser/Python/build tools, and ignored raw evidence; no reference source/assets or downloaded test packages are vendored into the project. The original integration helpers use Playwright as an external test dependency, without adding an emulator runtime library. Their licenses and their own dependencies remain unchanged. Do not bundle their source, binaries, or assets into emulator distributions under this notice.

## Future dependencies

Before adding or redistributing a dependency, record its name, purpose, upstream location, exact version/revision, license identifier and license text, copyright notices, modifications, build/runtime role, and distribution obligations. Update this file from the actual dependency inventory, not from the proposed dependency list. A proposed JSON library, compiler, or test tool is not an incorporated dependency merely because the plan mentions it.

Select permissively licensed incorporated library code, keep its notices separate from original MIT work, and record external tools/system libraries/compatibility clients according to their actual role. A future decision to bundle any external component requires a separate inventory and distribution review. Generated outputs, captures, logs, and screenshots do not acquire MIT provenance merely by entering this tree; follow the material categories and review gate in the linked licensing guide.

See [licensing provenance](engineering/licenses/README.md) for the independent implementation boundary and review record requirements.

The [milestone 5 provenance](engineering/licenses/milestone-5.md) records the selected isolated Debian 12 ARM64 tool environment and inspected ELF dependencies. Original staging rules install only the original executable/helper/service example, project license/notices, and standalone operating text. System C/C++ libraries, Python, systemd, and the existing test-tool image remain external and retain their own terms; none is bundled by those rules. No new third-party library or reference implementation is incorporated, and no binary/image package is published.

The [R2 provenance record](engineering/licenses/software-release-r2.md) inventories pinned external Actions/actionlint, official minimum-tool sources, snapshot-based Debian provisioning, and hash-locked existing test packages. These are external CI/test inputs, not incorporated emulator libraries or bundled release contents; all retain their own terms. No reference implementation or assets are reused, and no test-tool image or release is published.

## Audited 0.0.1-rc.1 compiler/runtime components

Original project source and implementation remain MIT. The [R5 actual-artifact audit](engineering/licenses/software-release-r5.md) records the final seven-file Linux payloads, exact source/executable/archive identities, selected GCC/glibc startup and template/runtime contributions, used Linux UAPI headers, and external loader/shared-library closure. No BrewPi/Fuscus implementation or asset is incorporated. No shared library, tool image, external client, Python/Tcl/Tk runtime, or font is bundled in the emulator payloads.

The complete proposed distribution requires all three unchanged qualified source/binary archives and both separate NOTICES and glibc-source companions. The latter preserve external terms and are not original MIT implementation. Full GNU licenses, runtime/syscall exceptions, package copyright notices, exact file-level startup notices, original MIT license, and complete component/member inventories accompany the set. AArch64 start.S and csu/init.c lack the additional linking permission present in some other startup files; the exact complete Debian glibc source package, patches/build scripts, and original application source provide the source/relink route described in the audit. GCC target-code contributions retain GPL-3.0-or-later WITH GCC-exception-3.1; independent MIT terms do not become a blanket license for every executable contribution.

The [R4 record](engineering/licenses/software-release-r4.md) is historical preliminary provenance. Its archived preliminary notices are preserved unchanged and must be accompanied by the final R5 companions; distributing an executable or the old notice alone is not the approved closure. Nothing has been publicly released; R6 handoff and publication authorization remain separate.

## Optional local LCD runtime

The original MIT LCD adapter, console renderer, Python helper, and tests are independently authored, with no copied BrewPi/Fuscus implementation, font, or graphical asset. Terminal/headless execution needs no Python or Tk runtime. The optional graphical helper uses the separately supplied Python standard library/tkinter and Tcl/Tk; those external runtimes retain their Python and Tcl/Tk license terms and contributor notices. They are not bundled or relicensed MIT. The separate lcd-viewer install component adds only the original helper, leaving the default six-file core inventory unchanged. The [LCD provenance record](engineering/licenses/lcd.md) identifies the actual tested versions, roles, and distribution limits. A future runtime/toolkit bundle or expanded release manifest requires its own component/notice review.
