// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "windows_channel.hpp"
#include "windows_host.hpp"

#include <chrono>
#include <filesystem>
#include <iostream>

namespace {
std::wstring argument(const std::wstring& input) {
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t c : input) {
        if (c == L'\\') {
            ++slashes;
            continue;
        }
        result.append(c == L'\"' ? slashes * 2 + 1 : slashes, L'\\');
        result += c;
        slashes = 0;
    }
    result.append(slashes * 2, L'\\');
    return result + L'\"';
}
void require(bool value, const char* reason) {
    if (!value)
        throw std::runtime_error(reason);
}
} // namespace
int wmain(int argc, wchar_t** argv) {
    try {
        require(argc == 4, "supply Python, client script, and channel module");
        auto directory =
            std::filesystem::temp_directory_path() / (L"rmx-pipe-proof-" + rmx::win::nonce());
        rmx::win::PrivateSecurity security;
        if (!CreateDirectoryW(directory.c_str(), security.get()))
            throw rmx::win::error("create private message proof directory");
        struct Cleanup {
            std::filesystem::path directory;
            ~Cleanup() {
                std::error_code ec;
                std::filesystem::remove_all(directory, ec);
            }
        } cleanup{directory};
        auto release = directory / "release";
        rmx::WindowsChannel channel;
        std::wstring command = argument(argv[1]) + L" -I " + argument(argv[2]) + L" --module " +
                               argument(argv[3]) + L" --pipe " + argument(channel.name()) +
                               L" --server-pid " + std::to_wstring(GetCurrentProcessId()) +
                               L" --release " + argument(release.native());
        STARTUPINFOW startup{};
        startup.cb = sizeof startup;
        PROCESS_INFORMATION info{};
        if (!CreateProcessW(argv[1], command.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                            nullptr, nullptr, &startup, &info))
            throw rmx::win::error("launch native packet proof client");
        rmx::win::Handle process(info.hProcess), thread(info.hThread);
        try {
            auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
            auto check = [&] {
                require(std::chrono::steady_clock::now() < deadline, "native packet proof timeout");
                require(WaitForSingleObject(process.get(), 0) == WAIT_TIMEOUT,
                        "packet client exited before completing exchange");
            };
            bool rejected = false;
            while (!rejected) {
                try {
                    (void)channel.accept(info.dwProcessId + 1);
                } catch (const std::runtime_error&) {
                    rejected = true;
                }
                check();
                Sleep(1);
            }
            require(channel.accept(info.dwProcessId), "correct child binding failed");
            for (auto bytes : {std::string{}, std::string(4097, 'x')}) {
                bool invalid = false;
                try {
                    (void)channel.send(bytes);
                } catch (const std::runtime_error&) {
                    invalid = true;
                }
                require(invalid, "invalid server packet length accepted");
            }
            for (unsigned i = 0; i < 100; ++i) {
                std::optional<std::string> packet;
                while (!(packet = channel.receive())) {
                    check();
                    Sleep(1);
                }
                std::string expected;
                expected += char(i & 255);
                expected += char(i >> 8);
                for (unsigned j = 0; j < 1024; ++j)
                    expected += char(j & 255);
                require(*packet == expected, "native message bytes or ordering changed");
                while (!channel.send(*packet)) {
                    check();
                    Sleep(1);
                }
            }
            std::optional<std::string> ready;
            while (!(ready = channel.receive())) {
                check();
                Sleep(1);
            }
            require(*ready == "backpressure-ready", "missing backpressure barrier");
            unsigned queued = 0;
            std::string payload(4096, 'z');
            while (queued < 256 && channel.send(payload))
                ++queued;
            require(queued > 0 && queued < 256, "pipe failed to reach bounded backpressure");
            rmx::win::Handle marker(CreateFileW(release.c_str(), GENERIC_WRITE, FILE_SHARE_READ,
                                                security.get(), CREATE_NEW, 0, nullptr));
            require(bool(marker), "cannot release message proof client");
            marker.reset();
            while (!channel.send("end")) {
                check();
                Sleep(1);
            }
            std::optional<std::string> drained;
            while (!(drained = channel.receive())) {
                check();
                Sleep(1);
            }
            require(*drained == "drained:" + std::to_string(queued),
                    "blocked message bytes were lost");
            while (!channel.send("ack-drained")) {
                check();
                Sleep(1);
            }
            require(WaitForSingleObject(process.get(), 5000) == WAIT_OBJECT_0,
                    "packet client did not stop");
            DWORD code = 0;
            require(GetExitCodeProcess(process.get(), &code) && code == 0,
                    "native packet client failed");
        } catch (...) {
            if (WaitForSingleObject(process.get(), 0) == WAIT_TIMEOUT) {
                TerminateProcess(process.get(), 1);
                WaitForSingleObject(process.get(), 5000);
            }
            throw;
        }
        std::cout << "100 private native message exchanges and launched-client binding passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
