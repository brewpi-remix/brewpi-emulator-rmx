// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <array>
#include <memory>
#include <string>

namespace rmx {
class Engine;
using LcdRows = std::array<std::string, 4>;
// Only this presentation boundary converts the exported degree byte to UTF-8.
LcdRows unicode_lcd(const LcdRows& raw, bool& replaced);
class LocalLcd {
  public:
    LocalLcd(const std::string& mode, const LcdRows& initial, Engine* engine = nullptr,
             bool keep_on = false);
    ~LocalLcd();
    LocalLcd(const LocalLcd&) = delete;
    LocalLcd& operator=(const LocalLcd&) = delete;
    void tick(const LcdRows& rows, bool writable = true);
    void suspend() noexcept;
    bool shutdown_requested() const noexcept;

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace rmx
