// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "windows_serial.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

using Clock = std::chrono::steady_clock;
void require(bool ok, const char* message) {
    if (!ok)
        throw std::runtime_error(message);
}
void transfer(rmx::WindowsSerial& source, rmx::WindowsSerial& destination,
              const std::string& bytes) {
    auto deadline = Clock::now() + std::chrono::seconds(5);
    size_t sent = 0;
    std::string received;
    while (sent < bytes.size() || received.size() < bytes.size()) {
        require(Clock::now() < deadline, "bounded transfer deadline exceeded");
        if (source.wait(false, sent < bytes.size(), 1) & rmx::WindowsSerial::writable)
            sent += source.write(bytes.data() + sent, bytes.size() - sent);
        if (destination.wait(true, false, 1) & rmx::WindowsSerial::readable) {
            char buffer[1024];
            auto count = destination.read(buffer, sizeof buffer);
            received.append(buffer, count);
        }
        require(received.size() <= bytes.size(), "provider invented serial bytes");
    }
    require(received == bytes && source.drained(),
            "raw bytes changed or write acknowledgement was premature");
}
int wmain(int argc, wchar_t** argv) {
    try {
        require(argc == 2, "supply the explicit approved pair record");
        std::ifstream input(std::filesystem::path(argv[1]), std::ios::binary);
        require(bool(input), "missing pair record");
        std::stringstream data;
        data << input.rdbuf();
        require(data.str().size() <= 65536, "pair record too large");
        auto record = rmx::Json::parse(data.str());
        require(record.at("endpoints").array().size() == 2, "pair must have two endpoints");
        const auto first = record.at("endpoints").array()[0].at("port").string();
        const auto second = record.at("endpoints").array()[1].at("port").string();
        std::string raw;
        for (unsigned i = 0; i < 1024; ++i)
            raw.push_back(char(i % 256));
        for (unsigned cycle = 0; cycle < 100; ++cycle) {
            rmx::WindowsSerial a(record, first);
            require(a.peer() == second, "operator peer record differs");
            bool busy = false;
            try {
                rmx::WindowsSerial duplicate(record, first);
            } catch (const std::runtime_error&) {
                busy = true;
            }
            require(busy, "exclusive virtual-device ownership was not enforced");
            rmx::WindowsSerial b(record, second);
            transfer(a, b, raw);
            transfer(b, a, raw);
            // A bounded preposted read may finish while the application gate
            // closes. It must remain staged until input is allowed again.
            a.wait(true, false, 0);
            size_t sent = 0;
            auto end = Clock::now() + std::chrono::seconds(5);
            while (sent < 2) {
                require(Clock::now() < end, "gate-probe write deadline exceeded");
                if (b.wait(false, true, 1) & rmx::WindowsSerial::writable)
                    sent += b.write("nc" + sent, 2 - sent);
            }
            require(!(a.wait(false, false, 2) & rmx::WindowsSerial::readable),
                    "closed gate exposed a read completion");
            char buffer[1024];
            require(a.read(buffer, sizeof buffer) == 0, "closed gate consumed staged bytes");
            std::string staged;
            while (staged.size() < 2) {
                require(Clock::now() < end, "gate-probe read deadline exceeded");
                if (a.wait(true, false, 1) & rmx::WindowsSerial::readable)
                    staged.append(buffer, a.read(buffer, sizeof buffer));
            }
            require(staged == "nc", "staged bytes changed across the application gate");
            // Destruction must cancel an outstanding read before releasing its
            // OVERLAPPED and storage. The outer runner bounds a broken driver.
            a.wait(true, false, 0);
            b.wait(true, false, 0);
        }
        auto wrong = record;
        wrong["endpoints"].value = record.at("endpoints").value;
        auto endpoints = wrong.at("endpoints").array();
        endpoints[0]["instance_id"] = "ROOT\\PORTS\\unapproved";
        wrong["endpoints"] = endpoints;
        bool refused = false;
        try {
            rmx::WindowsSerial bad(wrong, first);
        } catch (const std::runtime_error&) {
            refused = true;
        }
        require(refused, "device reassignment was not rejected");
        refused = false;
        try {
            auto unrecorded = first != "COM99999" && second != "COM99999" ? "COM99999" : "COM99998";
            rmx::WindowsSerial absent(record, unrecorded);
        } catch (const std::runtime_error&) {
            refused = true;
        }
        require(refused, "unrecorded COM selection was not rejected");
        std::cout << "100 virtual handle cycles, binary bytes, exclusive ownership, staged-read "
                     "gate, pending-read cancellation, and identity rejection passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
