// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "json.hpp"

#include <cstddef>
#include <memory>
#include <string>

namespace rmx {
// Windows-only OS boundary. The caller retains controller scheduling and the
// pending-output gate; this class never feeds an engine or creates COM devices.
class WindowsSerial {
  public:
    static constexpr unsigned readable = 1, writable = 2;
    WindowsSerial(const Json& provisioned_pair, const std::string& selected_port);
    ~WindowsSerial();
    WindowsSerial(const WindowsSerial&) = delete;
    WindowsSerial& operator=(const WindowsSerial&) = delete;
    unsigned wait(bool accept_input, bool have_output, unsigned milliseconds);
    size_t read(char* bytes, size_t capacity);
    size_t write(const char* bytes, size_t length);
    bool drained() const noexcept;
    const std::string& peer() const noexcept;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace rmx
