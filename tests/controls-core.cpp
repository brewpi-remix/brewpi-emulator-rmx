// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <iostream>
#include <stdexcept>
using namespace rmx;
void require(bool ok, const char* what) {
    if (!ok)
        throw std::runtime_error(what);
}
void profile_doors() {
    for (auto profile : {Profile::revc, Profile::i2c}) {
        std::string wire;
        Engine door([&](const std::string& text) { wire += text; }, profile);
        int inversion = profile == Profile::i2c ? 1 : 0;
        door.feed("EU{i:5,f:4,h:1,p:2,x:1}U{i:7,f:1,h:1,p:4,x:" + std::to_string(inversion) +
                  "}j{mode:o}");
        auto reading = [&](int slot) {
            wire.clear();
            door.feed("d{i:" + std::to_string(slot) + ",r:1}");
            return Json::parse(wire.substr(2)).array()[0].at("v").integer();
        };
        door.advance_ms(1000);
        require(!door.local_door() && reading(7) == 0 && reading(5) == 0,
                "closed physical door did not release its configured contact");
        for (bool open : {true, false}) {
            door.local_action(open ? "door open" : "door close", 1);
            door.advance_ms(1000);
            require(door.local_door() == open && reading(7) == int(open) && reading(5) == int(open),
                    "physical door action disagrees with controller door/light readback");
        }
        door.feed("U{i:7,f:1,x:" + std::to_string(1 - inversion) + "}");
        require(reading(7) == 1, "door wiring fix bypassed firmware inversion");
    }
}
int main() {
    profile_doors();
    std::string output;
    Engine engine([&](const std::string& s) { output += s; });
    engine.boot(false);
    engine.feed("Ej{mode:b,beerSet:20.023}");
    auto target = [&]() { return engine.checkpoint().at("settings").at("beerSet").integer(); };
    uint64_t now = 100;
    auto action = [&](const std::string& command) { return engine.local_action(command, ++now); };
    auto beer = [&]() {
        action("press");
        action("cw");
        action("press");
    };
    int original = target();
    auto before = engine.checkpoint().dump();
    auto output_before = output;
    beer();
    require(engine.checkpoint().dump() == before && output == output_before,
            "preview mutates controller");
    require(action("press") == "Target committed", "target confirmation failed");
    require(target() == original, "untouched target lost precision");
    before = engine.checkpoint().dump();
    beer();
    action("cw");
    now += 10000;
    engine.local_tick(now);
    require(engine.checkpoint().dump() == before, "timeout saves draft");
    require(action("press") == "Action accepted", "late press committed expired draft");
    engine.local_cancel();
    beer();
    action("cw");
    engine.feed("j{beerSet:21,beerSet:20.023}");
    require(action("press") == "Action accepted", "change-back did not cancel edit");
    engine.local_cancel();
    beer();
    engine.feed("j{tempSetMin:21}");
    require(target() == original, "serial bounds auto-clamped live target");
    require(action("press") == "Action accepted", "bounds change did not cancel edit");
    engine.local_cancel();
    beer();
    action("press");
    require(target() == absolute_raw(21), "local confirmation did not bound target");
    engine.feed("j{tempSetMin:1,tempSetMax:30,beerSet:30}");
    beer();
    action("cw");
    action("press");
    require(target() == absolute_raw(1), "temperature failed to wrap");
    engine.feed("j{tempFormat:F,beerSet:68.023}");
    original = target();
    beer();
    action("press");
    require(target() == original, "F unrotated target lost precision");
    beer();
    action("cw");
    action("press");
    require(target() > original, "F step did not increment");
    engine.feed("j{mode:x}");
    action("press");
    action("press");
    require(action("press") == "Choose valid mode", "invalid mode silently committed");
    action("cw");
    action("press");
    action("press");
    require(engine.checkpoint().at("settings").at("mode").integer() == 'b',
            "valid recovery failed");
    engine.feed("j{tempFormat:C,tempSetMin:30,tempSetMax:1}");
    require((beer(), engine.local_action("press", ++now)) == "Action accepted",
            "invalid range still editing");
    engine.local_cancel();
    engine.feed("j{tempSetMin:1,tempSetMax:30}");
    beer();
    auto checkpoint = engine.checkpoint();
    Engine resumed([](const std::string&) {});
    resumed.restore_checkpoint(checkpoint);
    require(resumed.lcd_rows() != engine.lcd_rows(), "checkpoint resurrected overlay");
    engine.local_cancel();
    require(action("door open") == "Door opened" && engine.local_door(), "door input failed");
    require(action("door open") == "Door unchanged", "door request not idempotent");
    engine.feed("R");
    engine.restart(false);
    require(engine.local_door(), "controller reset changed plant door");
    engine.feed("j{");
    require(action("press") == "Busy; retry action", "partial serial command accepted local edit");
    engine.read_timeout();
    require(engine.local_action("press", ++now, false) == "Busy; retry action",
            "backpressure accepted edit");
    engine.feed("Ej{mode:b,beerSet:20,hs:1}");
    beer();
    action("cw");
    action("press");
    require(target() == -14285, "logical step doubled in half-step mode");
    require(engine.lcd_rows()[1].substr(12, 6).find("20.1") != std::string::npos,
            "paused confirmation reverted to stale target display");
    engine.feed("j{tempSetMin:20.01,tempSetMax:20.02}");
    beer();
    require(action("cw") == "No tenth in range", "narrow interval selected invalid tenth");
    action("press");
    auto bounded = engine.checkpoint();
    require(target() >= bounded.at("constants").at("tempSetMin").integer() &&
                target() <= bounded.at("constants").at("tempSetMax").integer(),
            "narrow bound escaped");
    engine.feed("j{tempSetMin:1,tempSetMax:30,mode:b,beerSet:20}");
    before = engine.checkpoint().dump();
    action("press");
    action("press");
    action("ccw"); // preview off
    require(engine.checkpoint().dump() == before,
            "browsing off disabled targets or saved settings");
    now += 10000;
    engine.local_tick(now);
    require(engine.checkpoint().dump() == before, "mode timeout changed state");
    action("press");
    action("ccw");
    action("press"); // top wrap to fridge
    require(action("press") == "Target committed", "fridge confirmation failed");
    require(engine.checkpoint().at("settings").at("mode").integer() == 'f',
            "fridge mode not committed");
    engine.feed("EU{i:0,f:1,h:1,p:4,x:0}U{i:1,f:4,h:1,p:5,x:0}");
    action("door close");
    engine.advance_ms(1000);
    action("door open");
    engine.advance_ms(1000);
    require(engine.checkpoint().at("door").boolean(), "configured door not sensed");
    require(output.find("Fridge door opened") != std::string::npos, "door annotation missing");
    Engine plant_resume([](const std::string&) {});
    plant_resume.restore_checkpoint(engine.checkpoint());
    require(plant_resume.local_door(), "plant door was not checkpointed");
    engine.feed("U{i:0,f:1,h:1,p:4,x:1}");
    action("door close");
    engine.advance_ms(1000);
    require(engine.checkpoint().at("door").boolean(), "door inversion bypassed");
    Engine plain([](const std::string&) {}), editing([](const std::string&) {});
    plain.feed("Ej{mode:b,beerSet:20}");
    editing.feed("Ej{mode:b,beerSet:20}");
    editing.local_action("press", 0);
    for (int i = 1; i <= 8; ++i) {
        plain.advance_ms(1000);
        editing.advance_ms(1000);
        editing.local_tick(uint64_t(i) * 1000);
        require(plain.checkpoint().dump() == editing.checkpoint().dump(),
                "menu changed background evolution");
        for (const auto& row : editing.lcd_rows())
            require(row.size() == 20, "overlay row width changed");
    }
    engine.feed("Ej{mode:b,beerSet:20}");
    original = target();
    action("press");
    action("press");
    action("cw");
    action("cw");
    require(action("press") == "Mode committed", "profile confirmation failed");
    require(engine.checkpoint().at("settings").at("mode").integer() == 'p' && target() == original,
            "profile commit lost beer target");
    require(output.find("Changed to profile mode in menu") != std::string::npos,
            "profile annotation missing");
    action("press");
    action("press");
    action("cw");
    require(action("press") == "Mode committed", "off confirmation failed");
    require(target() == -32767 &&
                engine.checkpoint().at("settings").at("fridgeSet").integer() == -32767,
            "intentional off did not disable targets");
    require(output.find("Temp control turned off in menu") != std::string::npos,
            "off annotation missing");
    std::cout
        << "Controls precision, staging, range, conflicts, timeout, mode, door, resume passed\n";
}
