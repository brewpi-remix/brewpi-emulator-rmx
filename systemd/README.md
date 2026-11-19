# Service example

The original MIT [template](brewpi-emulator@.service.in) is configured with the install prefix and placed under `share/brewpi-emulator-rmx/systemd`, outside live unit directories. It assumes an existing `brewpi` user/group, private runtime/state directories, shared devpts visibility with the host, and explicit restarts. `ExecStartPost` runs the nonconsuming readiness helper and requires Python.

The example does not initialize controller state, enable itself, resume checkpoints, or restart the host. A uniquely named, otherwise unchanged configured copy passed actual activation, start/stop, explicit restart, and enabled startup after one reboot on the [qualified native Pi configuration](../engineering/qualification.md). Private permissions, readiness, saved assignments/settings, and explicit native host/panel reopening were checked. The disposable deployment was removed afterward; this is not automatic installation or qualification of other platforms, binary archives, or host-unit boot ordering.

Use a root-owned installation outside protected home directories and retain the configure-time prefix. The unit keeps `Restart=no`; explicitly reopen the host after replacing the emulator's PTY. See [operating assumptions and limits](../docs/operation.md#service-example-and-limits).
