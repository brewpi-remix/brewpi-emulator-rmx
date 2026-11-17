// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <memory>
#include <string>
#include <utility>

namespace rmx {
// Optional console presentation. Output runs on one bounded worker so a paused
// console cannot block the controller loop. Input never waits for a line.
class WindowsConsole {
  public:
    WindowsConsole();
    ~WindowsConsole();
    WindowsConsole(const WindowsConsole&) = delete;
    WindowsConsole& operator=(const WindowsConsole&) = delete;
    std::pair<unsigned, unsigned> dimensions() const;
    std::string input(bool discard);
    bool output(const std::string& text);
    void check() const;
    void restore() noexcept;
    void enable();

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace rmx
