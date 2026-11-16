# Build configuration

[version.cmake](version.cmake) supplies application metadata. The root [CMakeLists.txt](../CMakeLists.txt) builds the C++17 executable, native tests, optional sanitizers, and an inert service example. Install rules support DESTDIR staging and a separate lcd-viewer component. No controller library is downloaded or vendored. See [development](../docs/development.md).
