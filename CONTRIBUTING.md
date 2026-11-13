# Contributing

Read the [project contract](CONTRACT.md), [implementation plan](IMPLEMENTATION_PLAN.md), and [development guide](engineering/development/README.md) first. The public repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx), with `main` holding the initial plan/scaffolding baseline. Local Git is initialized, and `origin` uses the repository's HTTPS URL. No runnable application or automated CI exists yet.

Base documentation contributions on `main` and target `main` in pull requests. No separate development branch, branch-protection policy, automated merge policy, or release process has been established. Implementation remains subject to an explicit user instruction.

Contribute original work under the [MIT License](LICENSE.md). Do not import or translate reference implementation code, tests, tables, or assets. Describe the relevant behavioral contract and author changes independently. Record any new general-purpose dependency and its license in [third-party notices](THIRD_PARTY_NOTICES.md) before adding it.

By intentionally submitting an original contribution for inclusion, you agree to license that contribution under this project's MIT License and confirm you are entitled to do so. Preserve existing copyright notices and identify additional contributors' notices as appropriate; the owner's root notice does not replace them. Include `SPDX-License-Identifier: MIT` on new original source/helper files, using an adjacent record for formats that cannot carry comments. Do not submit reference-derived work through an automated translation or an AI-assisted rewrite.

For a future code/dependency change, state whether material was independently authored, which behavioral specification it implements, and whether any third-party bytes, generated assets, or captures are included. Complete the [provenance review gate](engineering/licenses/README.md#review-gate) and actual dependency inventory before introducing them. Contribution templates record this statement; no signed CLA or DCO process has been established.

Keep changes focused, preserve unrelated work, and update documentation when behavior or supported scope changes. Follow `.editorconfig` and `.clang-format`; use one physical line per prose paragraph or prose list item and Oxford commas. Do not include credentials, generated runtime state, private captures, or new machine-specific paths in shared guidance.

A change description should explain the problem, resulting behavior, validation performed, and material limitations. Distinguish source review from execution, and Linux host evidence from Raspberry Pi qualification. Do not claim a passing build or test suite until those facilities exist and have actually run.

The owner authorized repository creation, Git initialization, and the initial documentation/scaffolding commit and push to `main`. Subsequent implementation, commits, pushes, releases, and deployment follow the scope of the active task; this initial publication does not approve emulator implementation.
