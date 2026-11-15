# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.16)
include(cmake/version.cmake)
project(brewpi_emulator_rmx VERSION ${RMX_VERSION_MAJOR}.${RMX_VERSION_MINOR}.${RMX_VERSION_PATCH} LANGUAGES CXX)
set(RMX_APPLICATION_VERSION "${PROJECT_VERSION}-${RMX_VERSION_PRERELEASE}")
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(RMX_SANITIZERS "Enable address and undefined-behavior sanitizers" OFF)
add_library(rmx_protocol STATIC src/json.cpp src/engine.cpp src/controller.cpp src/controls.cpp src/dynamics.cpp src/storage.cpp)
target_include_directories(rmx_protocol PUBLIC src)
target_compile_options(rmx_protocol PUBLIC -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion)
if(RMX_SANITIZERS)
  target_compile_options(rmx_protocol PUBLIC -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer)
  target_link_options(rmx_protocol PUBLIC -fsanitize=address,undefined)
endif()
include(GNUInstallDirs)
add_library(rmx_lcd STATIC src/lcd.cpp)
target_link_libraries(rmx_lcd PUBLIC rmx_protocol)
file(RELATIVE_PATH RMX_LCD_HELPER_RELATIVE "${CMAKE_INSTALL_FULL_BINDIR}"
  "${CMAKE_INSTALL_FULL_LIBEXECDIR}/brewpi-emulator-rmx/lcd-viewer.py")
target_compile_definitions(rmx_lcd PRIVATE RMX_LCD_INSTALLED_HELPER="${RMX_LCD_HELPER_RELATIVE}")
add_executable(brewpi-emulator-rmx src/main.cpp)
add_custom_command(TARGET brewpi-emulator-rmx POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different "${CMAKE_CURRENT_SOURCE_DIR}/scripts/lcd-viewer.py"
    "$<TARGET_FILE_DIR:brewpi-emulator-rmx>/lcd-viewer.py" VERBATIM)
# A helper edit must also refresh the adjacent development copy.
set_property(TARGET brewpi-emulator-rmx APPEND PROPERTY LINK_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/scripts/lcd-viewer.py")
target_link_libraries(brewpi-emulator-rmx PRIVATE rmx_lcd)
target_compile_definitions(brewpi-emulator-rmx PRIVATE RMX_VERSION="${RMX_APPLICATION_VERSION}")
include(CTest)
if(BUILD_TESTING)
  find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
  execute_process(COMMAND ${Python3_EXECUTABLE} -c "import sys; sys.exit(0 if __debug__ else 1)"
    RESULT_VARIABLE RMX_PYTHON_OPTIMIZED)
  if(NOT RMX_PYTHON_OPTIMIZED EQUAL 0)
    message(FATAL_ERROR "Python test assertions must be enabled")
  endif()
  add_executable(rmx-controls-tests tests/controls-core.cpp)
  target_link_libraries(rmx-controls-tests PRIVATE rmx_protocol)
  add_executable(rmx-model-tests tests/model.cpp)
  target_link_libraries(rmx-model-tests PRIVATE rmx_protocol)
  add_executable(rmx-lcd-tests tests/lcd-core.cpp)
  target_link_libraries(rmx-lcd-tests PRIVATE rmx_lcd)
  add_test(NAME milestone3-model COMMAND rmx-model-tests)
  add_test(NAME milestone3-dynamics COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/dynamics.py $<TARGET_FILE:rmx-fixture-driver>)
  add_test(NAME milestone3-process COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/pacing.py $<TARGET_FILE:brewpi-emulator-rmx>)
  set_tests_properties(milestone3-model milestone3-dynamics milestone3-process PROPERTIES TIMEOUT 120)
  add_executable(rmx-fixture-driver tests/driver.cpp)
  target_link_libraries(rmx-fixture-driver PRIVATE rmx_protocol)
  add_test(NAME milestone2-fixtures COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/fixtures.py $<TARGET_FILE:rmx-fixture-driver>)
  set_tests_properties(milestone2-fixtures PROPERTIES TIMEOUT 60)
  add_test(NAME milestone2-edges COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/edges.py $<TARGET_FILE:rmx-fixture-driver>)
  set_tests_properties(milestone2-edges PROPERTIES TIMEOUT 60)
  add_test(NAME milestone2-pty COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tests/transport.py $<TARGET_FILE:brewpi-emulator-rmx> $<TARGET_FILE:rmx-lcd-tests> $<TARGET_FILE:rmx-controls-tests>)
  set_tests_properties(milestone2-pty PROPERTIES TIMEOUT 60)
  if(RMX_SANITIZERS)
    # Native hosted ARM64 instrumentation is substantially slower than Release.
    # This bounds each whole test suite; protocol/process assertions retain
    # their own unchanged deadlines and all sanitizer findings remain fatal.
    set_tests_properties(milestone3-model milestone3-dynamics milestone3-process
      milestone2-fixtures milestone2-edges milestone2-pty PROPERTIES TIMEOUT 300)
  endif()
endif()

# Original install tree; service remains an example until explicitly installed.
configure_file(systemd/brewpi-emulator@.service.in brewpi-emulator@.service @ONLY)
install(TARGETS brewpi-emulator-rmx RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(PROGRAMS scripts/wait-ready.py DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/brewpi-emulator-rmx)
# Explicit optional component: existing six-file release payloads remain distinct.
install(PROGRAMS scripts/lcd-viewer.py DESTINATION ${CMAKE_INSTALL_LIBEXECDIR}/brewpi-emulator-rmx
  COMPONENT lcd-viewer EXCLUDE_FROM_ALL)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/brewpi-emulator@.service DESTINATION ${CMAKE_INSTALL_DATADIR}/brewpi-emulator-rmx/systemd)
install(FILES LICENSE.md THIRD_PARTY_NOTICES.md DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/brewpi-emulator-rmx)
install(FILES docs/operation.txt DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/brewpi-emulator-rmx)
