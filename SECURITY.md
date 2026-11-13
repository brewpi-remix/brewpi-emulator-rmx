# Security reporting

This project has an unreleased milestone 2 development executable under review. No supported release exists. There is no supported-version or response-time commitment yet.

Report suspected vulnerabilities privately to the project maintainer, Lee Bussy. If no private reporting channel is available, request one without publishing exploit details. Include the affected revision or file, reproduction conditions, expected and observed behavior, and relevant environment details. Remove credentials and other private data.

Planned security-sensitive areas include serial command parsing, bounded buffers, configuration/state validation, symlink ownership, filesystem permissions, persistence failures, and service privilege boundaries. The proposed emulator is local and hardware-free; a PTY does not authenticate a client. Do not expose its serial endpoint through a network bridge as part of ordinary validation.
