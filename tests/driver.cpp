// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <cmath>
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
            } else if (op == "pid" || op == "outputs" || op == "state" || op == "sensors" ||
                       op == "peaks" || op == "sensor_peak") {
                int count = request.has("repeat") ? request.at("repeat").integer() : 1;
                if (count < 0 || count > 1000000)
                    throw std::runtime_error("invalid evaluation count");
                while (count-- > 0) {
                    if (op == "pid")
                        engine.evaluate_pid();
                    else if (op == "outputs")
                        engine.update_outputs();
                    else if (op == "state")
                        engine.evaluate_state();
                    else if (op == "sensors")
                        engine.update_sensors();
                    else if (op == "sensor_peak") {
                        engine.update_sensors();
                        engine.detect_peaks();
                    } else
                        engine.detect_peaks();
                    if (request.has("until_output") && request.at("until_output").boolean() &&
                        !wire.empty())
                        break;
                }
            } else if (op == "advance") {
                double ms = request.at("milliseconds").number();
                if (ms < 0 || ms > 9007199254740000.0 || ms != std::floor(ms))
                    throw std::runtime_error("invalid advance");
                int repeat = request.has("repeat") ? request.at("repeat").integer() : 1;
                if (repeat < 0 || repeat > 1000000)
                    throw std::runtime_error("invalid advance repeat");
                while (repeat-- > 0)
                    engine.advance_ms(uint64_t(ms), request.has("controller_allowed")
                                                        ? request.at("controller_allowed").boolean()
                                                        : true);
            } else if (op == "configure")
                engine.configure_plant(request.at("scenario"));
            else if (op == "restore")
                engine.restore_checkpoint(request.at("snapshot"));
            else if (op == "checkpoint") {
            } // Collected after common observation below.
            else if (op == "precondition")
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
            Json observations = engine.observations();
            if (op == "checkpoint")
                observations["checkpoint"] = engine.checkpoint();
            std::cout << Json(Json::Object{{"hex", hex}, {"observations", observations}}).dump()
                      << std::endl;
        } catch (const std::exception& e) {
            std::cout << Json(Json::Object{{"error", e.what()}}).dump() << std::endl;
        }
    }
}
