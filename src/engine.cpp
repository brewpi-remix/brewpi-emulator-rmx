// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace rmx {
namespace {
using Fields = std::vector<std::pair<std::string, std::string>>;
std::string object(const Fields& fields) {
    std::string out = "{";
    for (auto& e : fields) {
        if (out.size() > 1)
            out += ',';
        out += Json(e.first).dump() + ':' + e.second;
    }
    return out + '}';
}
// Protocol strings deliberately do not acquire local-JSON escaping semantics.
std::string wire_string(const std::string& s) {
    return '"' + s + '"';
}
std::string diagnostic_body(char type, int id, const Json::Array& args) {
    std::string values = "[";
    for (auto& arg : args) {
        if (values.size() > 1)
            values += ',';
        values +=
            std::holds_alternative<std::string>(arg.value) ? wire_string(arg.string()) : arg.dump();
    }
    return object({{"logType", wire_string(std::string(1, type))},
                   {"logID", std::to_string(id)},
                   {"V", values + ']'}});
}
long long ratio(long long n, long long divisor) {
    return n < 0 ? -((-n + divisor / 2) / divisor) : (n + divisor / 2) / divisor;
}
int narrow8(long long n) {
    int b = int(n & 255);
    return b >= 128 ? b - 256 : b;
}
int narrow16(long long n) {
    int b = int(n & 65535);
    return b >= 32768 ? b - 65536 : b;
}
long long integer_token(const std::string& s) {
    size_t n = 0;
    bool minus = false;
    while (n < s.size() && std::isspace(static_cast<unsigned char>(s[n])))
        ++n;
    if (n < s.size() && (s[n] == '-' || s[n] == '+')) {
        minus = s[n++] == '-';
    }
    long long v = 0;
    while (n < s.size() && s[n] >= '0' && s[n] <= '9') {
        if (v > 214748364LL || (v == 214748364LL && s[n] > (minus ? '8' : '7')))
            throw std::runtime_error("fidelity gap: AVR long overflow requires characterization");
        v = v * 10 + s[n++] - '0';
    }
    return minus ? -v : v;
}
struct NumericPrefix {
    long long value;
    size_t end;
};
std::optional<NumericPrefix> custom_prefix(const std::string& text) {
    size_t end = text.find_first_not_of("-0123456789");
    if (end == std::string::npos)
        end = text.size();
    auto digits = text.substr(0, end);
    bool negative = digits.find('-') != std::string::npos;
    digits.erase(std::remove(digits.begin(), digits.end(), '-'), digits.end());
    if (digits.empty())
        return {};
    auto leading = digits.find_first_not_of('0');
    digits = leading == std::string::npos ? "0" : digits.substr(leading);
    const std::string limit = negative ? "2147483648" : "2147483647";
    if (digits.size() > limit.size() || (digits.size() == limit.size() && digits > limit))
        throw std::runtime_error("fidelity gap: numeric prefix overflow requires characterization");
    long long n = std::stoll(digits);
    return NumericPrefix{negative ? -n : n, end};
}
int type_of(int f) {
    if (f == 5 || f == 6 || f == 9 || f == 10)
        return 1;
    if (f == 1)
        return 2;
    if (f == 2 || f == 3 || f == 4 || f == 7 || f == 11 || f == 12)
        return 3;
    return 0;
}
const std::vector<std::string> skeys = {"mode", "beerSet", "fridgeSet", "heatEst", "coolEst"};
const std::vector<std::string> ckeys = {"tempFormat",
                                        "tempSetMin",
                                        "tempSetMax",
                                        "pidMax",
                                        "Kp",
                                        "Ki",
                                        "Kd",
                                        "iMaxErr",
                                        "idleRangeH",
                                        "idleRangeL",
                                        "heatTargetH",
                                        "heatTargetL",
                                        "coolTargetH",
                                        "coolTargetL",
                                        "maxHeatTimeForEst",
                                        "maxCoolTimeForEst",
                                        "fridgeFastFilt",
                                        "fridgeSlowFilt",
                                        "fridgeSlopeFilt",
                                        "beerFastFilt",
                                        "beerSlowFilt",
                                        "beerSlopeFilt",
                                        "lah",
                                        "hs"};
const std::vector<std::string> vkeys = {
    "beerDiff", "diffIntegral", "beerSlope",  "p",       "i",      "d",
    "estPeak",  "negPeakEst",   "posPeakEst", "negPeak", "posPeak"};
Json map_json(const std::map<std::string, int>& m) {
    Json j(Json::Object{});
    for (auto& e : m)
        j[e.first] = e.second;
    return j;
}
std::map<std::string, int> read_map(const Json& j) {
    std::map<std::string, int> m;
    for (auto& e : j.object())
        m[e.first] = e.second.integer();
    return m;
}
} // namespace
Engine::Engine(Sink sink, Profile selected)
    : profile(selected), output(std::move(sink)), plant(selected) {
    defaults(true, true);
    for (auto& k : vkeys)
        variables[k] = 0;
    saved_settings = settings;
    saved_constants = constants;
    apply_filter_constants();
    reset_display();
}
void Engine::defaults(bool cs, bool cc) {
    if (cs)
        settings = {{"mode", 'o'},
                    {"beerSet", -32767},
                    {"fridgeSet", -32767},
                    {"heatEst", 102},
                    {"coolEst", 2560}};
    if (cc)
        constants = {{"tempFormat", 'C'},
                     {"tempSetMin", -24064},
                     {"tempSetMax", -9216},
                     {"pidMax", 5120},
                     {"Kp", 2560},
                     {"Ki", 128},
                     {"Kd", 768},
                     {"iMaxErr", 256},
                     {"idleRangeH", 512},
                     {"idleRangeL", -512},
                     {"heatTargetH", 154},
                     {"heatTargetL", -102},
                     {"coolTargetH", 102},
                     {"coolTargetL", -154},
                     {"maxHeatTimeForEst", 600},
                     {"maxCoolTimeForEst", 1200},
                     {"fridgeFastFilt", 1},
                     {"fridgeSlowFilt", 4},
                     {"fridgeSlopeFilt", 3},
                     {"beerFastFilt", 3},
                     {"beerSlowFilt", 4},
                     {"beerSlopeFilt", 4},
                     {"lah", 0},
                     {"hs", 0}};
}
void Engine::frame(char prefix, const std::string& body) {
    output(std::string(1, prefix) + ':' + body + "\r\n");
}
void Engine::diagnostic(char type, int id, Json::Array args) {
    frame('D', diagnostic_body(type, id, args));
}

bool Engine::fahrenheit() const {
    return constants.at("tempFormat") == 'F';
}
std::string Engine::number(int raw, int decimals, int category) const {
    // category: 0 unscaled, 1 absolute, 2 difference. Round in the fixed-point
    // domain first, then at the independently represented decimal boundary.
    if (category == 1 && (raw == -32768 || raw == -32767))
        return "null";
    long long n = raw;
    if (category == 1)
        n = fahrenheit() ? ratio((n + 33678) * 9, 5) : n + 24576;
    else if (category == 2 && fahrenheit())
        n = ratio(n * 9, 5);
    long long scale = decimals == 1 ? 10 : decimals == 2 ? 100 : 1000;
    long long units = ratio(std::abs(n) * scale, 512);
    std::ostringstream out;
    out << (n < 0 ? "-" : " ") << units / scale << '.' << std::setw(decimals) << std::setfill('0')
        << units % scale;
    return out.str();
}
std::optional<int> Engine::convert(const std::string& text, int category) const {
    if (category == 1 && text == "null")
        return -32767;
    auto whole = custom_prefix(text);
    if (!whole || (whole->end < text.size() && text[whole->end] != '.'))
        return {};
    if (whole->value < -4194304 || whole->value > 4194303)
        throw std::runtime_error("fidelity gap: scalar integer overflow requires characterization");
    long long fraction = 0;
    auto dot = text.find('.');
    if (dot != std::string::npos) {
        std::string tail = text.substr(dot + 1);
        auto part = custom_prefix(tail);
        if (!part || (part->end < tail.size() && tail[part->end] != '.'))
            return {};
        if (part->value < -4194304 || part->value > 4194303)
            throw std::runtime_error(
                "fidelity gap: scalar fraction overflow requires characterization");
        fraction = part->value * 512;
        // Decimal reduction is a specified sequence of integer quantizations.
        for (size_t digits = part->end; digits > 0; --digits)
            fraction = (fraction + 5) / 10;
    }
    long long raw =
        whole->value * 512 + (text.find('-') == std::string::npos ? fraction : -fraction);
    if (raw < -2147483648LL || raw > 2147483647LL)
        throw std::runtime_error(
            "fidelity gap: fixed-point long overflow requires characterization");
    if (fahrenheit() && category != 0) {
        long long shifted = raw - (category == 1 ? 16384 : 0);
        if (shifted * 50 - 45 < -2147483648LL || shifted * 50 + 45 > 2147483647LL)
            throw std::runtime_error(
                "fidelity gap: unit-conversion overflow requires characterization");
        raw = ratio(shifted * 5, 9);
    }
    if (category == 1)
        raw -= 24576;
    if (raw < -2147483648LL || raw > 2147483647LL)
        throw std::runtime_error(
            "fidelity gap: offset-conversion overflow requires characterization");
    return static_cast<int>(std::clamp(raw, -32766LL, 32767LL));
}

std::string Engine::settings_wire() const {
    Fields f;
    for (auto& k : skeys) {
        int v = settings.at(k);
        f.emplace_back(k, k == "mode" ? wire_string(std::string(1, char(v)))
                                      : number(v, k == "beerSet" || k == "fridgeSet" ? 2 : 3,
                                               k == "beerSet" || k == "fridgeSet" ? 1 : 0));
    }
    return object(f);
}
std::string Engine::constants_wire() const {
    Fields f;
    for (size_t i = 0; i < ckeys.size(); ++i) {
        auto& k = ckeys[i];
        int v = constants.at(k);
        f.emplace_back(k, i == 0    ? wire_string(std::string(1, char(v)))
                          : i >= 14 ? std::to_string(v)
                                    : number(v, i <= 2 ? 1 : 3,
                                             i <= 2             ? 1
                                             : i >= 4 && i <= 6 ? 0
                                                                : 2));
    }
    return object(f);
}
std::string Engine::variables_wire() const {
    Fields f;
    for (size_t i = 0; i < vkeys.size(); ++i) {
        auto& k = vkeys[i];
        f.emplace_back(k, number(narrow16(variables.at(k)), i >= 6 ? 1 : 3,
                                 i >= 6   ? 1
                                 : i <= 2 ? 2
                                          : 0));
    }
    return object(f);
}
void Engine::telemetry(const std::string& beer, const std::string& fridge) {
    auto temp = [this](int f) {
        auto it = targets.find(f);
        if (it == targets.end())
            return std::string("null");
        auto r = reading_raw(it->second, true);
        return r ? number(*r, 2, 1) : std::string("null");
    };
    Fields f = {{"BeerTemp", temp(9)},
                {"BeerSet", number(settings.at("beerSet"), 2, 1)},
                {"BeerAnn", beer.empty() ? "null" : wire_string(beer.substr(0, 31))},
                {"FridgeTemp", temp(5)},
                {"FridgeSet", number(settings.at("fridgeSet"), 2, 1)},
                {"FridgeAnn", fridge.empty() ? "null" : wire_string(fridge.substr(0, 31))}};
    std::string out = object(f);
    out.pop_back();
    std::string nested;
    auto room = targets.find(6);
    if (room != targets.end()) {
        auto raw = read_probe(room->second, nested);
        out += nested;
        if (raw)
            out += ",\"RoomTemp\":" + number(*raw, 2, 1);
    }
    out += ",\"State\":" + std::to_string(state) + '}';
    frame('T', out);
}
void Engine::save(bool cc) {
    if (!valid)
        return;
    saved_settings = settings;
    last_saved_target = settings.at("beerSet");
    if (cc)
        saved_constants = constants;
    if (save_callback)
        save_callback(store_image());
}
void Engine::mode(int m) {
    if (settings.at("mode") != m || state == 5 || state == 6 || state == 7) {
        settings["mode"] = m;
        if (m == 'o') {
            settings["beerSet"] = -32767;
            settings["fridgeSet"] = -32767;
        }
        state = 0;
        save(false);
    }
}
void Engine::command_evaluation() {
    evaluate_pid();
    evaluate_state();
}

void Engine::setting(const std::string& k, const std::string& v) {
    diagnostic('I', 12, {k, v});
    if (k == "mode") {
        mode(static_cast<unsigned char>(v[0]));
        telemetry("", "Mode set to " + v.substr(0, 1) + " by web");
        return;
    }
    if (k == "tempFormat") {
        constants[k] = static_cast<unsigned char>(v[0]);
        stationary_display();
        save(true);
        return;
    }
    if (k == "beerSet" || k == "fridgeSet") {
        auto n = convert(v, 1);
        if (!n)
            return;
        bool beer = k == "beerSet", profile = settings.at("mode") == 'p';
        if (beer && (!profile || std::abs(*n - settings.at(k)) > 100))
            telemetry("Beer set to " + v + (profile ? " by profile" : " by web"), "");
        if (!beer && settings.at("mode") == 'f')
            telemetry("", "Fridge set to " + v + " by web");
        if (!beer || std::abs(word16(settings.at(k) - *n)) > 256) {
            positive_pending = false;
            negative_pending = false;
        }
        settings[k] = *n;
        command_evaluation();
        if (!beer || !profile || std::abs(*n - last_saved_target) > 128)
            save(false);
        return;
    }
    bool cs = settings.count(k) > 0, cc = constants.count(k) > 0;
    if (!cs && !cc) {
        diagnostic('W', 0);
        return;
    }
    std::optional<int> n;
    if (k == "lah" || k == "hs") {
        if (v == "true" || v == "false")
            n = v == "true" ? 1 : 0;
        else {
            auto prefix = custom_prefix(v);
            if (prefix && (prefix->end == v.size() || v[prefix->end] == '.')) {
                int x = int(prefix->value & 255);
                if (x <= 1)
                    n = x;
            }
        }
    } else if (k.find("Filt") != std::string::npos)
        n = int(integer_token(v) & 255);
    else if (k == "maxHeatTimeForEst" || k == "maxCoolTimeForEst") {
        auto prefix = custom_prefix(v);
        if (prefix && (prefix->end == v.size() || v[prefix->end] == '.') && prefix->value >= 0)
            n = int(std::min(prefix->value, 65535LL));
    } else
        n = convert(v, k == "tempSetMin" || k == "tempSetMax"      ? 1
                       : k == "Kp" || k == "Ki" || k == "Kd" || cs ? 0
                                                                   : 2);
    if (n) {
        (cs ? settings : constants)[k] = *n;
        const std::map<std::string, std::pair<int, int>> routing{{"fridgeFastFilt", {5, 0}},
                                                                 {"fridgeSlowFilt", {5, 1}},
                                                                 {"fridgeSlopeFilt", {5, 2}},
                                                                 {"beerSlowFilt", {9, 0}},
                                                                 {"beerSlopeFilt", {9, 1}}};
        auto route = routing.find(k);
        if (route != routing.end()) {
            auto& h = sensors.at(route->second.first);
            (route->second.second == 0   ? h.fast
             : route->second.second == 1 ? h.slow
                                         : h.slope)
                .coefficient = unsigned(*n);
        }
        save(true);
    }
}
void Engine::pair() {
    // Token capacity counts received bytes, but callback arguments have C-string
    // visibility on the reference, including embedded NUL truncation.
    const std::string token_key = key.substr(0, key.find('\0'));
    const std::string token_value = value.substr(0, value.find('\0'));
    if (token_key.empty() || token_value.empty())
        return;
    if (command == 'j') {
        setting(token_key, token_value);
        return;
    }
    char name = token_key[0];
    if (command == 'U' && name == 'a') {
        if (token_value.size() > 16 || token_value.size() % 2)
            throw std::runtime_error("fidelity gap: odd/excessive ROM requires characterization");
        if (token_value.find_first_not_of("0123456789ABCDEFabcdef") != std::string::npos)
            throw std::runtime_error("fidelity gap: malformed ROM requires characterization");
        std::string result = address.value_or("FFFFFFFFFFFFFFFF");
        const std::string digits = "0123456789ABCDEF";
        auto component = [](char c) { return c >= 'A' ? c - 'A' + 10 : c - '0'; };
        for (size_t i = 0; i < token_value.size(); i += 2) {
            int byte_value =
                ((component(token_value[i]) * 16) | component(token_value[i + 1])) & 255;
            result[i] = digits[size_t(byte_value >> 4)];
            result[i + 1] = digits[size_t(byte_value & 15)];
        }
        address = result;
        return;
    }
    if (command == 'U' && name == 'j') {
        if (auto n = convert(token_value, 2))
            fields[name] = narrow8(int(std::floor(*n / 32.0)));
        return;
    }
    const std::string accepted = command == 'U' ? "icbfhdpx" : command == 'h' ? "hpvuf" : "irwe";
    if (accepted.find(name) != std::string::npos)
        fields[name] = narrow8(integer_token(token_value));
}

void Engine::finish() {
    phase = Phase::dispatch;
    if (command == 'j') {
        frame('S', settings_wire());
        frame('C', constants_wire());
    } else if (command == 'U')
        update_device();
    else if (command == 'd')
        query_slots();
    else if (command == 'h')
        discover();
}
void Engine::token(std::optional<unsigned char> c) {
    if (phase == Phase::brace) {
        if (c && *c == '{') {
            phase = Phase::key;
            key.clear();
            value.clear();
            return;
        }
        diagnostic('E', 10, {c ? int(*c) : -1});
        finish();
        return;
    }
    std::string& t = phase == Phase::key ? key : value;
    bool stop = t.size() == 29 || !c || *c == '}';
    bool delim = c && (*c == ':' || *c == ',');
    if (stop) {
        pair();
        finish();
        return;
    }
    if (delim) {
        if (phase == Phase::key) {
            phase = Phase::value;
            value.clear();
        } else {
            pair();
            phase = Phase::key;
            key.clear();
        }
        return;
    }
    if (*c != ' ' && *c != '"')
        t += char(*c);
}
void Engine::byte(unsigned char c) {
    if (reading()) {
        token(c);
        return;
    }
    switch (c) {
    case ' ':
    case '\r':
    case '\n':
        return;
    case 'j':
    case 'h':
    case 'd':
    case 'U':
        command = char(c);
        fields.clear();
        address.reset();
        phase = Phase::brace;
        key.clear();
        value.clear();
        return;
    case 'n':
        frame('N', object({{"v", "\"0.2.13\""},
                           {"n", wire_string(profile_revision(profile))},
                           {"s", std::to_string(profile_hardware(profile).shield)},
                           {"y", "0"},
                           {"b", "\"s\""},
                           {"l", "\"3\""}}));
        return;
    case 's':
        frame('S', settings_wire());
        return;
    case 'c':
        frame('C', constants_wire());
        return;
    case 'v':
        frame('V', variables_wire());
        return;
    case 't':
        telemetry();
        return;
    case 'l':
        frame('L', lcd());
        return;
    case 'S':
        local_cancel();
        mode('o');
        settings["beerSet"] = -32767;
        settings["fridgeSet"] = -32767;
        settings["heatEst"] = 102;
        settings["coolEst"] = 2560;
        frame('S', settings_wire());
        diagnostic('I', 14);
        return;
    case 'C':
        local_cancel();
        defaults(false, true);
        apply_filter_constants();
        stationary_display();
        frame('C', constants_wire());
        diagnostic('I', 13);
        return;
    case 'E':
        local_cancel();
        defaults(true, true);
        slots = {};
        targets.clear();
        for (auto& sensor : sensors) {
            sensor.second.connected = false;
            sensor.second.missed = 255;
        }
        valid = true;
        state = 0;
        camera = false;
        last_heat = last_cool = 0;
        positive_pending = negative_pending = false;
        apply_filter_constants();
        save(true);
        diagnostic('I', 15);
        return;
    case 'R':
        local_cancel();
        restart_requested = true;
        return;
    case 'A':
        alarm = true;
        return;
    case 'a':
        alarm = false;
        return;
    default:
        diagnostic('W', 1, {int(c)});
        return;
    }
}
void Engine::feed(const std::string& bytes) {
    if (dispatch_suspended()) {
        if (bytes.size() > 65536 - deferred_serial.size())
            throw std::runtime_error(
                "fidelity gap: serial receive overflow during controller suspension "
                "requires characterization");
        deferred_serial += bytes;
        return;
    }
    for (size_t index = 0; index < bytes.size(); ++index) {
        if (restart_requested)
            break;
        if (dispatch_suspended()) {
            feed(bytes.substr(index));
            break;
        }
        byte(static_cast<unsigned char>(bytes[index]));
    }
}
void Engine::read_timeout() {
    if (reading())
        token({});
}
bool Engine::live_target(const Device& d) const {
    return d.c <= 1 && d.b <= 1 &&
           (d.f == 1 || d.f == 2 || d.f == 3 || d.f == 4 || d.f == 5 || d.f == 6 || d.f == 7 ||
            d.f == 9);
}
std::optional<int> Engine::reading_raw(const Device& d, bool filtered_value) const {
    if (d.d || !live_target(d) || d.h != 2)
        return {};
    if (filtered_value && (d.f == 5 || d.f == 9))
        return sensors.at(d.f).connected ? std::optional<int>{filtered(d.f, 0)} : std::nullopt;
    auto index = physical_index(d);
    if (!index || plant.needs_initialization(*index))
        return {};
    auto raw = plant.read(*index);
    if (!raw)
        return {};
    return word16(*raw + d.cal * 32);
}

std::optional<int> Engine::read_probe(const Device& d, std::string& nested_diagnostic) {
    auto history = sensors.find(d.f);
    if (d.d || history == sensors.end() || !history->second.connected)
        return {};
    auto raw = reading_raw(d);
    if (!raw) {
        // Availability can change during a raw serial read, before the next
        // ordinary filter evaluation. Keep the warning inside its open reply.
        history->second.connected = false;
        nested_diagnostic += "D:" + diagnostic_body('W', 2, {d.p, d.rom}) + "\r\n";
    }
    return raw;
}

bool Engine::start_initialization(const Device& d, InitPurpose purpose, int slot) {
    auto index = physical_index(d);
    if (d.d || d.h != 2 || d.p != probe_pin(profile) || !index || !plant.read(*index) ||
        !plant.needs_initialization(*index))
        return false;
    // Connection setup clears the reset indication before requesting conversion.
    plant.set_probe_reset(*index, false);
    initialization = Initialization{purpose, controller_ms, *index, d.f, slot, d};
    return true;
}
void Engine::finish_sensor_initialization(const Device& d, bool installing) {
    auto raw = reading_raw(d);
    auto& h = sensors.at(d.f);
    bool was_connected = h.connected;
    h.connected = raw.has_value();
    if (!d.d && h.connected != was_connected)
        diagnostic(h.connected ? 'I' : 'W', h.connected ? 0 : 2, {d.p, d.rom});
    if (raw && *raw != -32768 && (installing || h.missed > 60))
        h.seed(*raw);
}
bool Engine::install(const Device& d, InitPurpose purpose, int slot) {
    if (!live_target(d))
        return true;
    targets[d.f] = d;
    if (d.h == 2) {
        auto& h = sensors.at(d.f);
        h.connected = true; // A new backend assumes connected until its first read.
        h.missed = 255;
        if (start_initialization(d, purpose, slot))
            return false;
        finish_sensor_initialization(d, true);
    }
    if (d.h == 1 && !d.d && type_of(d.f) == 3)
        pins[d.p] = bool(d.x);
    return true;
}
void Engine::finish_device_install(const Device& d, int slot) {
    slots[size_t(slot)] = d;
    if (save_callback)
        save_callback(store_image());
    frame('U', device_wire(d, slot));
}
void Engine::finish_initialization() {
    auto pending = *initialization;
    bool was_starting = startup;
    initialization.reset();
    // A second reset during conversion must not be mistaken for a completed read.
    if (pending.purpose == InitPurpose::discovery)
        discovery->failed_wait = !plant.read(pending.physical).has_value() ||
                                 plant.needs_initialization(pending.physical);
    if (pending.purpose != InitPurpose::discovery)
        finish_sensor_initialization(pending.device, pending.purpose == InitPurpose::device ||
                                                         pending.purpose == InitPurpose::boot);
    switch (pending.purpose) {
    case InitPurpose::loop:
    case InitPurpose::sensors:
        update_sensors(pending.purpose == InitPurpose::loop);
        if (!initialization && pending.purpose == InitPurpose::loop)
            finish_loop_evaluation();
        break;
    case InitPurpose::device:
        finish_device_install(pending.device, pending.slot);
        break;
    case InitPurpose::boot:
        continue_boot(pending.slot + 1);
        break;
    case InitPurpose::discovery:
        discover();
        break;
    }
    if (!dispatch_suspended()) {
        if (was_starting && !startup) {
            // Setup returns to the UI boundary before the first ordinary evaluation.
            if (service_menu())
                return;
            last_evaluation_ms = controller_ms;
            loop_evaluation();
            if (dispatch_suspended())
                return;
        }
        ++dispatch_generation;
        auto queued = std::move(deferred_serial);
        deferred_serial.clear();
        feed(queued);
    }
}
int Engine::validate(const Device& d) {
    if (d.c > 4) {
        diagnostic('E', 4, {d.c});
        return 4;
    }
    if (d.b > 6) {
        diagnostic('E', 5, {d.b});
        return 5;
    }
    if (d.f < 0 || d.f > 15) {
        diagnostic('E', 6, {d.f});
        return 6;
    }
    int owner = d.f == 0 ? 0 : d.f >= 9 ? 2 : 1;
    bool ok = owner == 0 ? d.c == 0 && d.b == 0 : owner == 1 ? d.c != 0 : d.b != 0;
    if (!ok) {
        diagnostic('E', 7, {owner, d.b, d.c});
        return 7;
    }
    int t = type_of(d.f);
    bool hardware = t == 0 ? d.h == 0 : t == 1 ? d.h == 2 : t == 2 || t == 3 ? d.h == 1 : false;
    if (!hardware) {
        diagnostic('E', 8, {t, d.h});
        return 8;
    }
    if (d.h == 2 && d.p != probe_pin(profile)) {
        diagnostic('E', 9, {d.p});
        return 9;
    }
    return 0;
}
std::string Engine::device_wire(const Device& d, int i, std::optional<std::string> val) const {
    Fields f = {{"i", std::to_string(i)},   {"t", std::to_string(type_of(d.f))},
                {"c", std::to_string(d.c)}, {"b", std::to_string(d.b)},
                {"f", std::to_string(d.f)}, {"h", std::to_string(d.h)},
                {"d", std::to_string(d.d)}, {"p", std::to_string(narrow8(d.p))}};
    if (val)
        f.emplace_back("v", *val);
    if (d.h == 1)
        f.emplace_back("x", std::to_string(d.x));
    if (d.h == 2) {
        f.emplace_back("a", wire_string(d.rom));
        f.emplace_back("j", number(d.cal * 32, 3, 2));
    }
    return object(f);
}
void Engine::update_device() {
    int index = -1;
    const auto& patch = fields;
    const auto& rom = address;
    if (patch.count('i'))
        index = patch.at('i');
    if (index < 0 || index > 16)
        return;
    if (index == 16 || !valid)
        throw std::runtime_error(
            "fidelity gap: uninitialized device record requires characterization");
    Device old = slots[size_t(index)], d = old;
    auto assign = [&](char k, int& field) {
        if (patch.count(k) && (k == 'j' ? patch.at(k) != -1 : patch.at(k) >= 0))
            field = patch.at(k);
    };
    assign('c', d.c);
    assign('b', d.b);
    assign('f', d.f);
    assign('h', d.h);
    assign('d', d.d);
    assign('p', d.p);
    assign('x', d.x);
    assign('j', d.cal);
    if (rom && rom->substr(0, 2) != "FF")
        d.rom = *rom;
    d.c = 1;
    d.b = patch.count('f') && patch.at('f') >= 9 && patch.at('f') <= 15 ? 1 : 0;
    if (d.f == 0)
        d = Device{};
    if (validate(d)) {
        diagnostic('E', 3);
        frame('U', device_wire(old, index));
        return;
    }
    if ((d.d != 0 && d.d != 1) || (d.x != 0 && d.x != 1))
        throw std::runtime_error(
            "fidelity gap: noncanonical bool representation requires characterization");
    if (live_target(old)) {
        targets.erase(old.f);
        if (old.h == 2) {
            sensors.at(old.f).connected = false;
            sensors.at(old.f).missed = 255;
        }
    }
    if (install(d, InitPurpose::device, index))
        finish_device_install(d, index);
}
void Engine::query_slots() {
    std::map<char, int> q = {{'i', -1}, {'r', -1}, {'w', -1}, {'e', 0}};
    for (auto& e : fields)
        if (q.count(e.first))
            q[e.first] = e.second;
    if (q['i'] == -2) {
        if (q['w'] >= 0) {
            camera = q['w'] != 0;
            if (camera)
                camera_last = seconds();
        }
        frame('d', "[]");
        return;
    }
    std::string out = "[";
    if (valid)
        for (int i = 0; i < 16; ++i) {
            const Device& d = slots[size_t(i)];
            if (q['i'] != -1 && q['i'] != i)
                continue;
            if (q['i'] == -1 && !q['e'] && d.f == 0)
                continue;
            const bool separator = out.size() > 1;
            std::string nested;
            std::optional<std::string> v;
            auto live = targets.find(d.f);
            if (live == targets.end() && live_target(d) && type_of(d.f) == 3) {
                if (q['w'] >= 0)
                    fallback = q['w'] != 0;
                else if (q['r'] == 1)
                    v = std::to_string(int(fallback));
            } else if (live != targets.end() && live_target(d)) {
                auto& target = live->second;
                if (q['w'] >= 0 && type_of(d.f) == 3) {
                    if (target.d)
                        fallback = q['w'] != 0;
                    else
                        pins[target.p] = (q['w'] != 0) != bool(target.x);
                } else if (q['r'] == 1) {
                    if (type_of(d.f) == 1) {
                        auto r = read_probe(target, nested);
                        v = r ? number(*r, 3, 1) : "null";
                    } else if (type_of(d.f) == 3)
                        v = std::to_string(target.d ? int(fallback)
                                                    : int(pins[target.p] != bool(target.x)));
                    else if (type_of(d.f) == 2)
                        v = std::to_string(int(sense_switch(target)));
                }
            }
            out += nested;
            if (separator)
                out += ',';
            out += device_wire(d, i, v);
        }
    frame('d', out + ']');
}
void Engine::discover() {
    std::map<char, int> q = {{'h', -1}, {'p', -1}, {'v', 0}, {'u', 0}, {'f', 0}};
    for (auto& e : fields)
        if (q.count(e.first))
            q[e.first] = e.second;
    if (!discovery) {
        discovery = Discovery{};
        discovery->carry.c = 1;
        output("h:[");
    }
    auto& carry = discovery->carry;
    std::vector<Device> inventory;
    for (auto rom : {"28A1010000000204", "28A10100000001E6", "28A101000000035A"}) {
        Device d;
        d.h = 2;
        d.p = probe_pin(profile);
        d.c = 1;
        d.rom = rom;
        inventory.push_back(d);
    }
    for (int p : output_pins(profile)) {
        Device d;
        d.h = 1;
        d.p = p;
        d.c = 1;
        d.x = 1;
        inventory.push_back(d);
    }
    while (discovery->cursor < inventory.size()) {
        auto& hardware = inventory[discovery->cursor];
        auto skip = [&]() {
            ++discovery->cursor;
            discovery->failed_wait = false;
        };
        if (hardware.h != discovery->previous_hardware) {
            carry = Device{};
            carry.c = 1;
            discovery->previous_hardware = hardware.h;
        }
        if ((hardware.h == 2 && !plant.read(*physical_index(hardware)) &&
             !discovery->failed_wait) ||
            (q['h'] != -1 && q['h'] != hardware.h) || (q['p'] != -1 && q['p'] != hardware.p) ||
            (q['f'] && type_of(q['f']) != (hardware.h == 2 ? 1 : 3))) {
            skip();
            continue;
        }
        // The enumeration cursor deliberately retains assigned fields between rows (F09).
        carry.h = hardware.h;
        carry.p = hardware.p;
        if (hardware.h == 2)
            carry.rom = hardware.rom;
        else
            carry.x = hardware.x;
        int index = -1;
        if (valid)
            for (int i = 0; i < 16; ++i) {
                auto& d = slots[size_t(i)];
                bool match = d.f && d.h == hardware.h && d.p == hardware.p &&
                             (d.h == 1 || d.rom == hardware.rom || d.rom.substr(0, 2) == "00");
                if (match) {
                    index = i;
                    if (!q['u'])
                        carry = d;
                    break;
                }
            }
        if (index >= 0 && q['u']) {
            skip();
            continue;
        }
        std::string out;
        const bool separator = discovery->has_row;
        std::optional<std::string> val;
        if (q['v'] && hardware.h == 2) {
            if (carry.rom != hardware.rom && carry.rom == "0000000000000000") {
                // The observed temporary zero-ROM reader logs before the row's
                // comma, while the discovery list is still open.
                out += "D:" + diagnostic_body('W', 2, {carry.p, carry.rom}) + "\r\n";
                val = "null";
            } else if (carry.rom != hardware.rom)
                throw std::runtime_error(
                    "fidelity gap: nested discovery diagnostics require characterization");
            else {
                if (!discovery->failed_wait && start_initialization(carry, InitPurpose::discovery))
                    return;
                auto raw = plant.read(*physical_index(hardware));
                if (!raw || discovery->failed_wait) {
                    out += "D:" + diagnostic_body('W', 2, {carry.p, carry.rom}) + "\r\n";
                    val = "null";
                } else
                    val = number(*raw, 3, 1);
            }
        }
        if (separator)
            out += ',';
        out += device_wire(carry, index, val);
        output(out);
        discovery->has_row = true;
        skip();
    }
    discovery.reset();
    output("]\r\n");
}
std::string Engine::lcd() const {
    std::string rows = "[";
    for (auto& row : local_rows()) {
        if (rows.size() > 1)
            rows += ',';
        rows += wire_string(row);
    }
    return rows + ']';
}

void Engine::boot(bool initialize_display) {
    if (initialize_display) {
        startup = startup_display = display_reset_busy = true;
        display_reset_started_ms = controller_ms;
        return;
    }
    targets.clear();
    if (!valid) {
        diagnostic('W', 3);
        startup = false;
        return;
    }
    settings = saved_settings;
    constants = saved_constants;
    apply_filter_constants();
    last_saved_target = settings.at("beerSet");
    if (settings.at("mode") == 'o') {
        settings["beerSet"] = -32767;
        settings["fridgeSet"] = -32767;
    }
    save(false);
    continue_boot(0);
}
void Engine::continue_boot(int first) {
    for (int index = first; index < 16; ++index) {
        auto& d = slots[size_t(index)];
        if (validate(d)) {
            d = Device{};
            // Firmware clears each invalid EEPROM record before loading the next.
            if (save_callback)
                save_callback(store_image());
        } else if (!install(d, InitPurpose::boot, index))
            return;
    }
    render_display();
    startup = false;
}
void Engine::restart(bool initialize_display) {
    local_cancel();
    encoder_value = encoder_seen = encoder_low = encoder_high = 0;
    encoder_pressed = false;
    phase = Phase::dispatch;
    restart_requested = false;
    alarm = false;
    camera = false;
    fallback = false;
    state = 0;
    controller_ms = 0;
    last_evaluation_ms = uint32_t(-1000);
    last_lcd_reset = 0;
    display_reset_busy = startup = startup_display = false;
    initialization.reset();
    discovery.reset();
    sensor_cursor = 0;
    display_reset_started_ms = 0;
    deferred_serial.clear();
    last_idle = last_heat = last_cool = wait_seconds = camera_last = 0;
    integral_counter = 0;
    integral_branches = 0;
    positive_pending = negative_pending = door_open = false;
    sensors = {{5, {}}, {6, {}}, {9, {}}};
    pins.clear();
    variables.clear();
    for (auto& k : vkeys)
        variables[k] = 0;
    defaults(true, true);
    apply_filter_constants();
    reset_display();
    boot(initialize_display);
}
Json Engine::encode_device(const Device& d) {
    return Json::Object{{"c", d.c}, {"b", d.b}, {"f", d.f},     {"h", d.h},    {"d", d.d},
                        {"p", d.p}, {"x", d.x}, {"cal", d.cal}, {"rom", d.rom}};
}
Device Engine::decode_device(const Json& j) {
    Device d;
    auto get = [&](const std::string& k, int& v) {
        if (j.has(k))
            v = j.at(k).integer();
    };
    get("c", d.c);
    get("b", d.b);
    get("f", d.f);
    get("h", d.h);
    get("d", d.d);
    get("p", d.p);
    get("x", d.x);
    get("cal", d.cal);
    if (j.has("rom"))
        d.rom = j.at("rom").string();
    if (j.has("a"))
        d.rom = j.at("a").string();
    if (j.has("j"))
        d.cal = narrow8(std::llround(j.at("j").number() * 16));
    return d;
}
Json Engine::store_image() const {
    Json::Array ds;
    for (auto& d : slots)
        ds.push_back(encode_device(d));
    return Json::Object{{"format", profile == Profile::i2c ? "brewpi-emulator-store-v2"
                                                           : "brewpi-emulator-store-v1"},
                        {"profile", profile_name(profile)},
                        {"controller_version", valid ? 4 : 255},
                        {"settings_raw", map_json(saved_settings)},
                        {"constants_raw", map_json(saved_constants)},
                        {"devices", ds}};
}
void Engine::load_store(const Json& image) {
    const auto format = image.at("format").string();
    if (format != "brewpi-emulator-store-v1" && format != "brewpi-emulator-store-v2")
        throw std::runtime_error("unrecognized emulator store format");
    // Older stores belong to the original RevC personality. Never reinterpret
    // pin assignments by silently changing the controller's hardware profile.
    Profile stored_profile =
        image.has("profile") ? parse_profile(image.at("profile").string()) : Profile::revc;
    // V2 protects I2C stores from older RevC-only executables, which reject the
    // format before they can clear or rewrite unfamiliar pin assignments.
    if ((format == "brewpi-emulator-store-v2") != (stored_profile == Profile::i2c))
        throw std::runtime_error("controller store format/profile mismatch");
    if (stored_profile != profile)
        throw std::runtime_error("controller store profile mismatch");
    int version = image.at("controller_version").integer();
    valid = version == 4;
    if (!valid)
        return;
    auto s = read_map(image.at("settings_raw")), c = read_map(image.at("constants_raw"));
    if (s.size() != skeys.size() || c.size() != ckeys.size())
        throw std::runtime_error("invalid store field count");
    for (auto& k : skeys)
        if (!s.count(k))
            throw std::runtime_error("missing store setting");
    for (auto& k : ckeys)
        if (!c.count(k))
            throw std::runtime_error("missing store constant");
    if (image.at("devices").array().size() != 16)
        throw std::runtime_error("invalid store slot count");
    for (auto& e : s)
        if (e.second < -32768 || e.second > 32767)
            throw std::runtime_error("invalid stored setting width");
    for (auto& e : c)
        if (e.second < -32768 || e.second > 65535)
            throw std::runtime_error("invalid stored constant width");
    if (s.at("mode") < 0 || s.at("mode") > 255 || c.at("tempFormat") < 0 ||
        c.at("tempFormat") > 255)
        throw std::runtime_error("invalid stored character width");
    for (auto& key : ckeys) {
        if (key.find("Filt") != std::string::npos && (c.at(key) < 0 || c.at(key) > 255))
            throw std::runtime_error("invalid stored filter width");
        if ((key == "lah" || key == "hs") && c.at(key) != 0 && c.at(key) != 1)
            throw std::runtime_error("invalid stored flag representation");
        if (key != "tempFormat" && key.find("Filt") == std::string::npos && key != "lah" &&
            key != "hs" && key.find("TimeForEst") == std::string::npos &&
            (c.at(key) < -32768 || c.at(key) > 32767))
            throw std::runtime_error("invalid stored fixed-point width");
        if (key.find("TimeForEst") != std::string::npos && c.at(key) < 0)
            throw std::runtime_error("invalid stored time width");
    }
    saved_settings = std::move(s);
    saved_constants = std::move(c);
    for (size_t i = 0; i < 16; ++i) {
        const auto& record = image.at("devices").array()[i];
        const std::vector<std::string> required = {"c", "b", "f", "h", "d", "p", "x", "cal", "rom"};
        if (record.object().size() != required.size())
            throw std::runtime_error("invalid stored device field count");
        for (const auto& name : required)
            if (!record.has(name))
                throw std::runtime_error("missing stored device field: " + name);
        slots[i] = decode_device(record);
        auto& d = slots[i];
        if (d.rom.size() != 16 || d.rom.find_first_not_of("0123456789ABCDEF") != std::string::npos)
            throw std::runtime_error("invalid stored ROM");
        for (int v : {d.c, d.b, d.f, d.h, d.d, d.p, d.x})
            if (v < 0 || v > 255)
                throw std::runtime_error("invalid stored device width");
        if ((d.d != 0 && d.d != 1) || (d.x != 0 && d.x != 1))
            throw std::runtime_error("invalid stored boolean representation");
        if (d.cal < -128 || d.cal > 127)
            throw std::runtime_error("invalid stored calibration width");
    }
}
void Engine::construct(const Json& spec) {
    menu = {};
    encoder_value = encoder_seen = encoder_low = encoder_high = 0;
    encoder_pressed = false;
    defaults(true, true);
    slots = {};
    targets.clear();
    pins.clear();
    state = 0;
    controller_ms = 0;
    last_evaluation_ms = uint32_t(-1000);
    last_lcd_reset = 0;
    display_reset_busy = startup = startup_display = false;
    initialization.reset();
    discovery.reset();
    sensor_cursor = 0;
    display_reset_started_ms = 0;
    deferred_serial.clear();
    pending_ms = 0;
    last_idle = last_heat = last_cool = wait_seconds = camera_last = 0;
    integral_counter = 0;
    integral_branches = 0;
    positive_pending = negative_pending = door_open = false;
    plant = Plant{profile};
    if (spec.has("scenario"))
        plant.configure(spec.at("scenario"));
    sensors = {{5, {}}, {6, {}}, {9, {}}};
    valid = spec.at("valid").boolean();
    for (auto& k : vkeys)
        variables[k] = 0;
    if (spec.has("settings_raw"))
        settings = read_map(spec.at("settings_raw"));
    if (spec.has("constants_raw"))
        constants = read_map(spec.at("constants_raw"));
    if (spec.has("variables_raw"))
        variables = read_map(spec.at("variables_raw"));
    phase = Phase::dispatch;
    restart_requested = false;
    alarm = false;
    camera = false;
    fallback = false;
    fields.clear();
    address.reset();
    key.clear();
    value.clear();
    apply_filter_constants();
    reset_display();
    if (spec.has("slots"))
        for (auto& j : spec.at("slots").array())
            slots.at(size_t(j.at("i").integer())) = decode_device(j);
    saved_settings = settings;
    saved_constants = constants;
    last_saved_target = settings.at("beerSet");
    for (int slot = 0; slot < 16; ++slot)
        if (slots[size_t(slot)].f && !install(slots[size_t(slot)], InitPurpose::boot, slot))
            break;
    render_display();
}
void Engine::precondition(const Json& fields) {
    for (auto& e : fields.object()) {
        auto& k = e.first;
        auto& v = e.second;
        if (k == "variables_raw")
            for (auto& item : v.object())
                variables.at(item.first) = item.second.integer();
        else if (k == "persisted_device_records") {
            slots = {};
            for (auto& j : v.array())
                slots.at(size_t(j.at("i").integer())) = decode_device(j);
        } else if (k == "mode")
            settings["mode"] = v.string().at(0);
        else if (k == "state")
            state = v.integer();
        else if (k == "beer_target_c" || k == "fridge_target_c")
            settings[k == "beer_target_c" ? "beerSet" : "fridgeSet"] = absolute_raw(v.number());
        else if (k == "slow_beer_c")
            sensors.at(9).slow.seed(absolute_raw(v.number()));
        else if (k == "fast_fridge_temperature_c")
            sensors.at(5).fast.seed(absolute_raw(v.number()));
        else if (k == "beer_slope_c_per_hour")
            sensors.at(9).slope.seed(temperature_limit(std::llround(v.number() * 512)));
        else if (k == "diff_integral_raw")
            variables["diffIntegral"] = v.integer();
        else if (k == "cool_estimator_raw")
            settings["coolEst"] = v.integer();
        else if (k == "integral_evaluation_count") {
            int n = v.integer();
            if (n < 0 || n > 60)
                throw std::runtime_error("invalid PID fixture count");
            integral_counter = unsigned(n);
        } else if (k == "camera_request_active")
            camera = v.boolean();
        else if (k == "camera_last_active_seconds")
            camera_last = uint16_t(v.integer());
        else if (k == "controller_millis") {
            double n = v.number();
            if (n < 0 || n > 4294967295.0 || n != std::floor(n))
                throw std::runtime_error("invalid fixture clock");
            controller_ms = uint32_t(n);
        } else if (k == "controller_seconds") {
            if (!fields.has("controller_millis"))
                controller_ms = uint32_t(v.integer()) * 1000;
        } else if (k == "seconds_since_idle") {
        } // Coherent timestamp construction occurs after clock patches.
        else if (k == "required_probe_connected") {
            for (size_t i = 0; i < 3; ++i)
                plant.set_connected(i, v.boolean());
        } else if (k == "door_open")
            plant.set_door(v.boolean());
        else if (k == "positive_peak_pending")
            positive_pending = v.boolean();
        else if (k == "negative_peak_pending")
            negative_pending = v.boolean();
        else if (k == "last_heat_seconds")
            last_heat = uint16_t(v.integer());
        else if (k == "last_cool_seconds")
            last_cool = uint16_t(v.integer());
        else if (k == "physical_temperatures_c") {
            auto& a = v.array();
            if (a.size() != 3)
                throw std::runtime_error("invalid physical fixture temperatures");
            for (size_t i = 0; i < 3; ++i)
                plant.set_temperature(i, a[i].number());
        } else if (k == "probe_reset") {
            if (v.array().size() != 3)
                throw std::runtime_error("invalid fixture probe reset states");
            for (size_t i = 0; i < 3; ++i)
                plant.set_probe_reset(i, v.array()[i].boolean());
        } else if (k == "connected") {
            auto& a = v.array();
            if (a.size() != 3)
                throw std::runtime_error("invalid physical fixture connectivity");
            for (size_t i = 0; i < 3; ++i)
                plant.set_connected(i, a[i].boolean());
        } else
            throw std::runtime_error("unknown fixture precondition: " + k);
    }
    if (fields.has("controller_seconds") && seconds() != fields.at("controller_seconds").integer())
        throw std::runtime_error("incoherent fixture clocks");
    if (fields.has("seconds_since_idle"))
        last_idle = uint16_t(seconds() - fields.at("seconds_since_idle").integer());
}

Json Engine::observations() const {
    Json::Array electrical;
    for (auto& pin : pins)
        electrical.emplace_back(Json::Array{pin.first, pin.second});
    int fridge = settings.at("fridgeSet");
    return Json::Object{
        {"variables_raw", map_json(variables)},
        {"store", store_image()},
        {"state", state},
        {"controller_millis", double(controller_ms)},
        {"controller_seconds", int(seconds())},
        {"pending_ms", double(pending_ms)},
        {"camera_request_active", camera},
        {"camera_last_active_seconds", int(camera_last)},
        {"integral_branch_executions", double(integral_branches)},
        {"integral_evaluation_count", int(integral_counter)},
        {"last_d_unscaled", variables.at("d") / 512.0},
        {"last_fridge_target_c", fridge <= -32767 ? Json{} : Json(fridge / 512.0 + 48)},
        {"effective_beer_filter_coefficients",
         Json::Object{{"fast", int(sensors.at(9).fast.coefficient)},
                      {"slow", int(sensors.at(9).slow.coefficient)},
                      {"slope", int(sensors.at(9).slope.coefficient)}}},
        {"plant", plant.observations()},
        {"pins", electrical},
        {"wait_seconds", int(wait_seconds)},
        {"last_idle_seconds", int(last_idle)},
        {"last_heat_seconds", int(last_heat)},
        {"last_cool_seconds", int(last_cool)},
        {"positive_peak_pending", positive_pending},
        {"negative_peak_pending", negative_pending},
        {"door_open", door_open}};
}
} // namespace rmx
