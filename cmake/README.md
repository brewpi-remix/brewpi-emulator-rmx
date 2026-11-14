# Build support

The root [CMakeLists.txt](../CMakeLists.txt) builds the original C++17 library/executable and independent tests with CTest. Optional address/undefined-behavior sanitizer flags are available for GCC/Clang. No helper module or downloaded dependency is required. Future CMake helper files belong here. Use the tested commands in the [build/run guide](../docs/milestone-2.md).

CMake now generates the optional service example and provides original install rules. Use DESTDIR staging and inspect the manifest as described in the [operating guide](../docs/operation.md); the rules do not activate a service or bundle external libraries.
