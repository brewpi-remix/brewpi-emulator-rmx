// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "windows_channel.hpp"

#include "windows_host.hpp"

namespace rmx {
struct WindowsChannel::Impl {
    std::wstring path = L"\\\\.\\pipe\\brewpi-emulator-" + win::nonce();
    win::Handle pipe;
    bool connected = false;
    bool connect() {
        if (connected)
            return true;
        BOOL result = ConnectNamedPipe(pipe.get(), nullptr);
        DWORD code = result ? ERROR_SUCCESS : GetLastError();
        if (code == ERROR_PIPE_LISTENING)
            return false;
        if (code != ERROR_SUCCESS && code != ERROR_PIPE_CONNECTED)
            throw win::error("connect private message channel");
        return true;
    }
    Impl() {
        win::PrivateSecurity security;
        // NOWAIT here implements a polled packet interface, not overlapped I/O.
        // Message writes either accept the complete packet or accept no bytes.
        pipe = win::Handle(CreateNamedPipeW(
            path.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_NOWAIT | PIPE_REJECT_REMOTE_CLIENTS, 1,
            8192, 8192, 0, security.get()));
        if (!pipe)
            throw win::error("create private LCD message channel");
        if (!ConnectNamedPipe(pipe.get(), nullptr) && GetLastError() != ERROR_PIPE_LISTENING)
            throw win::error("listen on private LCD message channel");
    }
};
WindowsChannel::WindowsChannel() : impl(std::make_unique<Impl>()) {}
WindowsChannel::~WindowsChannel() = default;
const std::wstring& WindowsChannel::name() const noexcept {
    return impl->path;
}
bool WindowsChannel::accept(uint32_t expected_child_pid) {
    if (impl->connected)
        return true;
    if (!impl->connect())
        return false;
    ULONG actual = 0;
    if (!GetNamedPipeClientProcessId(impl->pipe.get(), &actual))
        throw win::error("inspect LCD channel client");
    if (!expected_child_pid || actual != expected_child_pid)
        throw std::runtime_error("LCD channel client is not the launched helper");
    impl->connected = true;
    return true;
}
bool WindowsChannel::accept_local() {
    if (!impl->connect())
        return false;
    impl->connected = true;
    return true;
}
void WindowsChannel::disconnect() {
    if (!DisconnectNamedPipe(impl->pipe.get()) && GetLastError() != ERROR_PIPE_NOT_CONNECTED)
        throw win::error("disconnect private message channel");
    impl->connected = false;
}
bool WindowsChannel::send(const std::string& packet) {
    if (!impl->connected)
        return false;
    if (packet.empty() || packet.size() > 4096)
        throw std::runtime_error("invalid LCD packet length");
    DWORD amount = 0;
    if (!WriteFile(impl->pipe.get(), packet.data(), static_cast<DWORD>(packet.size()), &amount,
                   nullptr))
        throw win::error("write LCD message");
    if (amount == 0)
        return false;
    if (amount != packet.size())
        throw std::runtime_error("LCD message write was not atomic");
    return true;
}
std::optional<std::string> WindowsChannel::receive() {
    if (!impl->connected)
        return {};
    char packet[4097];
    DWORD amount = 0;
    if (!ReadFile(impl->pipe.get(), packet, sizeof packet, &amount, nullptr)) {
        if (GetLastError() == ERROR_NO_DATA)
            return {};
        throw win::error("read LCD message");
    }
    if (amount == 0 || amount > 4096)
        throw std::runtime_error("invalid LCD message length");
    return std::string(packet, amount);
}
} // namespace rmx
