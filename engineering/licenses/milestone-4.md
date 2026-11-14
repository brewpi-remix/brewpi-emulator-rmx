# Milestone 4 provenance record

Date: November 13, 2026. The original integration launcher, Docker recipe, package-version declarations, Python orchestration/browser/socket clients, original profile input, assertions, and documentation are copyright 2026 Lee Bussy and licensed under the root [MIT License](../../LICENSE.md). Source/helper files carry SPDX-License-Identifier: MIT. Following isolated host/panel testing, review, and fixes, the owner authorized committing and pushing the reviewed milestone 4 setup, tests, and supporting docs to main.

## Original implementation and external-client boundary

The integration helpers were independently authored from the [planned workflows](../../IMPLEMENTATION_PLAN.md), reviewed behavioral contract, public host/socket/PHP interfaces, and observed panel DOM controls. They orchestrate processes and send original test input through real interfaces. They import no BrewPi/Fuscus reference module, routine, class, test/helper, generated table, or asset. Required command names, selectors, field names, numerical settings, and source revisions are interoperability facts. No production emulator code or reviewed fixture oracle needs replacement to accommodate a host/panel expectation.

Read-only reference mounts and temporary runtime clones are external test clients, not implementation source or vendored material. Host Python code, PHP/JavaScript/CSS, bundled panel assets, and reference licenses remain in the temporary clone; tracked-file hashes are checked before/after execution, with only the active host profile CSV declared mutable as runtime test input. Configuration and original test data change only those clones. No reference code is copied into src, tests, the test image build context, or tracked evidence. This remains disclosed source-informed development, not a formally separated clean-room claim.

Raw application logs, protocol captures, screenshots containing panel artwork, and other client-produced material remain ignored local evidence. Do not treat those bytes as original MIT assets or include them in a package without a separate provenance/distribution review. The saved review describes findings and minimal original examples rather than incorporating captures or panel assets.

## Actual external inventory

| Material | Role and disposition |
| --- | --- |
| brewpi-script-rmx d183fb5319b928f78b4c0eb6f05fe3620610ffff | Unmodified external host, GPL-3.0-or-later and its retained original notices; temporary runtime clone only. |
| brewpi-www-rmx f79631830a99575e250403f08a19be8bf944596c | Unmodified external PHP/browser panel with GPL-3.0-or-later project terms and bundled components' own notices; temporary runtime clone only. |
| Debian bookworm-slim base digest 99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 | External disposable test environment, with Debian packages retaining their individual licenses. The tool image is not an emulator release or redistributed MIT bundle. |
| GCC/C++ standard library, Make, CMake, Git, Python, PHP including sockets/mbstring, and Chromium | External build/application/browser tools installed inside that environment; not vendored or incorporated into original source. Their versions and system/package notices remain separate from project MIT terms. |
| Python host dependencies and browser tools | Exact versions are declared in the original [requirements file](../../tests/integration/requirements.txt); these are external test dependencies, not emulator runtime libraries. Installed metadata and freeze output are retained as ignored evidence. |

Python tools include Playwright 1.56.0 under Apache-2.0 and the host's simplejson, requests, psutil, configobj, aioblescan, GitPython, pyserial, NumPy, and packaging dependencies. Their supporting packages retain their own terms, including certifi's MPL-2.0 data/package terms. No requirement declaration relicenses those packages. A local test image containing them is not asserted to be distributable under MIT; no image/source/binary bundle or package is published by this milestone. Future redistribution must inventory actual image/library/data contents and notices separately.

An existing unrelated local browser/tool image was used for initial setup diagnosis, then replaced by the saved standalone public-base recipe. Only the final standalone environment supplies the completed review-run evidence. Failed preparation/automation attempts remain ignored and are not passing workflow claims. No package was installed on the user's host operating system, and no working BrewPi configuration/service or physical hardware was accessed.

## Review gate

The [milestone review](../development/milestone-4-review.md) records 17 passing integration checks, six passing native suites, eight passing negative evidence/isolation regressions, unchanged tracked reference files, the final standalone tool image/version inventory, and remaining evidence limits. Check original-source SPDX/copyright coverage, unchanged root license/history/defaults/diagnostics/fixtures, production-source preservation, clean pinned reference repositories, ignored-output exclusions, unchanged HEAD, and empty staging index before handoff. No new incorporated runtime library or reference implementation is present; [third-party notices](../../THIRD_PARTY_NOTICES.md) retain the empty incorporation inventory while distinguishing these external clients and tools.

The follow-up review independently authored the evidence-directory/failure gates, session-aware trace reader, cleanup/audit changes, stronger interface assertions, and negative regressions. These import only original helpers, the standard library, and the already declared external browser tool; no reference routine/test, asset, dependency, or wire oracle was copied or replaced. Runtime collection excludes unrelated bundled sample datasets; captured application output and screenshots still retain their external provenance. No production controller policy or licensing terms changed.
