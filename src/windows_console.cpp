// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "windows_console.hpp"

#include "windows_host.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <mutex>
#include <thread>

namespace rmx {
struct WindowsConsole::Impl {
    win::Handle in{CreateFileW(L"CONIN$", GENERIC_READ | GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0,
                               nullptr)};
    win::Handle out{CreateFileW(L"CONOUT$", GENERIC_READ | GENERIC_WRITE,
                                FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0,
                                nullptr)};
    DWORD saved_in = 0, saved_out = 0;
    bool configured = false;
    std::atomic<bool> stopping{false}, busy{false}, failed{false};
    std::mutex mutex;
    std::wstring pending;
    win::Handle wake{CreateEventW(nullptr, FALSE, FALSE, nullptr)};
    std::thread worker;
    std::chrono::steady_clock::time_point submitted{};
    Impl() {
        if (!in || !out || !wake || !GetConsoleMode(in.get(), &saved_in) ||
            !GetConsoleMode(out.get(), &saved_out))
            throw std::runtime_error("no Windows console available");
        worker = std::thread([this]() {
            while (!stopping) {
                WaitForSingleObject(wake.get(), 100);
                if (stopping)
                    break;
                std::wstring text;
                {
                    std::lock_guard<std::mutex> guard(mutex);
                    text.swap(pending);
                }
                if (text.empty())
                    continue;
                size_t offset = 0;
                while (offset < text.size() && !stopping) {
                    DWORD count = 0;
                    if (!WriteConsoleW(out.get(), text.data() + offset,
                                       static_cast<DWORD>(text.size() - offset), &count, nullptr) ||
                        !count) {
                        failed = true;
                        break;
                    }
                    offset += count;
                }
                busy = false;
            }
        });
    }
    ~Impl() {
        stopping = true;
        SetEvent(wake.get());
        if (worker.joinable()) {
            // Cancel only this owned worker's blocking console call. Never
            // terminate a thread while it owns C++ state.
            auto thread = static_cast<HANDLE>(worker.native_handle());
            for (unsigned i = 0; i < 100 && WaitForSingleObject(thread, 0) == WAIT_TIMEOUT; ++i) {
                CancelSynchronousIo(thread);
                Sleep(10);
            }
            if (WaitForSingleObject(thread, 0) != WAIT_OBJECT_0) {
                TerminateProcess(GetCurrentProcess(), 2);
                std::_Exit(2);
            }
            worker.join();
        }
        restore();
    }
    void restore() noexcept {
        if (configured) {
            SetConsoleMode(in.get(), saved_in);
            SetConsoleMode(out.get(), saved_out);
            configured = false;
        }
    }
};
WindowsConsole::WindowsConsole() : impl(std::make_unique<Impl>()) {}
WindowsConsole::~WindowsConsole() = default;
void WindowsConsole::restore() noexcept {
    impl->restore();
}
void WindowsConsole::enable() {
    if (impl->configured)
        return;
    DWORD input =
        impl->saved_in & ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_QUICK_EDIT_MODE);
    input |= ENABLE_EXTENDED_FLAGS | ENABLE_PROCESSED_INPUT;
    if (!SetConsoleMode(impl->in.get(), input))
        throw win::error("configure console input");
    impl->configured = true;
    if (!SetConsoleMode(impl->out.get(), impl->saved_out | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
        throw win::error("configure console output");
}
std::pair<unsigned, unsigned> WindowsConsole::dimensions() const {
    CONSOLE_SCREEN_BUFFER_INFO info{};
    if (!GetConsoleScreenBufferInfo(impl->out.get(), &info))
        throw win::error("read console size");
    return {static_cast<unsigned>(info.srWindow.Right - info.srWindow.Left + 1),
            static_cast<unsigned>(info.srWindow.Bottom - info.srWindow.Top + 1)};
}
std::string WindowsConsole::input(bool discard) {
    if (discard && !FlushConsoleInputBuffer(impl->in.get()))
        throw win::error("discard suspended console input");
    DWORD available = 0;
    if (!GetNumberOfConsoleInputEvents(impl->in.get(), &available))
        throw win::error("inspect console input");
    if (!available)
        return {};
    INPUT_RECORD records[128];
    DWORD count = 0;
    if (!ReadConsoleInputW(impl->in.get(), records, std::min<DWORD>(available, 128), &count))
        throw win::error("read console input");
    std::string text;
    for (DWORD i = 0; i < count; ++i) {
        if (records[i].EventType != KEY_EVENT || !records[i].Event.KeyEvent.bKeyDown)
            continue;
        const auto& key = records[i].Event.KeyEvent;
        wchar_t c = key.uChar.UnicodeChar;
        if (!c)
            continue;
        for (WORD repeat = 0; repeat < key.wRepeatCount && text.size() < 256; ++repeat)
            text += c <= 127 ? static_cast<char>(c) : '\x01';
    }
    return text;
}
void WindowsConsole::check() const {
    if (impl->failed || (impl->busy && std::chrono::steady_clock::now() - impl->submitted >
                                           std::chrono::seconds(5)))
        throw std::runtime_error("console output stalled or failed");
}
bool WindowsConsole::output(const std::string& text) {
    check();
    if (text.size() > 4096)
        throw std::runtime_error("console output unavailable");
    if (impl->busy) {
        if (std::chrono::steady_clock::now() - impl->submitted > std::chrono::seconds(5))
            throw std::runtime_error("console output stalled");
        return false;
    }
    {
        std::lock_guard<std::mutex> guard(impl->mutex);
        impl->pending = win::wide(text);
        impl->submitted = std::chrono::steady_clock::now();
        impl->busy = true;
    }
    SetEvent(impl->wake.get());
    return true;
}
} // namespace rmx
