# Service example

The original MIT [template](brewpi-emulator@.service.in) is configured with the install prefix and placed under `share/brewpi-emulator-rmx/systemd`, outside live unit directories. It assumes an existing `brewpi` user/group, private runtime/state directories, shared devpts visibility with the host, and explicit restarts. `ExecStartPost` runs the nonconsuming readiness helper and requires Python.

The example does not initialize controller state, enable itself, resume checkpoints, or restart the host. Syntax and command checks do not establish boot ordering or service-manager activation. See [operating assumptions](../docs/operation.md#service-example-and-limits).
