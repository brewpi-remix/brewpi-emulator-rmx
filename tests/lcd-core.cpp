// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"
#include "lcd.hpp"

#include <iostream>
#include <stdexcept>

void require(bool value) {
    if (!value)
        throw std::runtime_error("LCD invariant failed");
}
int main() {
    using namespace rmx;
    for (unsigned value = 0; value < 256; ++value) {
        LcdRows input;
        input.fill(std::string(20, char(value)));
        bool replaced;
        auto output = unicode_lcd(input, replaced);
        std::string expected;
        for (int n = 0; n < 20; ++n)
            expected += value == 0xb0
                            ? "\xc2\xb0"
                            : (value >= 32 && value <= 126 ? std::string(1, char(value)) : "?");
        for (const auto& row : output)
            require(row == expected);
        require(replaced == !(value == 0xb0 || (value >= 32 && value <= 126)));
        require(input[0] == std::string(20, char(value)));
    }
    bool replaced;
    bool rejected = false;
    try {
        unicode_lcd({}, replaced);
    } catch (const std::runtime_error&) {
        rejected = true;
    }
    require(rejected);
    std::string a, b;
    Engine plain([&](const std::string& bytes) { a += bytes; });
    Engine viewed([&](const std::string& bytes) { b += bytes; });
    plain.boot();
    viewed.boot();
    for (const std::string command :
         {"E", "j{mode:f,fridgeSet:21}", "l", "j{tempFormat:F}", "l", "R", "l"}) {
        plain.feed(command);
        viewed.feed(command);
        if (plain.restarting()) {
            plain.restart();
            viewed.restart();
        }
        auto before = viewed.checkpoint().dump();
        for (int n = 0; n < 20; ++n) {
            auto rows = viewed.lcd_rows();
            unicode_lcd(rows, replaced);
            rows[0][0] = '?'; // returned data is a copy
        }
        require(before == viewed.checkpoint().dump());
        plain.advance_ms(8000);
        viewed.advance_ms(8000);
        require(a == b);
        require(plain.checkpoint().dump() == viewed.checkpoint().dump());
    }
    require(a.find(char(0xb0)) != std::string::npos);
    std::cout << "LCD adapter: 256 bytes, cell geometry, immutable accessor, wire/checkpoint "
                 "parity passed\n";
}
