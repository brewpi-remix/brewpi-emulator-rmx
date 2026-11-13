// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <iostream>
#include <memory>
#include <stdexcept>
using rmx::Json;
int main() {
    std::string wire;
    rmx::Engine engine([&](const std::string& s) { wire += s; });
    std::string line;
    while (std::getline(std::cin, line)) {
        try {
            auto request = Json::parse(line);
            auto op = request.at("op").string();
            wire.clear();
            if (op == "construct")
                engine.construct(request.at("state"));
            else if (op == "feed") {
                std::string bytes;
                if (request.has("bytes_hex")) {
                    std::string hex = request.at("bytes_hex").string();
                    if (hex.size() % 2)
                        throw std::runtime_error("odd input hex");
                    for (size_t i = 0; i < hex.size(); i += 2) {
                        auto pair = hex.substr(i, 2);
                        if (pair.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos)
                            throw std::runtime_error("invalid input hex");
                        bytes += static_cast<char>(std::stoi(pair, nullptr, 16));
                    }
                } else
                    bytes = request.at("bytes").string();
                engine.feed(bytes);
            } else if (op == "timeout")
                engine.read_timeout();
            else if (op == "boot")
                engine.boot();
            else if (op == "restart") {
                if (!engine.restarting())
                    throw std::runtime_error("restart barrier without R");
                engine.restart();
            } else if (op == "precondition")
                engine.precondition(request.at("fields"));
            else
                throw std::runtime_error("unknown test operation");
            // Hex is a lossless envelope for the protocol's non-UTF-8 LCD byte.
            const char* digits = "0123456789ABCDEF";
            std::string hex;
            for (char ch : wire) {
                auto c = static_cast<unsigned char>(ch);
                hex += digits[c >> 4];
                hex += digits[c & 15];
            }
            std::cout
                << Json(Json::Object{{"hex", hex}, {"observations", engine.observations()}}).dump()
                << std::endl;
        } catch (const std::exception& e) {
            std::cout << Json(Json::Object{{"error", e.what()}}).dump() << std::endl;
        }
    }
}
