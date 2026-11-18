// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"
#include "lcd.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>

void require(bool value, const char* message = "LCD invariant failed") {
    if (!value)
        throw std::runtime_error(message);
}
int main() {
    using namespace rmx;
    for (auto profile : {Profile::revc, Profile::i2c}) {
        std::string wire;
        Engine engine([&](const std::string& bytes) { wire += bytes; }, profile);
        const char degree = char(profile == Profile::i2c ? 0xdf : 0xb0);
        const char other_degree = char(profile == Profile::i2c ? 0xb0 : 0xdf);
        auto check = [&](char unit) {
            auto raw = engine.lcd_rows();
            bool replaced;
            auto display = unicode_lcd(raw, replaced);
            require(!replaced, "profile degree was replaced in local display");
            for (size_t row : {1u, 2u}) {
                require(raw[row].size() == 20);
                require(raw[row][18] == degree, "wrong profile degree byte in shadow");
                require(raw[row][19] == unit, "wrong temperature unit in shadow");
                require(display[row].substr(18) == std::string("\xc2\xb0") + unit,
                        "wrong local Unicode degree cell");
            }
            wire.clear();
            engine.feed("l");
            require(wire.substr(0, 2) == "L:");
            require(wire.substr(wire.size() - 2) == "\r\n");
            require(std::count(wire.begin(), wire.end(), degree) == 2);
            require(wire.find(other_degree) == std::string::npos);
            require(wire.find("\xc2\xb0") == std::string::npos);
            std::string expected = "L:[";
            for (size_t row = 0; row < raw.size(); ++row) {
                if (row)
                    expected += ',';
                expected += '"' + raw[row] + '"';
            }
            require(wire == expected + "]\r\n", "serial LCD differs from shadow bytes");
        };
        engine.boot(false);
        check('C');
        engine.feed("E");
        check('C');
        engine.feed("j{tempFormat:F}");
        check('F');
        engine.feed("C");
        check('C');
        engine.feed("j{tempFormat:C}R");
        engine.restart(false);
        check('C');
        const auto checkpoint = engine.checkpoint();
        engine.restore_checkpoint(checkpoint);
        check('C');
    }
    for (auto profile : {Profile::revc, Profile::i2c}) {
        const auto hardware = profile_hardware(profile);
        Engine equipment([](const std::string&) {}, profile);
        equipment.feed("EU{i:3,f:2,h:1,p:" + std::to_string(hardware.heater) +
                       ",x:1}j{mode:t}d{i:3,w:1}");
        require(equipment.local_equipment() == EquipmentStates{{1, 0, 0, 0}},
                "active-low physical heater was not shown");
        auto snapshot = equipment.checkpoint();
        for (int i = 0; i < 20; ++i)
            require(equipment.local_equipment()[0] == 1);
        require(equipment.checkpoint().dump() == snapshot.dump(), "indicator mutated engine");
        equipment.feed("U{i:3,f:0}j{mode:o}");
        equipment.advance_ms(1000);
        require(equipment.local_equipment()[0] == 1,
                "orphaned electrical latch was replaced with controller intent");
        equipment.feed("U{i:3,f:2,h:1,p:" + std::to_string(hardware.heater) + ",x:1}");
        require(equipment.local_equipment()[0] == 0);
        for (const auto& output :
             {std::array<int, 3>{{3, hardware.cooler, 1}}, std::array<int, 3>{{7, hardware.fan, 2}},
              std::array<int, 3>{{4, hardware.light, 3}}}) {
            equipment.feed("j{mode:t}U{i:4,f:" + std::to_string(output[0]) +
                           ",h:1,p:" + std::to_string(output[1]) + ",x:1}d{i:4,w:1}");
            EquipmentStates expected{{0, 0, 0, 0}};
            expected[size_t(output[2])] = 1;
            require(equipment.local_equipment() == expected, "wrong default load indicator");
            equipment.feed("d{i:4,w:0}");
            require(equipment.local_equipment() == EquipmentStates{{0, 0, 0, 0}});
        }
        equipment.configure_plant(Json::Object{{"physical_loads", Json::Array{}}});
        require(equipment.local_equipment() == EquipmentStates{{-1, -1, -1, -1}});
        equipment.configure_plant(Json::Object{
            {"physical_loads",
             Json::Array{
                 Json::Object{{"pin", 8}, {"kind", "fan"}, {"watts", 0}, {"active_low", false}},
                 Json::Object{{"pin", 9}, {"kind", "fan"}, {"watts", 0}, {"active_low", true}}}}});
        equipment.feed("j{mode:t}U{i:3,f:4,h:1,p:8,x:0}d{i:3,w:1}");
        require(equipment.local_equipment() == EquipmentStates{{-1, -1, 1, -1}},
                "custom zero-watt physical fan was inferred from its logical light role");
        equipment.feed("d{i:3,w:0}U{i:4,f:2,h:1,p:9,x:1}d{i:4,w:1}");
        require(equipment.local_equipment()[2] == 1, "multiple physical fans were not combined");
        equipment.feed("d{i:4,w:0}");
        require(equipment.local_equipment()[2] == 0);
        snapshot = equipment.checkpoint();
        Engine resumed([](const std::string&) {}, profile);
        resumed.restore_checkpoint(snapshot);
        require(resumed.local_equipment() == equipment.local_equipment());
    }
    for (unsigned value = 0; value < 256; ++value) {
        LcdRows input;
        input.fill(std::string(20, char(value)));
        bool replaced;
        auto output = unicode_lcd(input, replaced);
        std::string expected;
        for (int n = 0; n < 20; ++n)
            expected += (value == 0xb0 || value == 0xdf)
                            ? "\xc2\xb0"
                            : (value >= 32 && value <= 126 ? std::string(1, char(value)) : "?");
        for (const auto& row : output)
            require(row == expected);
        require(replaced == !(value == 0xb0 || value == 0xdf || (value >= 32 && value <= 126)));
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
    plain.boot(false);
    viewed.boot(false);
    for (const std::string command :
         {"E", "j{mode:f,fridgeSet:21}", "l", "j{tempFormat:F}", "l", "R", "l"}) {
        plain.feed(command);
        viewed.feed(command);
        if (plain.restarting()) {
            plain.restart(false);
            viewed.restart(false);
        }
        auto before = viewed.checkpoint().dump();
        for (int n = 0; n < 20; ++n) {
            auto rows = viewed.lcd_rows();
            viewed.local_equipment();
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
    std::cout << "LCD adapter: profile degree bytes, 256 bytes, cell geometry, immutable accessor, "
                 "wire/checkpoint "
                 "parity passed\n";
}
