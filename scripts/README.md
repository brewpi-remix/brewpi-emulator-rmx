# Runtime helpers

[lcd-viewer.py](lcd-viewer.py) is the original MIT graphical LCD helper. The emulator launches it over a private inherited POSIX descriptor or a private Windows message pipe; it does not open the controller serial endpoint. It uses external Python 3.9+/`tkinter` and Tcl/Tk 8.6+ and sends local action intents to the C++ engine. The `lcd-viewer` CMake install component installs this helper and its Windows transport module on Windows.

[wait-ready.py](wait-ready.py) uses the Python standard library to check a positive PID and an owned raw PTY without consuming startup bytes or changing terminal modes on POSIX. That POSIX check does not authenticate the process/endpoint relationship. On Windows, `--state` selects the private publication and live challenge channel; it checks the publication generation without opening either COM endpoint. Neither path initializes controller configuration.

On macOS, the readiness check accepts `IGNBRK` in Darwin's raw PTY mode; byte translation, echo, canonical input, signal processing, and software flow control remain disabled. Linux retains its existing flag checks.

See [operation](../docs/operation.md) for dependencies, invocation, and limits.
