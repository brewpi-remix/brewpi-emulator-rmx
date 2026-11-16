# External GNU C Library corresponding source

This README is original MIT project documentation, copyright 2026 Lee Bussy. The enclosed glibc source archives and DSC retain all upstream/distributor licenses and notices; they are not original MIT emulator implementation.

This companion contains the complete Debian source package glibc 2.36-9+deb12u14: the upstream source tarball, Debian patch/build-script tarball, and unchanged DSC. SHA-256 values and sizes were checked against the DSC after retrieval through the snapshot repository. The DSC maintainer signature was not independently verified; no signature/attestation is claimed for this unsigned RC.

Extract with Debian's standard dpkg-source -x glibc_2.36-9+deb12u14.dsc, or use the upstream tarball and the provided Debian packaging/patches. The Debian package's own build dependencies and scripts describe its build. The separate original emulator source archive contains all application code and CMake build scripts. Together these supply library source and the work's source for modifying/rebuilding/relinking the startup/library pieces. R5 records the original exact compiler/runtime versions, link inputs, generic architecture flags, and the qualified executable hashes; no proprietary object or library is required.

Keep this companion and the NOTICES archive with the original source/binary archives. Standard dynamic OS libraries remain separately supplied and replaceable through the normal ELF loader. No reverse-engineering restriction is imposed for debugging library modifications. Refer to the supplied original LGPL/GPL texts and the unmodified glibc copyright/permission notices for their terms.
