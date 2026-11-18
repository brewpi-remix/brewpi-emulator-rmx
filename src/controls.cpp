// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <algorithm>
#include <cmath>

namespace rmx {
namespace {
const std::string modes = "bfpo";
int cycle(int value, int direction, int count) {
    return (value + direction + count) % count;
}
std::string cell(const std::string& text) {
    if (text == "null")
        return " --.- ";
    return std::string(text.size() < 5 ? 5 - text.size() : 0, ' ') + text;
}
} // namespace
void Engine::local_cancel() {
    menu = {};
    ++local_epoch;
}
void Engine::local_tick(uint64_t wall) {
    menu.now = wall;
    if (menu.page != LocalMenu::idle && (wall < menu.changed || wall - menu.changed >= 10000))
        local_cancel();
    menu.now = wall;
}
std::array<int, 5> Engine::local_dependencies() const {
    // Ignore PID-derived fridge values while editing beer/mode/top-level selection.
    return {{settings.at("mode"),
             settings.at(menu.page == LocalMenu::fridge ? "fridgeSet" : "beerSet"),
             constants.at("tempFormat"), constants.at("tempSetMin"), constants.at("tempSetMax")}};
}
int Engine::local_to_tenths(int raw) const {
    auto nearest = [](int n, int d) { return (n + (n < 0 ? -d / 2 : d / 2)) / d; };
    int fixed = fahrenheit() ? nearest((raw + 33678) * 9, 5) : raw + 24576;
    return nearest(fixed * 10, 512);
}
int Engine::local_tenth(int tenth) const {
    // Quantize the display unit before the existing absolute-unit converter.
    int fixed = (tenth * 512 + 5) / 10;
    int raw = fixed;
    if (fahrenheit()) {
        int delta = fixed - 32 * 512;
        raw = (delta * 5 + (delta < 0 ? -4 : 4)) / 9;
    }
    return raw - 48 * 512;
}
std::string Engine::local_temperature(bool beer) {
    int lo = constants.at("tempSetMin"), hi = constants.at("tempSetMax");
    if (lo < -32766 || hi < -32766 || lo > hi) {
        local_cancel();
        return "Invalid bounds";
    }
    menu.page = beer ? LocalMenu::beer : LocalMenu::fridge;
    menu.proposed_mode = beer ? 'b' : 'f';
    int original = settings.at(beer ? "beerSet" : "fridgeSet");
    menu.target = std::clamp(original < -32766 ? absolute_raw(20) : original, lo, hi);
    menu.low = local_to_tenths(lo) - 2;
    while (local_tenth(menu.low) < lo)
        ++menu.low;
    menu.high = local_to_tenths(hi) + 2;
    while (local_tenth(menu.high) > hi)
        --menu.high;
    menu.rotated = false;
    return "Edit target";
}
std::string Engine::local_action(const std::string& action, uint64_t wall, bool writable) {
    local_tick(wall);
    ++local_epoch;
    if (action == "cancel") {
        local_cancel();
        return "Edit canceled";
    }
    if (action == "door open" || action == "door close") {
        bool open = action == "door open";
        bool same = plant.door_open() == open;
        plant.set_door(open);
        return same ? "Door unchanged" : open ? "Door opened" : "Door closed";
    }
    if (action == "help")
        return "cw ccw press door open/close";
    if (action != "cw" && action != "ccw" && action != "press")
        return "Unknown command";
    if (reading() || restarting() || dispatch_suspended() || !writable)
        return "Busy; retry action";
    menu.changed = wall;
    if (menu.page == LocalMenu::idle) {
        if (action == "press") {
            menu.page = LocalMenu::setting;
            menu.index = 0;
        }
        return "Action accepted";
    }
    int direction = action == "cw" ? 1 : -1;
    if (action != "press") {
        if (menu.page == LocalMenu::setting)
            menu.index = cycle(menu.index, direction, 3);
        else if (menu.page == LocalMenu::mode) {
            menu.index = menu.index < 0 ? (direction > 0 ? 0 : 3) : cycle(menu.index, direction, 4);
            menu.proposed_mode = modes[size_t(menu.index)];
        } else {
            if (menu.low > menu.high)
                return "No tenth in range";
            int current = local_to_tenths(menu.target);
            int next = current + direction;
            if (next > menu.high)
                next = menu.low;
            if (next < menu.low)
                next = menu.high;
            menu.target = local_tenth(next);
            menu.rotated = true;
        }
        return "Action accepted";
    }
    if (menu.page == LocalMenu::setting) {
        if (menu.index == 1 || menu.index == 2)
            return local_temperature(menu.index == 1);
        menu.page = LocalMenu::mode;
        auto index = modes.find(char(settings.at("mode")));
        menu.index = index == std::string::npos ? -1 : int(index);
        menu.proposed_mode = menu.index < 0 ? 0 : modes[index];
        return menu.index < 0 ? "Choose valid mode" : "Select mode";
    }
    if (menu.page == LocalMenu::mode) {
        if (menu.index < 0 || menu.index > 3)
            return "Choose valid mode";
        if (menu.proposed_mode == 'b' || menu.proposed_mode == 'f')
            return local_temperature(menu.proposed_mode == 'b');
        int selected = menu.proposed_mode;
        mode(selected);
        render_display(); // A deliberate local confirmation repaints even while paused.
        local_cancel();
        telemetry(selected == 'p' ? "Changed to profile mode in menu."
                                  : "Temp control turned off in menu.");
        return "Mode committed";
    }
    bool beer = menu.page == LocalMenu::beer;
    int target = menu.target;
    if (target < constants.at("tempSetMin") || target > constants.at("tempSetMax")) {
        local_cancel();
        return "Bounds changed; retry";
    }
    int old = settings.at(beer ? "beerSet" : "fridgeSet");
    mode(beer ? 'b' : 'f');
    if (!beer || std::abs(word16(old - target)) > 256)
        positive_pending = negative_pending = false;
    settings[beer ? "beerSet" : "fridgeSet"] = target;
    command_evaluation();
    save(false);
    render_display();
    local_cancel();
    std::string value = number(target, 1, 1);
    std::string note =
        std::string(beer ? "Beer" : "Fridge") + " temp set to " + value + " in Menu.";
    note.resize(std::min(size_t(31), note.size()));
    telemetry(beer ? note : "", beer ? "" : note);
    return "Target committed";
}
std::array<std::string, 4> Engine::local_rows() const {
    auto rows = screen;
    if (menu.page == LocalMenu::idle)
        return rows;
    // The overlay is transient. The retained controller shadow remains checkpoint-exact.
    rows[2].replace(0, 6, "Fridge");
    auto fridge = targets.find(5);
    rows[2].replace(6, 6,
                    (cell(fridge == targets.end()
                              ? "null"
                              : number(reading_raw(fridge->second, true).value_or(-32768), 1, 1)) +
                     " ")
                        .substr(0, 6));
    rows[2].replace(12, 6, (cell(number(settings.at("fridgeSet"), 1, 1)) + " ").substr(0, 6));
    for (auto& row : rows)
        row.resize(20, ' ');
    bool hide = ((menu.now - menu.changed) / 384) % 2;
    if (menu.page == LocalMenu::setting) {
        if (hide)
            rows[size_t(menu.index)].replace(0, 6, "      ");
    } else if (menu.page == LocalMenu::mode) {
        const std::map<int, std::string> names{
            {'b', "Beer Const."}, {'f', "Fridge Const."}, {'p', "Beer Profile"}, {'o', "Off"}};
        auto found = names.find(menu.proposed_mode);
        std::string label = found == names.end() ? "Invalid mode" : found->second;
        rows[0].replace(7, 13,
                        hide ? std::string(13, ' ') : label + std::string(13 - label.size(), ' '));
    } else {
        rows[0].replace(7, 13, menu.page == LocalMenu::beer ? "Beer Const.  " : "Fridge Const.");
        rows[menu.page == LocalMenu::beer ? 1 : 2].replace(
            12, 6, hide ? "      " : (cell(number(menu.target, 1, 1)) + " ").substr(0, 6));
    }
    return rows;
}
} // namespace rmx
