# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.16)
project(rmx_windows_boundaries LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "These native Windows development tests require an MSVC-compatible toolchain")
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
get_filename_component(RMX_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(RMX_SERIAL_PAIR "" CACHE FILEPATH "Explicit approved operator-provisioned COM pair record")
find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
enable_testing()
add_executable(rmx-windows-storage-tests "${RMX_ROOT}/tests/windows-storage.cpp"
  "${RMX_ROOT}/src/storage_windows.cpp" "${RMX_ROOT}/src/json.cpp")
add_executable(rmx-windows-serial-tests "${RMX_ROOT}/tests/windows-serial.cpp"
  "${RMX_ROOT}/src/windows_serial.cpp" "${RMX_ROOT}/src/json.cpp")
add_executable(rmx-windows-channel-tests "${RMX_ROOT}/tests/windows-channel.cpp"
  "${RMX_ROOT}/src/windows_channel.cpp")
foreach(target rmx-windows-storage-tests rmx-windows-serial-tests rmx-windows-channel-tests)
  target_include_directories(${target} PRIVATE "${RMX_ROOT}/src")
  target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8)
endforeach()
target_link_libraries(rmx-windows-storage-tests PRIVATE advapi32 bcrypt)
target_link_libraries(rmx-windows-serial-tests PRIVATE setupapi advapi32)
target_link_libraries(rmx-windows-channel-tests PRIVATE advapi32 bcrypt)
add_test(NAME windows-storage COMMAND rmx-windows-storage-tests "${CMAKE_CURRENT_BINARY_DIR}")
# Always register the provider-backed test. Missing configuration is a failure,
# never a silently skipped COM qualification or evidence of a physical port.
add_test(NAME windows-serial COMMAND rmx-windows-serial-tests "${RMX_SERIAL_PAIR}")
add_test(NAME windows-channel COMMAND rmx-windows-channel-tests "${Python3_EXECUTABLE}"
  "${RMX_ROOT}/tests/windows-channel-client.py" "${RMX_ROOT}/scripts/windows_channel.py")
set_tests_properties(windows-storage windows-serial windows-channel PROPERTIES TIMEOUT 120)
