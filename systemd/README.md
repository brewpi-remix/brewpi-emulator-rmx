# Optional Linux service example

The original MIT [template](brewpi-emulator@.service.in) is configured by CMake with the selected install prefix and staged under share/brewpi-emulator-rmx/systemd, outside the live system unit directory. It assumes an existing brewpi user/group, private runtime and durable state directories, a shared devpts namespace with the serial host, and explicit operator restarts. ExecStartPost runs the original nonconsuming endpoint-readiness helper. It does not initialize erased controller state, enable itself, or resume checkpoints.

The [operating guide](../docs/operation.md) explains assumptions and limits. The [milestone 5 review](../engineering/development/milestone-5-review.md) distinguishes target systemd-analyze syntax validation and execution of the exact commands as UID 2001 from actual system-manager activation, namespace policies, and boot ordering, which are unqualified. Deployment requires separate authorization.
