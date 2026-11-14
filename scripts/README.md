# Development scripts

The original MIT [wait-ready.py](wait-ready.py) helper checks that a positive PID exists and an owned character endpoint has raw terminal flags without reading, writing, consuming startup diagnostics, or changing termios settings. It requires Python 3 and reports failures outside the serial protocol. A process/endpoint readiness result does not initialize the controller or establish firmware parity.

See the [operating guide](../docs/operation.md) for invocation and private-directory assumptions. Six original stdlib checks in [qualification/checks.py](../tests/qualification/checks.py) cover nonconsumption and invalid endpoint/process arguments; target runtime checks also exercise the installed helper and service commands. No installation or activation is performed on the user's host.
