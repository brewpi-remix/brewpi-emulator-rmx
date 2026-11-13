# Configuration and scenarios

The original [active fermentation](active-fermentation.json) and [daily room cycle](room-cycle.json) examples are copyright 2026 Lee Bussy, SPDX-License-Identifier: MIT, covered by the root [license](../LICENSE.md). These are independently authored external scenario inputs, not copied simulator assets or serial commands. Omitted fields use the reviewed original baseline; see the [milestone 3 operating guide](../docs/milestone-3.md) for supported parameters and lifecycle semantics.

Pass an example with --scenario PATH. Inputs are read without modification or adjacent locks, and unknown fields fail explicitly. Keep generated checkpoints, saved controller images, and private runs in ignored state/run directories. No schema library or installed dependency is required.
