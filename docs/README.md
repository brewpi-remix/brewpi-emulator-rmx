# Operator and development documentation

The [operating guide](operation.md) describes prerequisites, Release/test/staging commands, private PTY and durable-state paths, initialization, nonconsuming readiness, optional service assumptions, clocks, checkpoints, and deliberate recovery. The installed [standalone runbook](operation.txt) remains usable without a source checkout. These are development artifacts, not a release or deployment authorization.

The [milestone 5 review](../engineering/development/milestone-5-review.md) records owner-selected isolated Debian 12 ARM64 qualification. Physical Pi operation, actual systemd activation, and nine exact-firmware characterization cases remain unqualified. The [milestone 3 guide](milestone-3.md) details scenario/clock semantics; the [milestone 4 guide](milestone-4.md) records the isolated real host/panel fixture and its distinct application evidence.
