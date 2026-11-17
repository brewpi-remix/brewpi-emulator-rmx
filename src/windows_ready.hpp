// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <filesystem>
#include <memory>
#include <string>
namespace rmx {
// An account-private publication and live challenge channel, independent of
// either COM endpoint. A stale record alone never establishes readiness.
class WindowsReady {
  public:
    WindowsReady(const std::filesystem::path& state, const std::string& serial);
    ~WindowsReady();
    void tick();

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace rmx
