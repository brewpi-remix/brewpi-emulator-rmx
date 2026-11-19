# Third-party notices

The [MIT License](LICENSE.md) covers independently authored emulator source, helpers, tests, scenarios, fixtures, and documentation. No BrewPi/Fuscus implementation, header, routine, generated table, test, font, or image is incorporated. Required wire identifiers and source-backed behavior are interoperability facts. BrewPi names identify compatibility targets, not endorsement or transferred rights.

## Linux compiled components

| Component | Role and applicable terms |
| --- | --- |
| GCC startup/support objects, C++ templates, and ARM64 outline atomics | Compiler-provided target-code contributions retain GPL-3.0-or-later with GCC Runtime Library Exception 3.1. Preserve the actual compiler/package notices and eligible-compilation record. |
| GNU glibc startup objects | Retain LGPL-2.1-or-later and any file-specific linking permissions. The distribution includes the corresponding Debian glibc source/patches/build scripts and original application source/build scripts for the source/relink route. Some startup files lack the additional linking permission; do not assume it applies to all objects. |
| Linux UAPI headers | Retain their file-specific terms, including Linux-syscall-note for normal user-space interfaces, and package notices. No kernel implementation is bundled. |
| ELF loader, libc/libm, libstdc++, and libgcc shared libraries | External operating-system requirements under their own terms; the binary payload does not bundle these shared libraries. |

The `NOTICES` companion preserves full applicable license/exception texts, package copyright notices, file-level startup notices, and exact component inventories. The glibc-source companion supplies the complete corresponding Debian source package, its patches, and build scripts. The inspected GNU baseline uses GCC 12.2.0-14+deb12u1 and glibc 2.36-9+deb12u14; actual package manifests/inventories identify the build inputs. Keep required source and notice companions with redistributed binaries. Original MIT terms do not become a blanket license for every executable contribution or for external GNU source.

The application source/build scripts permit rebuilding and relinking with modified libraries. The MIT application terms do not restrict modification or reverse engineering for debugging those modifications. ELF runtime/library requirements remain architecture-specific; a glibc version alone is not an ABI guarantee.

## macOS compiled components

Native macOS source builds use Apple Clang, the macOS SDK, and libc++ headers. The inspected libc++ headers identify their terms as Apache-2.0 with LLVM-exception and reference the [LLVM license](https://llvm.org/LICENSE.txt). The repository retains that legal text verbatim in `release/notices/LLVM-LICENSE.txt`, SHA-256 `8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee`. It is third-party legal material, not independently authored MIT prose.

The inspected native executable uses the external system libraries `/usr/lib/libc++.1.dylib` and `/usr/lib/libSystem.B.dylib`; no copy of either library is bundled. Compiler/SDK versions and exact build inputs remain part of component inspection. GNU/glibc companion requirements describe the Linux builds above, not these Apple toolchain inputs. Original MIT terms do not relabel compiler/runtime contributions or grant rights to redistribute the SDK itself.

## Windows compiled components

Native Windows builds use the separately installed Microsoft C++ compiler, Windows SDK, and C++ runtime. Inspected MSVC toolset `14.51.36231` STL headers carry Microsoft copyright and Apache-2.0 with LLVM-exception terms. The unmodified legal text is retained in `release/notices/MSVC-STL-LICENSE.txt`, SHA-256 `1fc6b6db121d4555d8f661937d7f6013693cd8fd67495d5e5d98c1d18fb83eda`, from the [Microsoft STL license](https://github.com/microsoft/STL/blob/219514876ea86491de191ceaa88632616bbc0f19/LICENSE.txt), and accompanies Windows binary payloads. It is external legal material, not original MIT prose. Compiler startup/support code and Windows SDK contributions retain their applicable Microsoft terms. Original MIT terms do not relabel these contributions or grant rights to distribute the compiler or SDK. The Windows profile does not bundle runtime DLLs; the Microsoft Visual C++ v14 x64 runtime is an external prerequisite. Source/package records bind the actual compiler, SDK headers, linker inputs, imported libraries, and retained notices. No provider SDK is incorporated.

The COM tests use externally provisioned [HHD Free Virtual Serial Ports](https://freevirtualserialports.com/) `7.35.01.1760`, with driver identity `7.35.0.1753`. This proprietary tool and its virtual-device components are not bundled or linked into the emulator. The free edition excludes commercial, government, and military use; its other provider restrictions also apply. The tests use an operator-provisioned pair record and standard Windows APIs, with no HHD SDK dependency. Original emulator code, tests, and helpers remain independently authored MIT work.

## External tools and clients

Python is external for the readiness helper and development tests. The graphical LCD uses separately supplied Python/`tkinter` and Tcl/Tk under their own terms. No interpreter, toolkit, font, or desktop runtime is bundled. Headless and terminal operation require neither Python nor Tcl/Tk.

The BrewPi Remix host and panel run separately under their own licenses. Development checks use separately supplied CMake/compiler tools, Python/PHP/browser packages, Playwright, GitHub Actions, and actionlint. Execution does not incorporate their code into the emulator or relicense their assets. Raw client captures/screenshots and downloaded tool images are excluded from the original source and binary payloads.

Native macOS and Windows endpoint checks use separately installed pySerial `3.5` under its BSD-3-Clause terms. It is an external test client and is not copied into source or binary payloads.

Required external license and copyright texts are preserved verbatim in the `NOTICES` and glibc-source companions available through the [project release channel](https://github.com/brewpi-remix/brewpi-emulator-rmx/releases). The source archive includes the contribution/provenance requirements and companion guides under `CONTRACT.md`, `engineering/licenses/`, and `release/`. These source-only documents are not installed beside this notice.
