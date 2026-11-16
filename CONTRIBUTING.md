# Contributing

Build and test using the [development guide](docs/development.md). Target `main` and keep changes focused. Follow `.editorconfig` and `.clang-format`. Write each prose paragraph and list item on one physical line, separated by blank lines.

Follow the [project contract](CONTRACT.md), [behavioral reference](engineering/protocol/behavioral-contract.md), and [provenance gate](engineering/licenses/README.md#review-gate). Preserve Arduino behavior, including documented bugs, and keep undefined/hardware-dependent cases distinct from passing tests. Local controls must not tighten serial input acceptance.

Submit only independently authored work you are entitled to license under MIT. Preserve copyright notices and include `SPDX-License-Identifier: MIT` in original source/helper files; use adjacent provenance records where the format cannot carry comments. No reference implementation, test, asset, generated table, translated routine, or AI-assisted rewrite of such material is accepted. Required wire identifiers and behavioral facts may be specified for interoperability.

Record each external component's origin, exact version, purpose, terms, notices, and distribution impact. External clients, captures, and tool images are not original MIT material. Keep private captures and generated results outside tracked inputs.

Explain the resulting behavior and relevant validation in a change description. Keep product documentation focused on current installation, operation, configuration, and limits. Do not add milestone reports, historical decisions, future roadmaps, or machine-specific development narratives. Preserve unrelated work and existing public artifacts.
