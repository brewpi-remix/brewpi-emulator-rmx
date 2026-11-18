// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <algorithm>
#include <cmath>

namespace rmx {
namespace {
const std::string modes = "bfpo";
std::string cell(const std::string& text) {
    if (text == "null")
        return " --.- ";
    return std::string(text.size() < 5 ? 5 - text.size() : 0, ' ') + text;
}
} // namespace
void Engine::local_cancel() {
    // Administrative cancellation never rolls back firmware-visible mutations.
    if (menu.page != LocalMenu::idle) {
        screen = local_rows();
        screen_room = menu.old_room;
        ++dispatch_generation;
    }
    menu = {};
    ++local_epoch;
}
void Engine::local_tick(uint64_t, bool writable) {
    // Native UI wall time does not advance the emulated firmware clock.
    if (encoder_pressed && writable && !reading() && !display_reset_busy && !initialization)
        service_controller();
}
int Engine::local_to_tenths(int raw) const {
    auto nearest = [](int n, int d) { return (n + (n < 0 ? -d / 2 : d / 2)) / d; };
    int fixed = fahrenheit() ? nearest((raw + 33678) * 9, 5) : raw + 24576;
    return nearest(fixed * 10, 512);
}
int Engine::local_tenth(int tenth) const {
    int fixed = (tenth * 512 + 5) / 10;
    int raw = fixed;
    if (fahrenheit()) {
        int delta = fixed - 32 * 512;
        raw = (delta * 5 + (delta < 0 ? -4 : 4)) / 9;
    }
    return std::clamp(raw - 48 * 512, -32766, 32767);
}
void Engine::menu_range(int value, int low, int high) {
    encoder_value = value;
    encoder_low = low;
    encoder_high = high;
    menu.changed = seconds();
    menu.blink_started = controller_ms;
}
void Engine::menu_temperature(bool beer) {
    menu.page = beer ? LocalMenu::beer : LocalMenu::fridge;
    menu.target = settings.at(beer ? "beerSet" : "fridgeSet");
    if (menu.target < -32766)
        menu.target = absolute_raw(20);
    menu_range(local_to_tenths(menu.target), local_to_tenths(constants.at("tempSetMin")),
               local_to_tenths(constants.at("tempSetMax")));
    menu_poll();
}
void Engine::menu_poll() {
    if (menu.page == LocalMenu::idle)
        return;
    if (since(menu.changed) >= 10) {
        if (menu.page == LocalMenu::mode)
            mode(menu.old_mode);
        local_cancel();
        return;
    }
    bool changed = encoder_value != encoder_seen || encoder_pressed;
    encoder_seen = encoder_value;
    if (changed) {
        menu.changed = seconds();
        menu.blink_started = controller_ms;
        if (menu.page == LocalMenu::mode) {
            if (encoder_value < 0 || encoder_value > 3)
                throw std::runtime_error(
                    "fidelity gap: invalid menu mode lookup requires characterization");
            mode(modes[size_t(encoder_value)]);
        } else if (menu.page == LocalMenu::beer || menu.page == LocalMenu::fridge)
            menu.target = local_tenth(encoder_value);
    }
    if (!encoder_pressed)
        return;
    encoder_pressed = false;
    if (menu.page == LocalMenu::setting) {
        if (encoder_value == 0) {
            auto found = modes.find(char(settings.at("mode")));
            if (found == std::string::npos)
                throw std::runtime_error(
                    "fidelity gap: invalid menu mode lookup requires characterization");
            menu.page = LocalMenu::mode;
            menu.old_mode = settings.at("mode");
            menu_range(int(found), 0, 3);
            menu_poll();
        } else {
            bool beer = encoder_value == 1;
            mode(beer ? 'b' : 'f');
            menu_temperature(beer);
        }
        return;
    }
    if (menu.page == LocalMenu::mode) {
        int selected = settings.at("mode");
        if (selected == 'b' || selected == 'f') {
            menu_temperature(selected == 'b');
            return;
        }
        telemetry(selected == 'p' ? "Changed to profile mode in menu."
                                  : "Temp control turned off in menu.");
    } else {
        bool beer = menu.page == LocalMenu::beer;
        int old = settings.at(beer ? "beerSet" : "fridgeSet");
        if (!beer || std::abs(word16(old - menu.target)) > 256)
            positive_pending = negative_pending = false;
        settings[beer ? "beerSet" : "fridgeSet"] = menu.target;
        command_evaluation();
        save(false);
        std::string note = std::string(beer ? "Beer" : "Fridge") + " temp set to " +
                           number(menu.target, 1, 1) + " in Menu.";
        note.resize(std::min(size_t(31), note.size()));
        telemetry(beer ? note : "", beer ? "" : note);
    }
    local_cancel();
}
bool Engine::service_menu() {
    if (menu.page == LocalMenu::idle && encoder_pressed) {
        encoder_pressed = false;
        menu.page = LocalMenu::setting;
        menu.old_room = screen_room;
        screen_room = false;
        stationary_display();
        menu_range(0, 0, 2);
    }
    menu_poll();
    return menu.page != LocalMenu::idle;
}
std::string Engine::local_action(const std::string& action, uint64_t, bool writable) {
    ++local_epoch;
    if (action == "cancel") {
        encoder_pressed = false;
        local_cancel();
        service_controller(writable);
        return "Menu closed; live changes retained";
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
    if (startup_display)
        return "Encoder unavailable during startup";
    if (action == "press")
        encoder_pressed = true;
    else {
        int next = word16(encoder_value + (action == "cw" ? 1 : -1));
        encoder_value = next > encoder_high  ? encoder_low
                        : next < encoder_low ? encoder_high
                                             : next;
    }
    if (!writable || reading() || restarting() || display_reset_busy || initialization)
        return "Encoder event retained";
    // Preserve an evidence limit without invoking undefined lookup memory.
    if (menu.page == LocalMenu::setting && encoder_pressed && encoder_value == 0 &&
        modes.find(char(settings.at("mode"))) == std::string::npos) {
        encoder_pressed = false;
        return "Fidelity gap: invalid menu mode lookup";
    }
    auto previous = menu.page;
    bool expired = previous != LocalMenu::idle && since(menu.changed) >= 10;
    service_controller(writable);
    if (previous != LocalMenu::idle && menu.page == LocalMenu::idle && action == "press" &&
        !expired)
        return previous == LocalMenu::beer || previous == LocalMenu::fridge ? "Target committed"
                                                                            : "Mode committed";
    if (previous != menu.page && (menu.page == LocalMenu::beer || menu.page == LocalMenu::fridge))
        return "Edit target";
    return "Action accepted";
}
std::array<std::string, 4> Engine::local_rows() const {
    auto rows = screen;
    if (menu.page == LocalMenu::idle)
        return rows;
    bool hide = ((uint32_t(controller_ms - menu.blink_started) / 384) % 2) != 0;
    if (menu.page == LocalMenu::setting) {
        if (hide)
            rows[size_t(encoder_value)].replace(0, 6, "      ");
    } else if (menu.page == LocalMenu::mode) {
        const std::map<int, std::string> names{
            {'b', "Beer Const."}, {'f', "Fridge Const."}, {'p', "Beer Profile"}, {'o', "Off"}};
        auto found = names.find(settings.at("mode"));
        std::string label = found == names.end() ? "Invalid mode" : found->second;
        rows[0].replace(7, 13,
                        hide ? std::string(13, ' ') : label + std::string(13 - label.size(), ' '));
    } else {
        const std::string label = menu.page == LocalMenu::beer ? "Beer Const.  " : "Fridge Const.";
        rows[0].replace(7, 13, label);
        rows[menu.page == LocalMenu::beer ? 1 : 2].replace(
            12, 6, hide ? "      " : (cell(number(menu.target, 1, 1)) + " ").substr(0, 6));
    }
    return rows;
}
} // namespace rmx
