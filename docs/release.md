# Package contents

Binary archives contain a single named directory with this prefix-relative layout:

| Path | Purpose |
| --- | --- |
| bin/brewpi-emulator-rmx | Emulator executable. |
| libexec/brewpi-emulator-rmx/wait-ready.py | Nonconsuming PTY readiness helper. |
| libexec/brewpi-emulator-rmx/lcd-viewer.py | Optional graphical LCD helper. |
| share/brewpi-emulator-rmx/systemd/brewpi-emulator@.service | Inert service example. |
| share/doc/brewpi-emulator-rmx/LICENSE.md | MIT license for original work. |
| share/doc/brewpi-emulator-rmx/THIRD_PARTY_NOTICES.md | Component and license information. |
| share/doc/brewpi-emulator-rmx/operation.txt | Standalone operating guide. |

The source archive contains the implementation, build files, scenarios, current documentation, and development tests. Binary archives contain no test harness, planning history, private logs, screenshots, reference clients, compiler, or shared-library bundle. The optional viewer is included in the controls distribution; a default CMake source installation omits it unless its install component is selected.

Obtain source/binary archives, SHA256SUMS, NOTICES, and the GNU glibc-source companion from the [project release channel](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases). Keep the required notice/source companions with extracted or redistributed binaries. They retain external license terms and are not MIT application source. The source and build scripts support rebuilding/relinking; see [component licensing](../THIRD_PARTY_NOTICES.md).

Verify the downloaded files with sha256sum --ignore-missing --check SHA256SUMS before use. Confirm that each downloaded archive reports OK; the ignore-missing option skips unselected files and does not establish companion completeness. Archives and tags are unsigned; checksums establish integrity, not independent authenticity. Use brewpi-emulator-rmx --version to identify the application. Serial n reports the separate emulated firmware identity.

See the [operating guide](operation.md) for extraction, dependencies, and use.
