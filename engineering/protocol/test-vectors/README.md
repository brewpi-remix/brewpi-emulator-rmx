# Protocol test vectors

This directory reserves the planned location for independently authored protocol vectors. It contains no executable tests, JSON fixtures, or captured messages yet.

Milestone 1 of the [implementation plan](../../../IMPLEMENTATION_PLAN.md) must define input bytes, expected response fields/types, initial state, ordered mutations, and relevant timing for each supported workflow. Separate exact wire requirements from approximate thermal/controller results. Include malformed input and reconnect/reset cases.

New original vectors are MIT-licensed under the root [license](../../../LICENSE.md). Record each vector's behavioral source/revision and authorship in adjacent documentation when its data format cannot hold comments. Do not copy upstream tests, diagnostic tables, implementation-generated fixtures, or raw external captures into this directory. Follow the [provenance review gate](../../licenses/README.md#review-gate) before inclusion. A directory placeholder is not a conformance result.
