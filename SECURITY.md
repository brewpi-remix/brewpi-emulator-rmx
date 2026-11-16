# Security reporting

Report suspected vulnerabilities privately to the project maintainer, Lee Bussy. If no private reporting channel is available, request one without publishing exploit details. Include the affected build/source identity, reproduction steps, observed behavior, and environment, with credentials/private data removed.

The emulator uses local PTYs, private IPC, and state/checkpoint files. A PTY does not authenticate clients or isolate other code running under the same account. Restrict runtime/state directories and run unprivileged. Keep serial endpoints local rather than exposing them through a network bridge.
