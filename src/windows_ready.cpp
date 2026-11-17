// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "windows_ready.hpp"

#include "storage.hpp"
#include "windows_channel.hpp"
#include "windows_host.hpp"

#include <chrono>
namespace rmx {
struct WindowsReady::Impl {
    Storage record;
    WindowsChannel channel;
    std::string serial, generation = win::utf8(win::nonce());
    std::chrono::steady_clock::time_point connected{};
    std::string response;
    Impl(const std::filesystem::path& state, std::string selected)
        : record(std::filesystem::path(state.native() + L".ready")), serial(std::move(selected)) {
        record.write(Json::Object{{"format", "brewpi-emulator-ready-v1"},
                                  {"pipe", win::utf8(channel.name())},
                                  {"pid", double(GetCurrentProcessId())},
                                  {"generation", generation},
                                  {"serial", serial}});
    }
    void reset() {
        channel.disconnect();
        connected = {};
        response.clear();
    }
    void tick() {
        try {
            if (!channel.accept_local())
                return;
            auto now = std::chrono::steady_clock::now();
            if (connected == decltype(connected){})
                connected = now;
            if (response.empty()) {
                auto packet = channel.receive();
                if (packet) {
                    auto probe = Json::parse(*packet);
                    auto nonce = probe.at("nonce").string();
                    if (probe.object().size() != 1 || nonce.size() != 32 ||
                        nonce.find_first_not_of("0123456789abcdef") != std::string::npos)
                        throw std::runtime_error("invalid readiness probe");
                    response = Json(Json::Object{{"format", "brewpi-emulator-ready-v1"},
                                                 {"nonce", nonce},
                                                 {"generation", generation},
                                                 {"serial", serial}})
                                   .dump();
                }
            }
            // Keep the pipe connected until the client consumes this response
            // and closes it. DisconnectNamedPipe would discard unread data.
            if (!response.empty()) {
                if (response != "sent" && channel.send(response))
                    response = "sent";
                else if (response == "sent")
                    (void)channel.receive();
            }
            if (now - connected > std::chrono::seconds(2))
                reset();
        } catch (const std::exception&) {
            reset();
        }
    }
};
WindowsReady::WindowsReady(const std::filesystem::path& state, const std::string& serial)
    : impl(std::make_unique<Impl>(state, serial)) {}
WindowsReady::~WindowsReady() {
    try {
        impl->record.write(Json::Object{{"format", "brewpi-emulator-ready-v1"}, {"ready", false}});
    } catch (const std::exception&) {
        // A retained stale generation cannot answer a new live challenge.
    }
}
void WindowsReady::tick() {
    impl->tick();
}
} // namespace rmx
