// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <cstdint>
#include <memory>
#include <optional>
#include <string>

namespace rmx {
// Private, local, nonblocking message channel for the existing LCD protocol.
// The engine and action validation remain with the caller.
class WindowsChannel {
  public:
    WindowsChannel();
    ~WindowsChannel();
    WindowsChannel(const WindowsChannel&) = delete;
    WindowsChannel& operator=(const WindowsChannel&) = delete;
    const std::wstring& name() const noexcept;
    bool accept(uint32_t expected_child_pid);
    // The pipe DACL admits only this account; readiness accepts its local
    // probes without authenticating a caller by PID.
    bool accept_local();
    void disconnect();
    bool send(const std::string& packet);
    std::optional<std::string> receive();

  private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};
} // namespace rmx
