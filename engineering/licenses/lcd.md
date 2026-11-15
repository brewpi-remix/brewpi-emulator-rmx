# Local LCD provenance

Date: November 15, 2026. Original work is copyright 2026 Lee Bussy under the root [MIT License](../../LICENSE.md). The owner authorized implementation, validation, and repeated adversarial review of [Add LCD](<../development/Add LCD.md>), preserving Arduino behavior and independent MIT licensing, with a stop before committing or pushing.

## Original material

The LCD implementation in src/lcd.cpp and src/lcd.hpp, immutable accessor in engine.hpp, integration in main.cpp, scripts/lcd-viewer.py, CMake wiring, tests/lcd-core.cpp, tests/lcd_tests.py, tests/lcd_gui_checks.py, tests/lcd_installed_checks.py, and accompanying documentation are independently authored for this task. New source/helper files carry MIT SPDX identifiers and contributor notices. Controller, parser, temperature-formatting, and LCD-shadow firmware semantics are unchanged. Required degree-byte values, cell positions, and other interoperability facts come from the existing independently written behavioral specification. No firmware/Fuscus code, routine translation, tests, macros, font, image, or graphical asset was incorporated.

The GUI draws ordinary text at eighty positions using the system's existing fixed font. System-rendered test-window captures remain in ignored build evidence, not in the MIT source or a package payload. No third-party font bytes or downloaded graphic assets are included. Source-informed behavioral compatibility is not represented as a formally separated clean-room process.

## Actual external runtimes and tools

| Material | Actual role and evidence | Licensing/distribution disposition |
| --- | --- | --- |
| C++ standard library and POSIX system APIs | Native AppleClang 21.0.0/macOS ARM64 and Debian GCC 12.2.0/Linux AArch64 builds; no extra linked GUI library. | Existing compiler/runtime licensing remains applicable; no new system-library bundle. |
| Homebrew CPython 3.15.2 | Native macOS standard-library test driver and default PATH-selected GUI probe; this environment has no working _tkinter module. | External Python runtime under its supplied Python License Agreement/component notices; not bundled. Missing Tk selects fallback. |
| Apple CPython 3.9.6 and Tk 8.5.9 | Local legacy GUI smoke test revealed a blank canvas. The implementation now explicitly requires Tk 8.6+ and rejects this version before opening a window. | External system runtime/toolkit; not bundled. No support claim for this legacy GUI combination. |
| Debian CPython 3.11.2, python3-tk 3.11.2-3, and Tcl/Tk 8.6.13 | Real GUI, cell geometry, resizing, degree glyphs, private-channel parent-loss behavior, and installed-helper lifecycle in a disposable ARM64 Linux/X11 environment. | Python and Tcl/Tk retain their own supplied license agreements, BSD-style terms, component notices, and contributor notices. Only the original helper is staged; no runtime/toolkit source or binary is redistributed. |
| Xvfb 21.1.7 and x11-apps 7.7+9 | Disposable X11 display and capture of the original LCD test window; actual package versions are saved in ignored build evidence. | External test tools only, with their package terms/notices unchanged; not emulator dependencies or payloads. |
| FFmpeg | Local conversion of original test-window XWD captures to PNG for inspection. | External test tool only; no executable, codec, or generated source is incorporated. |

The helper imports tkinter lazily after establishing its private channel; terminal/headless execution needs neither Python nor Tcl/Tk. Tk 8.6 is the selected minimum following actual legacy rendering failure, not an assertion that every operating-system/font combination has been qualified. Runtime/toolkit redistribution, if ever requested, requires exact component/license-text/notice inventory before distribution; this task distributes no such bytes.

## Review gate and packaging boundary

The default fresh install still has six original project files. The explicitly selected lcd-viewer component adds only libexec/brewpi-emulator-rmx/lcd-viewer.py, yielding seven files; no reference clients, captures, Python, Tcl/Tk, fonts, or system libraries enter that tree. The installed helper path is relative to the executable/configured bindir/libexec relationship; absolute source/build paths are not compiled into the binary for development discovery. The development helper is copied next to the build executable by CMake.

Existing saved R4 source/binary archives, manifests, version metadata, checksums, and earlier unaccepted copies are untouched. Current working source is an uncommitted development revision, not a newly reviewed/frozen candidate commit or a replacement artifact. The old R4 source allowlist and candidate acceptance do not cover these additional files; creating a new feature-bearing source/binary release set requires separate authorization, an explicit complete inventory, and new snapshot/candidate identities. Keeping the application version at its existing value during this local task does not qualify the modified executable as the earlier accepted candidate.

The [LCD review](../development/lcd-review.md) records actual validation and the repeated review/fix dispositions. Independent original authorship, optional runtime separation, source notices, default/optional staged inventories, and exclusion of raw test captures have been reviewed. Physical Pi/Arduino qualification, unresolved F16 timing/history, signing, publication, deployment, and service activation remain separate gates.

## Native GUI follow-up runtime

For the owner's later native demonstration, the official Homebrew python-tk@3.14 3.14.10 package and its external libtommath 1.3.0 and tcl-tk 9.1.0 dependencies were installed on this Mac. CPython 3.14.10/Tk 9.1 successfully displayed the original graphical LCD. These runtimes retain their own supplied Python/Tcl/Tk/libtommath terms and notices and are not copied into the repository or staged project payload. The new close lifecycle message/exit status and associated helpers/tests are independently authored MIT work; they change local application shutdown policy, not Arduino reactions. See the [owner follow-up](../development/lcd-review.md#owner-follow-up-local-gui-and-stop-on-close) for the observed clean shutdown and historical snapshot boundary.
