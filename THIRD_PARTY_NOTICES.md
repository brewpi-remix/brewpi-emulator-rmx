# Third-party notices

The [MIT License](LICENSE.md) covers independently authored emulator source, helpers, tests, scenarios, fixtures, and documentation. No BrewPi/Fuscus implementation, header, routine, generated table, test, font, or image is incorporated. Required wire identifiers and source-backed behavior are interoperability facts. BrewPi names identify compatibility targets, not endorsement or transferred rights.

## Compiled components

| Component | Role and applicable terms |
| --- | --- |
| GCC startup/support objects, C++ templates, and ARM64 outline atomics | Compiler-provided target-code contributions retain GPL-3.0-or-later with GCC Runtime Library Exception 3.1. Preserve the actual compiler/package notices and eligible-compilation record. |
| GNU glibc startup objects | Retain LGPL-2.1-or-later and any file-specific linking permissions. The distribution includes the corresponding Debian glibc source/patches/build scripts and original application source/build scripts for the source/relink route. Some startup files lack the additional linking permission; do not assume it applies to all objects. |
| Linux UAPI headers | Retain their file-specific terms, including Linux-syscall-note for normal user-space interfaces, and package notices. No kernel implementation is bundled. |
| ELF loader, libc/libm, libstdc++, and libgcc shared libraries | External operating-system requirements under their own terms; the binary payload does not bundle these shared libraries. |

The NOTICES companion preserves full applicable license/exception texts, package copyright notices, file-level startup notices, and exact component inventories. The glibc-source companion supplies the complete corresponding Debian source package, its patches, and build scripts. The inspected GNU baseline uses GCC 12.2.0-14+deb12u1 and glibc 2.36-9+deb12u14; actual package manifests/inventories identify the build inputs. Keep required source and notice companions with redistributed binaries. Original MIT terms do not become a blanket license for every executable contribution or for external GNU source.

The application source/build scripts permit rebuilding and relinking with modified libraries. The MIT application terms impose no restriction on modification or reverse engineering for debugging those modifications. ELF runtime/library requirements remain architecture-specific; a glibc version alone is not an ABI guarantee.

## External tools and clients

Python is external for the readiness helper and development tests. The graphical LCD uses separately supplied Python/tkinter and Tcl/Tk under their own terms. No interpreter, toolkit, font, or desktop runtime is bundled. Headless and terminal operation require neither Python nor Tcl/Tk.

The BrewPi Remix host and panel run separately under their own licenses. Development checks use separately supplied CMake/compiler tools, Python/PHP/browser packages, Playwright, GitHub Actions, and actionlint. Execution does not incorporate their code into the emulator or relicense their assets. Raw client captures/screenshots and downloaded tool images are excluded from the original source and binary payloads.

Required external license and copyright texts are preserved verbatim in the NOTICES and glibc-source companions available through the [project release channel](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases). The source archive includes the contribution/provenance requirements and companion guides under CONTRACT.md, engineering/licenses/, and release/. These source-only documents are not installed beside this notice.
