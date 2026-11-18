// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace rmx {
namespace {
int product(int factor, int64_t value) {
    return temperature_limit(signed_shift(word32(int64_t(factor) * value), 9));
}
bool invalid(int raw) {
    return raw == -32768 || raw == -32767;
}
bool hot(int state) {
    return state == 3 || state == 9;
}
bool cold(int state) {
    return state == 4 || state == 8;
}
std::string hex(const std::string& text) {
    const char* h = "0123456789ABCDEF";
    std::string s;
    for (char c : text) {
        unsigned v = static_cast<unsigned char>(c);
        s += h[v >> 4];
        s += h[v & 15];
    }
    return s;
}
std::string unhex(const std::string& s) {
    if (s.size() % 2 || s.find_first_not_of("0123456789ABCDEF") != std::string::npos)
        throw std::runtime_error("invalid checkpoint hex");
    std::string r;
    for (size_t i = 0; i < s.size(); i += 2)
        r += char(std::stoi(s.substr(i, 2), nullptr, 16));
    return r;
}
Json pack(const std::map<std::string, int>& values) {
    Json o(Json::Object{});
    for (auto& p : values)
        o[p.first] = p.second;
    return o;
}
std::map<std::string, int> unpack(const Json& j) {
    std::map<std::string, int> m;
    for (auto& e : j.object())
        m[e.first] = e.second.integer();
    return m;
}
uint32_t u32(const Json& j) {
    double d = j.number();
    if (d < 0 || d > 4294967295.0 || d != std::floor(d))
        throw std::runtime_error("invalid checkpoint unsigned word");
    return uint32_t(d);
}
uint16_t u16(const Json& j) {
    auto v = u32(j);
    if (v > 65535)
        throw std::runtime_error("invalid checkpoint timestamp");
    return uint16_t(v);
}
uint64_t exact_count(const Json& j) {
    double d = j.number();
    if (!std::isfinite(d) || d < 0 || d > 9007199254740991.0 || d != std::floor(d))
        throw std::runtime_error("invalid checkpoint exact counter");
    return uint64_t(d);
}
} // namespace
std::optional<size_t> Engine::physical_index(const Device& d) {
    static const std::array<std::string, 3> ids{
        {"28A10100000001E6", "28A1010000000204", "28A101000000035A"}};
    for (size_t i = 0; i < ids.size(); ++i)
        if (d.rom == ids[i])
            return i;
    return {};
}
void Engine::configure_plant(const Json& scenario) {
    plant.configure(scenario);
}
void Engine::apply_filter_constants() {
    for (auto f : {5, 9}) {
        std::string prefix = f == 5 ? "fridge" : "beer";
        auto& h = sensors.at(f);
        h.fast.coefficient = unsigned(constants.at(prefix + "FastFilt"));
        h.slow.coefficient = unsigned(constants.at(prefix + "SlowFilt"));
        h.slope.coefficient = unsigned(constants.at(prefix + "SlopeFilt"));
    }
}
int Engine::filtered(int function, int kind) const {
    auto& h = sensors.at(function);
    return kind == 0 ? h.fast.value() : kind == 1 ? h.slow.value() : h.slope.value();
}
void Engine::update_sensors(bool ordinary_loop) {
    if (initialization)
        return;
    const std::array<int, 3> order{{9, 5, 6}};
    while (sensor_cursor < order.size()) {
        int f = order[sensor_cursor++];
        auto& history = sensors.at(f);
        auto target = targets.find(f);
        auto raw = target == targets.end() ? std::optional<int>{} : reading_raw(target->second);
        bool was_connected = history.connected;
        if (raw && *raw == -32768) {
            if (f != 6)
                history.missed = std::min(255u, history.missed + 1);
            continue;
        }
        if (was_connected && raw) {
            if (f != 6)
                history.sample(*raw);
            continue;
        }
        if (f != 6)
            history.missed = std::min(255u, history.missed + 1);
        if (was_connected && target != targets.end() && !target->second.d)
            diagnostic('W', 2, {target->second.p, target->second.rom});
        history.connected = false;
        if (target == targets.end())
            continue;
        if (start_initialization(target->second,
                                 ordinary_loop ? InitPurpose::loop : InitPurpose::sensors))
            return;
        finish_sensor_initialization(target->second, false);
    }
    sensor_cursor = 0;
}
void Engine::evaluate_pid() {
    int m = settings.at("mode");
    if (m == 'f') {
        settings["beerSet"] = -32767;
        return;
    }
    if (m != 'b' && m != 'p')
        return;
    int target = settings.at("beerSet");
    if (invalid(target)) {
        settings["fridgeSet"] = -32767;
        return;
    }
    int error = word16(target - filtered(9, 1));
    variables["beerDiff"] = error;
    variables["beerSlope"] = filtered(9, 2);
    if (integral_counter++ == 60) {
        integral_counter = 0;
        ++integral_branches;
        int update = error;
        if (state != 0)
            update = 0;
        else if (error == -32768)
            throw std::runtime_error(
                "fidelity gap: PID signed absolute-value overflow requires characterization");
        else if (std::abs(error) < constants.at("iMaxErr")) {
            bool increasing = (error > 0) == (variables.at("diffIntegral") > 0);
            if (increasing) {
                int previous = settings.at("fridgeSet"), measured = filtered(5, 0);
                bool saturated = previous >= constants.at("tempSetMax") ||
                                 previous <= constants.at("tempSetMin") ||
                                 word16(previous - target) >= constants.at("pidMax") ||
                                 word16(target - previous) >= constants.at("pidMax") ||
                                 (error <= 0 && measured > word16(previous + 1024)) ||
                                 (error > 0 && measured < word16(previous - 1024));
                if (saturated)
                    update = 0;
            } else
                update = word16(update * 2);
        } else
            update = word16(-signed_shift(variables.at("diffIntegral"), 3));
        variables["diffIntegral"] = word32(int64_t(variables.at("diffIntegral")) + update);
    }
    variables["p"] = product(constants.at("Kp"), error);
    variables["i"] = product(constants.at("Ki"), variables.at("diffIntegral"));
    variables["d"] = product(constants.at("Kd"), variables.at("beerSlope"));
    int low = target <= word16(constants.at("tempSetMin") + constants.at("pidMax"))
                  ? constants.at("tempSetMin")
                  : word16(target - constants.at("pidMax"));
    int high = target >= word16(constants.at("tempSetMax") - constants.at("pidMax"))
                   ? constants.at("tempSetMax")
                   : word16(target + constants.at("pidMax"));
    int desired = temperature_limit(int64_t(target) + variables.at("p") + variables.at("i") +
                                    variables.at("d"));
    settings["fridgeSet"] = desired < low ? low : desired > high ? high : desired;
}
bool Engine::configured_actuator(int f) const {
    auto t = targets.find(f);
    return t != targets.end() && !t->second.d && t->second.h == 1;
}
void Engine::evaluate_state() {
    bool sensed = false;
    auto door = targets.find(1);
    if (door != targets.end())
        sensed = sense_switch(door->second);
    if (sensed != door_open) {
        door_open = sensed;
        telemetry("", std::string("Fridge door ") + (door_open ? "opened" : "closed"));
    }
    bool beer_mode = settings.at("mode") == 'b' || settings.at("mode") == 'p',
         fridge_mode = settings.at("mode") == 'f';
    auto present = [&](int f) {
        auto t = targets.find(f);
        return t != targets.end() && reading_raw(t->second, true).has_value();
    };
    bool forced = settings.at("mode") == 'o';
    if (forced)
        state = 1;
    if (invalid(settings.at("fridgeSet")) || !present(5) || (beer_mode && !present(9))) {
        state = 0;
        forced = true;
    }
    int fridge = filtered(5, 0), beer = filtered(9, 0), target = settings.at("fridgeSet"),
        beer_target = settings.at("beerSet");
    const uint16_t idle_age = since(last_idle), heat_age = since(last_heat),
                   cool_age = since(last_cool), now = seconds();
    if (hot(state) || cold(state)) {
        bool cooling = cold(state);
        if (cooling) {
            negative_pending = true;
            last_cool = now;
        } else {
            positive_pending = true;
            last_heat = now;
        }
        int duration = std::min<int>(
            idle_age, constants.at(cooling ? "maxCoolTimeForEst" : "maxHeatTimeForEst"));
        int overshoot =
            word16(word32(int64_t(settings.at(cooling ? "coolEst" : "heatEst")) * duration) / 3600);
        variables["estPeak"] = word16(fridge + (cooling ? -overshoot : overshoot));
        bool reached =
            cooling ? variables.at("estPeak") <= target : variables.at("estPeak") >= target;
        bool beer_reached = !fridge_mode && (cooling ? beer < word16(beer_target - 16)
                                                     : beer > word16(beer_target + 16));
        state = cooling ? 4 : 3;
        if (reached || beer_reached) {
            state = idle_age > 180 ? 0 : cooling ? 8 : 9;
            if (state == 0)
                variables[cooling ? "negPeakEst" : "posPeakEst"] = variables.at("estPeak");
        }
        return;
    }
    if (state != 0 && state != 1 && state != 5 && state != 6 && state != 7 && state != 10)
        return;
    last_idle = now;
    if (forced)
        return;
    wait_seconds = 0;
    auto wait_for = [&](int threshold, uint16_t age) {
        if (age < threshold)
            wait_seconds = uint16_t(std::max<int>(wait_seconds, threshold - age));
    };
    int direction = fridge > word16(target + constants.at("idleRangeH"))   ? -1
                    : fridge < word16(target + constants.at("idleRangeL")) ? 1
                                                                           : 0;
    if (direction == 0) {
        state = 0;
        return;
    }
    bool cooling = direction < 0;
    wait_for(600, cooling ? heat_age : cool_age);
    if (!cooling)
        wait_for(300, heat_age);
    if (!fridge_mode &&
        (cooling ? beer < word16(beer_target + 16) : beer > word16(beer_target - 16))) {
        state = 0;
        return;
    }
    if (cooling)
        wait_for(fridge_mode ? 600 : 300, cool_age);
    bool available =
        cooling ? configured_actuator(3)
                : configured_actuator(2) || (constants.at("lah") && configured_actuator(4));
    if (available)
        state = wait_seconds ? (cooling ? 5 : 6) : (cooling ? 4 : 3);
    if (hot(state) || cold(state)) {
        if (negative_pending)
            wait_for(1800, cool_age);
        else if (positive_pending)
            wait_for(900, heat_age);
        else
            return;
        state = 7;
    }
}
bool Engine::sense_switch(const Device& device) const {
    if (device.d)
        return false;
    bool electrical = device.p == plant.door_input_pin()
                          ? plant.door_open() != profile_hardware(profile).door_active_low
                          : (pins.count(device.p) ? pins.at(device.p) : false);
    return electrical != bool(device.x);
}
void Engine::write_actuator(int f, bool active) {
    auto t = targets.find(f);
    if (t == targets.end() || t->second.d)
        fallback = active;
    else
        pins[t->second.p] = active != bool(t->second.x);
}
void Engine::update_outputs() {
    if (settings.at("mode") == 't')
        return;
    if (since(camera_last) >= 600)
        camera = false;
    write_actuator(3, cold(state));
    write_actuator(2, hot(state));
    write_actuator(4, door_open || (constants.at("lah") && hot(state)) || camera);
    write_actuator(7, hot(state) || cold(state));
}
void Engine::detect_peaks() {
    bool positive = positive_pending && !hot(state);
    bool negative = !positive && negative_pending && !cold(state);
    if (!positive && !negative)
        return;
    auto& signal = sensors.at(5).slow;
    auto found = signal.turn(positive);
    int peak = found.value_or(-32768),
        estimate = variables.at(positive ? "posPeakEst" : "negPeakEst");
    int error = word16(peak - estimate), old = settings.at(positive ? "heatEst" : "coolEst"),
        event = 0;
    bool increase = false, decrease = false;
    if (found) {
        int lo = constants.at(positive ? "heatTargetL" : "coolTargetL"),
            hi = constants.at(positive ? "heatTargetH" : "coolTargetH");
        increase = positive ? error > hi : error < lo;
        decrease = positive ? error < lo : error > hi;
        event = positive ? 17 : 18;
    } else if (since(positive ? last_heat : last_cool) > (positive ? 900 : 1800)) {
        int current = filtered(5, 0),
            threshold = word16(estimate + constants.at(positive ? "heatTargetL" : "coolTargetH"));
        if (positive ? current < threshold : current > threshold) {
            peak = current;
            decrease = true;
            event = positive ? 19 : 20;
        } else {
            if (positive)
                positive_pending = false;
            else
                negative_pending = false;
        }
    }
    if (!event)
        return;
    if (error == -32768)
        throw std::runtime_error(
            "fidelity gap: sentinel-derived adaptation arithmetic requires characterization");
    auto name = positive ? "heatEst" : "coolEst";
    if (increase) {
        int factor = 614 + std::clamp(std::abs(error) / 32, 0, 154);
        settings[name] = std::max(25, product(factor, settings.at(name)));
        save(false);
    }
    if (decrease) {
        int factor = 426 - std::clamp(std::abs(error) / 32, 0, 85);
        settings[name] = product(factor, settings.at(name));
        save(false);
    }
    variables[positive ? "posPeak" : "negPeak"] = peak;
    if (positive)
        positive_pending = false;
    else
        negative_pending = false;
    diagnostic('I', event,
               {number(peak, 1, 1), number(estimate, 1, 1), number(old, 3, 0),
                number(settings.at(name), 3, 0)});
}
void Engine::loop_evaluation() {
    update_sensors(true);
    if (!initialization)
        finish_loop_evaluation();
}
void Engine::finish_loop_evaluation() {
    detect_peaks();
    evaluate_pid();
    int old = state;
    evaluate_state();
    if (old != state)
        telemetry();
    update_outputs();
    render_display();
}
void Engine::service_controller(bool allowed) {
    if (uart_writing)
        return;
    if (initialization) {
        if (!allowed || uint32_t(controller_ms - initialization->started_ms) < 750)
            return;
        finish_initialization();
        return;
    }
    if (!display_reset_busy && allowed && !reading() && !restart_requested && service_menu())
        return;
    bool completed_reset = false;
    auto repaint = [&]() {
        for (auto& row : screen)
            row = std::string(20, ' ');
        screen_state = -1;
        screen_room = false;
        stationary_display();
        render_state();
    };
    if (display_reset_busy) {
        uint32_t wait_ms = profile == Profile::i2c ? i2c_display_wait_ms : revc_display_wait_ms;
        if (!allowed || uint32_t(controller_ms - display_reset_started_ms) < wait_ms)
            return;
        display_reset_busy = false;
        completed_reset = true;
        if (startup_display) {
            startup_display = false;
            boot(false);
            if (initialization)
                return;
        }
        repaint();
    }
    if (!completed_reset && allowed && !reading() && !restart_requested &&
        uint32_t(uint32_t(seconds()) - last_lcd_reset) >= 3600) {
        last_lcd_reset = seconds();
        display_reset_busy = true;
        display_reset_started_ms = controller_ms;
        return;
    }
    if (allowed && !reading() && !restart_requested &&
        uint32_t(controller_ms - last_evaluation_ms) >= 1000) {
        last_evaluation_ms = controller_ms;
        loop_evaluation();
    }
    if (!dispatch_suspended() && allowed && !reading() && !restart_requested &&
        (completed_reset || !deferred_serial.empty()) && !receiving) {
        ++dispatch_generation;
        auto queued = std::move(deferred_serial);
        deferred_serial.clear();
        feed(queued);
    }
}
void Engine::advance_ms(uint64_t ms, bool allowed, bool startup_only) {
    if (ms > 9007199254740000ULL - pending_ms || plant.elapsed_ms + ms > 9007199254740000ULL)
        throw std::runtime_error("simulation clock exhausted exact checkpoint range");
    pending_ms += ms;
    service_controller(allowed);
    if (startup_only && !startup) {
        pending_ms = 0;
        return;
    }
    while (pending_ms >= 100) {
        plant.step(pins);
        controller_ms += 100;
        pending_ms -= 100;
        service_controller(allowed);
        if (startup_only && !startup) {
            pending_ms = 0;
            break;
        }
    }
}
void Engine::reset_display() {
    screen = {{"Mode   Off          ",
               "Beer   --.-  --.- \xB0"
               "C",
               "Fridge --.-  --.- \xB0"
               "C",
               "Idling for     00m00"}};
    screen_state = 0;
    screen_room = false;
    stationary_display();
}
void Engine::stationary_display() {
    auto place = [&](size_t row, size_t col, const std::string& text) {
        for (char c : text) {
            if (col >= 20)
                break;
            screen[row][col++] = c;
        }
    };
    place(0, 0, "Mode");
    place(1, 0, "Beer ");
    place(2, 0, screen_room ? "Room  " : "Fridge ");
    for (auto row : {1u, 2u}) {
        screen[row][18] = char(profile == Profile::i2c ? 0xdf : 0xb0);
        screen[row][19] = char(constants.at("tempFormat"));
    }
}
void Engine::render_display() {
    auto place = [&](size_t row, size_t col, const std::string& text) {
        for (char c : text) {
            if (col >= 20)
                break;
            screen[row][col++] = c;
        }
    };
    auto read = [&](int f) {
        auto t = targets.find(f);
        if (t == targets.end())
            return std::optional<int>{};
        if (f == 6) {
            std::string diagnostic;
            auto raw = read_probe(t->second, diagnostic);
            if (!diagnostic.empty())
                serial_write(diagnostic);
            return raw;
        }
        return reading_raw(t->second, true);
    };
    bool room = (seconds() & 8) == 0 && read(6).has_value();
    if (room != screen_room) {
        screen_room = room;
        stationary_display();
    }
    auto cell = [&](size_t row, size_t col, std::optional<int> raw) {
        std::string s = raw ? number(*raw, 1, 1) : "null";
        if (s == "null")
            s = " --.- ";
        else if (s.size() < 5)
            s = std::string(5 - s.size(), ' ') + s;
        place(row, col, s);
    };
    cell(1, 6, read(9));
    cell(1, 12, settings.at("beerSet"));
    cell(2, 6, read(room ? 6 : 5));
    cell(2, 12, room ? -32767 : settings.at("fridgeSet"));
    const std::map<int, std::string> modes{{'f', "Fridge Const."},
                                           {'b', "Beer Const."},
                                           {'p', "Beer Profile"},
                                           {'o', "Off"},
                                           {'t', "** Testing **"}};
    auto mode = modes.find(settings.at("mode"));
    std::string label = mode == modes.end() ? "Invalid mode" : mode->second;
    place(0, 7, label + std::string(13 - label.size(), ' '));
    render_state();
}
void Engine::render_state() {
    auto place = [&](size_t row, size_t col, const std::string& text) {
        for (char c : text) {
            if (col >= 20)
                break;
            screen[row][col++] = c;
        }
    };
    int displayed = door_open ? 2 : state;
    const std::array<std::string, 10> labels{
        {"Idling for", "Temp. control OFF", "Door open", "Heating for", "Cooling for",
         "Wait to Cool", "Wait to Heat", "Waiting for peak", "Cool time left", "Heat time left"}};
    if (displayed != screen_state) {
        screen_state = displayed;
        std::string text =
            displayed >= 0 && displayed < 10 ? labels[size_t(displayed)] : "Unknown status!";
        screen[3] = text + std::string(20 - text.size(), ' ');
    }
    std::optional<uint16_t> duration;
    if (displayed == 0)
        duration = std::min(since(last_cool), since(last_heat));
    else if (displayed == 3 || displayed == 4)
        duration = since(last_idle);
    else if (displayed == 8 || displayed == 9)
        duration = uint16_t(180 - since(last_idle));
    else if (displayed == 5 || displayed == 6)
        duration = wait_seconds;
    if (duration && *duration != 65535) {
        unsigned t = *duration;
        std::ostringstream time;
        if (t >= 3600)
            time << t / 3600 << 'h';
        time << std::setw(2) << std::setfill('0') << (t / 60) % 60 << 'm' << std::setw(2) << t % 60;
        std::string s = time.str();
        place(3, 20 - s.size(), s);
    }
}
Json Engine::checkpoint() const {
    if (reading() || restart_requested || uart_writing || uart_faulted || !uart_tx.empty() ||
        !uart_rx.empty() || uart_budget_us)
        throw std::runtime_error("checkpoint requires a quiescent command and drained UART");
    if (!deferred_serial.empty() && !display_reset_busy && !initialization &&
        menu.page == LocalMenu::idle)
        throw std::runtime_error("checkpoint contains unconsumed UART input");
    Json::Array ts, hs, ps, rows;
    for (auto& t : targets)
        ts.emplace_back(encode_device(t.second));
    for (auto& h : sensors)
        hs.emplace_back(Json::Object{{"function", h.first}, {"history", h.second.snapshot()}});
    for (auto& p : pins)
        ps.emplace_back(Json::Array{p.first, p.second});
    for (auto& r : screen)
        rows.emplace_back(hex(r));
    Json result = Json::Object{{"format", "brewpi-emulator-engine-checkpoint-v1"},
                               {"profile", profile_name(profile)},
                               {"store", store_image()},
                               {"settings", pack(settings)},
                               {"constants", pack(constants)},
                               {"variables", pack(variables)},
                               {"targets", ts},
                               {"histories", hs},
                               {"pins", ps},
                               {"plant", plant.snapshot()},
                               {"controller_ms", double(controller_ms)},
                               {"last_evaluation_ms", double(last_evaluation_ms)},
                               {"last_lcd_reset", double(last_lcd_reset)},
                               {"pending_ms", double(pending_ms)},
                               {"last_idle", int(last_idle)},
                               {"last_heat", int(last_heat)},
                               {"last_cool", int(last_cool)},
                               {"camera_last", int(camera_last)},
                               {"wait", int(wait_seconds)},
                               {"state", state},
                               {"last_saved_target", last_saved_target},
                               {"integral_counter", int(integral_counter)},
                               {"integral_branches", double(integral_branches)},
                               {"camera", camera},
                               {"alarm", alarm},
                               {"fallback", fallback},
                               {"door", door_open},
                               {"positive_pending", positive_pending},
                               {"negative_pending", negative_pending},
                               {"screen", rows},
                               {"screen_state", screen_state},
                               {"screen_room", screen_room}};
    if (encoder_value || encoder_seen || encoder_low || encoder_high || encoder_pressed ||
        menu.page != LocalMenu::idle)
        result["encoder"] = Json::Object{{"value", encoder_value},
                                         {"seen", encoder_seen},
                                         {"low", encoder_low},
                                         {"high", encoder_high},
                                         {"pressed", encoder_pressed}};
    if (menu.page != LocalMenu::idle)
        result["menu"] = Json::Object{{"page", int(menu.page)},
                                      {"target", menu.target},
                                      {"old_mode", menu.old_mode},
                                      {"old_room", menu.old_room},
                                      {"changed", int(menu.changed)},
                                      {"blink_started", double(menu.blink_started)},
                                      {"queued_hex", hex(deferred_serial)}};
    if (display_reset_busy)
        result["display_reset"] = Json::Object{{"started_ms", double(display_reset_started_ms)},
                                               {"queued_hex", hex(deferred_serial)}};
    if (startup)
        result["startup"] = startup_display ? "display" : "sensors";
    if (initialization) {
        const auto& i = *initialization;
        result["sensor_initialization"] = Json::Object{{"purpose", int(i.purpose)},
                                                       {"started_ms", double(i.started_ms)},
                                                       {"physical", int(i.physical)},
                                                       {"function", i.function},
                                                       {"slot", i.slot},
                                                       {"device", encode_device(i.device)},
                                                       {"cursor", int(sensor_cursor)},
                                                       {"queued_hex", hex(deferred_serial)}};
        Json parsed(Json::Object{});
        for (const auto& field : fields)
            parsed[std::string(1, field.first)] = field.second;
        result["sensor_initialization"]["fields"] = parsed;
        if (discovery) {
            result["sensor_initialization"]["discovery"] =
                Json::Object{{"cursor", int(discovery->cursor)},
                             {"carry", encode_device(discovery->carry)},
                             {"previous_hardware", discovery->previous_hardware},
                             {"has_row", discovery->has_row},
                             {"failed_wait", discovery->failed_wait}};
        }
    }
    return result;
}
void Engine::restore_checkpoint(const Json& j) {
    if (uart_writing || uart_faulted || receiving || !uart_tx.empty() || !uart_rx.empty() ||
        uart_budget_us)
        throw std::runtime_error("cannot restore over an active UART continuation");
    if (j.at("format").string() != "brewpi-emulator-engine-checkpoint-v1")
        throw std::runtime_error("unsupported checkpoint format");
    Profile captured = j.has("profile") ? parse_profile(j.at("profile").string()) : Profile::revc;
    if (captured != profile)
        throw std::runtime_error("checkpoint profile mismatch");
    Engine copy(output, profile);
    copy.load_store(j.at("store"));
    // Validate live words using the native store schema without applying a
    // firmware reload or mutating the captured saved configuration.
    Json live_store = j.at("store");
    live_store["controller_version"] = 4;
    live_store["settings_raw"] = j.at("settings");
    live_store["constants_raw"] = j.at("constants");
    Engine live([](const std::string&) {}, profile);
    live.load_store(live_store);
    copy.settings = live.saved_settings;
    copy.constants = live.saved_constants;
    copy.variables = unpack(j.at("variables"));
    if (copy.variables.size() != variables.size())
        throw std::runtime_error("invalid checkpoint variable fields");
    for (auto& entry : variables) {
        int v = copy.variables.at(entry.first);
        if (entry.first != "diffIntegral" && (v < -32768 || v > 32767))
            throw std::runtime_error("invalid checkpoint variable width");
    }
    for (auto& target : j.at("targets").array()) {
        for (auto name : {"c", "b", "f", "h", "d", "p", "x", "cal", "rom"})
            if (!target.has(name))
                throw std::runtime_error("missing checkpoint target field");
        if (target.object().size() != 9)
            throw std::runtime_error("invalid checkpoint target field count");
        Device d = decode_device(target);
        if (!copy.live_target(d) || copy.targets.count(d.f) || d.c < 0 || d.b < 0 || d.p < 0 ||
            d.p > 255 || d.cal < -128 || d.cal > 127 || (d.x != 0 && d.x != 1) ||
            (d.d != 0 && d.d != 1) || d.rom.size() != 16 ||
            d.rom.find_first_not_of("0123456789ABCDEF") != std::string::npos || live.validate(d))
            throw std::runtime_error("invalid checkpoint target");
        copy.targets[d.f] = d;
    }
    if (j.at("histories").array().size() != 3)
        throw std::runtime_error("incomplete checkpoint histories");
    std::map<int, bool> histories_seen;
    for (auto& h : j.at("histories").array()) {
        int f = h.at("function").integer();
        if (histories_seen.count(f))
            throw std::runtime_error("duplicate checkpoint history");
        histories_seen[f] = true;
        copy.sensors.at(f).restore(h.at("history"));
    }
    for (auto& p : j.at("pins").array()) {
        auto& a = p.array();
        if (a.size() != 2)
            throw std::runtime_error("invalid checkpoint pin");
        int pin = a[0].integer();
        if (pin < 0 || pin > 255 || copy.pins.count(pin))
            throw std::runtime_error("invalid checkpoint pin number");
        copy.pins[pin] = a[1].boolean();
    }
    copy.plant.restore(j.at("plant"));
    copy.controller_ms = u32(j.at("controller_ms"));
    copy.last_evaluation_ms = u32(j.at("last_evaluation_ms"));
    copy.last_lcd_reset = u32(j.at("last_lcd_reset"));
    if (j.has("display_reset")) {
        auto& pause = j.at("display_reset");
        if (pause.object().size() != 2)
            throw std::runtime_error("invalid checkpoint display reset");
        copy.display_reset_started_ms = u32(pause.at("started_ms"));
        copy.deferred_serial = unhex(pause.at("queued_hex").string());
        if (copy.deferred_serial.size() > uart_receive_capacity ||
            uint32_t(copy.controller_ms - copy.display_reset_started_ms) > 0x7fffffffu ||
            copy.last_lcd_reset != uint16_t(copy.display_reset_started_ms / 1000))
            throw std::runtime_error("invalid checkpoint display reset history");
        copy.display_reset_busy = true;
    }
    copy.pending_ms = u32(j.at("pending_ms"));
    if (copy.pending_ms >= 100)
        throw std::runtime_error("invalid checkpoint fractional clock");
    copy.last_idle = u16(j.at("last_idle"));
    copy.last_heat = u16(j.at("last_heat"));
    copy.last_cool = u16(j.at("last_cool"));
    copy.camera_last = u16(j.at("camera_last"));
    copy.wait_seconds = u16(j.at("wait"));
    copy.state = j.at("state").integer();
    copy.last_saved_target = j.at("last_saved_target").integer();
    if (copy.state < 0 || copy.state > 255 || copy.last_saved_target < -32768 ||
        copy.last_saved_target > 32767)
        throw std::runtime_error("invalid checkpoint controller word");
    int counter = j.at("integral_counter").integer();
    if (counter < 0 || counter > 60)
        throw std::runtime_error("invalid checkpoint PID counter");
    copy.integral_counter = unsigned(counter);
    copy.integral_branches = exact_count(j.at("integral_branches"));
    copy.camera = j.at("camera").boolean();
    copy.alarm = j.at("alarm").boolean();
    copy.fallback = j.at("fallback").boolean();
    copy.door_open = j.at("door").boolean();
    copy.positive_pending = j.at("positive_pending").boolean();
    copy.negative_pending = j.at("negative_pending").boolean();
    if (j.at("screen").array().size() != 4)
        throw std::runtime_error("invalid checkpoint display");
    for (size_t i = 0; i < 4; ++i) {
        copy.screen[i] = unhex(j.at("screen").array()[i].string());
        if (copy.screen[i].size() != 20)
            throw std::runtime_error("invalid checkpoint display row");
    }
    copy.screen_state = j.at("screen_state").integer();
    copy.screen_room = j.at("screen_room").boolean();
    if (j.has("sensor_initialization")) {
        const auto& init = j.at("sensor_initialization");
        int purpose = init.at("purpose").integer(), physical = init.at("physical").integer();
        int function = init.at("function").integer(), slot = init.at("slot").integer();
        int cursor = init.at("cursor").integer();
        auto started = u32(init.at("started_ms"));
        Device device = decode_device(init.at("device"));
        if (init.object().size() != (purpose == int(InitPurpose::discovery) ? 10u : 9u) ||
            !j.at("plant").has("probe_reset") || init.at("device").object().size() != 9 ||
            device.c < 0 || device.c > 4 || device.b < 0 || device.b > 6 || device.f < 0 ||
            device.f > 15 || device.cal < -128 || device.cal > 127 ||
            (device.x != 0 && device.x != 1) || copy.display_reset_busy || purpose < 0 ||
            purpose > 4 || physical < 0 || physical > 2 || cursor < 0 || cursor > 3 || slot < -1 ||
            slot > 15 || uint32_t(copy.controller_ms - started) > 0x7fffffffu ||
            !copy.physical_index(device) || *copy.physical_index(device) != size_t(physical) ||
            device.h != 2 || device.p != probe_pin(profile) || device.d)
            throw std::runtime_error("invalid checkpoint sensor initialization");
        if (purpose != int(InitPurpose::discovery) &&
            (function != device.f || !copy.targets.count(function) ||
             encode_device(copy.targets.at(function)).dump() != encode_device(device).dump()))
            throw std::runtime_error("invalid checkpoint initializing target");
        if ((purpose == int(InitPurpose::device) || purpose == int(InitPurpose::boot)) &&
            (slot < 0 || cursor != 0))
            throw std::runtime_error("invalid checkpoint initializing slot");
        if ((purpose == int(InitPurpose::sensors) || purpose == int(InitPurpose::loop)) &&
            (slot != -1 || cursor < 1 ||
             std::array<int, 3>{{9, 5, 6}}[size_t(cursor - 1)] != function))
            throw std::runtime_error("invalid checkpoint initializing cursor");
        if (purpose == int(InitPurpose::boot) &&
            encode_device(copy.slots[size_t(slot)]).dump() != encode_device(device).dump())
            throw std::runtime_error("invalid checkpoint boot device");
        copy.deferred_serial = unhex(init.at("queued_hex").string());
        if (copy.deferred_serial.size() > uart_receive_capacity)
            throw std::runtime_error("invalid checkpoint initialization queue");
        copy.fields.clear();
        for (const auto& entry : init.at("fields").object()) {
            int value = entry.second.integer();
            if (entry.first.size() != 1 || value < -128 || value > 127)
                throw std::runtime_error("invalid checkpoint initialization fields");
            copy.fields[entry.first[0]] = value;
        }
        if (purpose == int(InitPurpose::discovery)) {
            const auto& q = init.at("discovery");
            if (!copy.fields.count('v') || !copy.fields.at('v'))
                throw std::runtime_error("invalid checkpoint discovery value request");
            int row = q.at("cursor").integer();
            if (q.object().size() != 5 || row < 0 || row > 2 ||
                q.at("previous_hardware").integer() != 2 || q.at("failed_wait").boolean() ||
                slot != -1 || cursor != 0 ||
                std::array<int, 3>{{1, 0, 2}}[size_t(row)] != physical ||
                encode_device(decode_device(q.at("carry"))).dump() != encode_device(device).dump())
                throw std::runtime_error("invalid checkpoint discovery continuation");
            copy.discovery = Discovery{size_t(row), device, 2, q.at("has_row").boolean(), false};
        }
        copy.initialization =
            Initialization{InitPurpose(purpose), started, size_t(physical), function, slot, device};
        copy.sensor_cursor = size_t(cursor);
    }
    if (j.has("startup")) {
        auto stage = j.at("startup").string();
        if (stage == "display" && copy.display_reset_busy && !copy.initialization) {
            copy.startup_display = true;
        } else if (stage != "sensors" || !copy.initialization ||
                   copy.initialization->purpose != InitPurpose::boot)
            throw std::runtime_error("invalid checkpoint startup stage");
        copy.startup = true;
    }
    if (j.has("encoder")) {
        const auto& e = j.at("encoder");
        if (e.object().size() != 5)
            throw std::runtime_error("invalid checkpoint encoder fields");
        auto word = [&](const char* key) {
            int value = e.at(key).integer();
            if (value < -32768 || value > 32767)
                throw std::runtime_error("invalid checkpoint encoder word");
            return value;
        };
        copy.encoder_value = word("value");
        copy.encoder_seen = word("seen");
        copy.encoder_low = word("low");
        copy.encoder_high = word("high");
        copy.encoder_pressed = e.at("pressed").boolean();
    }
    if (j.has("menu")) {
        const auto& m = j.at("menu");
        int page = m.at("page").integer();
        if (m.object().size() != 7 || !j.has("encoder") || page < 1 || page > 4 ||
            copy.display_reset_busy || copy.initialization || copy.startup)
            throw std::runtime_error("invalid checkpoint menu continuation");
        copy.menu.page = LocalMenu::Page(page);
        copy.menu.target = m.at("target").integer();
        copy.menu.old_mode = m.at("old_mode").integer();
        copy.menu.old_room = m.at("old_room").boolean();
        copy.menu.changed = u16(m.at("changed"));
        copy.menu.blink_started = u32(m.at("blink_started"));
        copy.deferred_serial = unhex(m.at("queued_hex").string());
        if (copy.menu.target < -32766 || copy.menu.target > 32767 || copy.menu.old_mode < 0 ||
            copy.menu.old_mode > 255 || copy.screen_room ||
            uint16_t(copy.menu.blink_started / 1000) != copy.menu.changed ||
            uint32_t(copy.controller_ms - copy.menu.blink_started) > 0x7fffffffu ||
            copy.deferred_serial.size() > uart_receive_capacity)
            throw std::runtime_error("invalid checkpoint menu history");
        bool top = page == int(LocalMenu::setting), mode_page = page == int(LocalMenu::mode);
        int low = top || mode_page ? 0 : copy.local_to_tenths(copy.constants.at("tempSetMin"));
        int high = top ? 2 : mode_page ? 3 : copy.local_to_tenths(copy.constants.at("tempSetMax"));
        int active_mode = copy.settings.at("mode");
        if ((page == int(LocalMenu::beer) && active_mode != 'b') ||
            (page == int(LocalMenu::fridge) && active_mode != 'f') ||
            (mode_page && std::string("bfpo").find(char(active_mode)) == std::string::npos))
            throw std::runtime_error("invalid checkpoint menu mode");
        if (copy.encoder_low != low || copy.encoder_high != high ||
            ((top || mode_page) && (copy.encoder_value < low || copy.encoder_value > high)) ||
            (mode_page && std::string("bfpo").find(char(copy.menu.old_mode)) == std::string::npos))
            throw std::runtime_error("invalid checkpoint menu range");
    }
    if (copy.startup_display && !copy.deferred_serial.empty())
        throw std::runtime_error("checkpoint contains input before application UART enable");
    copy.save_callback = save_callback;
    copy.local_epoch = local_epoch + 1;
    *this = std::move(copy);
}
} // namespace rmx
