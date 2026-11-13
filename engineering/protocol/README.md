# Protocol documentation

Status: source-reviewed plan only; no implemented protocol or conformance suite exists. The [implementation plan](../../IMPLEMENTATION_PLAN.md) currently contains the command inventory, identity proposal, field schemas, host timing, discovery behavior, and intentional differences.

Before implementation, finish the plan's milestone 1: independently authored command/response fixtures, default settings/constants, field-specific unit conversion, supported diagnostic IDs/arguments, mutation validation, and reset/persistence semantics. Required wire identifiers and numeric values are compatibility facts; do not copy upstream source enums, parsers, tables, or tests.

Keep exact wire compatibility separate from approximate controller numerics. Include strict JSON responses, permissive flat host command objects, CP437-safe transport, null setpoints/readings, full telemetry on state changes, and discovery refresh ordering. Distinguish panel operations from socket/harness-only operations. The [test-vector directory](test-vectors/README.md) reserves space for independently authored vectors; none have been created. Write them from behavioral facts, not copied upstream tests or captured diagnostic prose, and apply the [provenance review gate](../licenses/README.md#review-gate).
