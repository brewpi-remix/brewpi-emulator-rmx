# Runtime helpers

[lcd-viewer.py](lcd-viewer.py) is the original MIT graphical LCD helper. The emulator launches it over a private inherited descriptor; it does not open controller serial. It uses external Python 3.9+/`tkinter` and Tcl/Tk 8.6+ and sends local action intents to the C++ engine. The `lcd-viewer` CMake install component installs only this helper.

[wait-ready.py](wait-ready.py) uses the Python standard library to check a positive PID and an owned raw PTY without consuming startup bytes or changing terminal modes. It does not initialize controller configuration or authenticate the process/endpoint relationship.

See [operation](../docs/operation.md) for dependencies, invocation, and limits.
