// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "dynamics.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace rmx {
int word16(int64_t n) {
    int v = int(uint64_t(n) & 65535);
    return v >= 32768 ? v - 65536 : v;
}
int32_t word32(int64_t n) {
    if (n < std::numeric_limits<int32_t>::min() || n > std::numeric_limits<int32_t>::max())
        throw std::runtime_error(
            "fidelity gap: controller/filter long overflow requires characterization");
    return static_cast<int32_t>(n);
}
int64_t signed_shift(int64_t n, unsigned bits) {
    if (bits >= 32)
        throw std::runtime_error("fidelity gap: reference shift width requires characterization");
    int64_t divisor = int64_t(1) << bits;
    return n >= 0 ? n / divisor : -((-n + divisor - 1) / divisor);
}
int temperature_limit(int64_t n) {
    return int(std::clamp(n, int64_t(-32766), int64_t(32767)));
}
int absolute_raw(double c) {
    if (!std::isfinite(c))
        throw std::runtime_error("nonfinite scenario temperature");
    return temperature_limit(std::llround(std::clamp((c - 48) * 512, -32766.0, 32767.0)));
}
void Signal::seed(int raw) {
    int32_t p = word32(int64_t(raw) * 65536);
    for (auto& row : delays)
        row.fill(p);
    recent.fill(p);
}
int Signal::value() const {
    return word16(signed_shift(recent[0], 16));
}
void Signal::push(int32_t input) {
    unsigned a = (2 * coefficient + 4) & 255;
    if (coefficient >= 32 || a < 2 || a >= 32)
        throw std::runtime_error(
            "fidelity gap: filter coefficient shift requires characterization");
    int32_t v = input;
    for (auto& row : delays) {
        const auto old = row;
        int32_t next = word32(int64_t(old[2]) + (int64_t(old[2]) - old[3]));
        const std::array<int64_t, 6> terms{{-signed_shift(old[2], coefficient),
                                            signed_shift(old[3], coefficient), signed_shift(v, a),
                                            signed_shift(old[0], a - 1), signed_shift(old[1], a),
                                            -signed_shift(old[3], a - 2)}};
        for (auto term : terms)
            next = word32(int64_t(next) + term);
        row = {{v, old[0], next, old[2]}};
        v = next;
    }
    recent = {{v, recent[0], recent[1]}};
}
std::optional<int> Signal::turn(bool positive) const {
    bool found = positive ? (recent[0] < recent[1] && recent[1] >= recent[2])
                          : (recent[0] > recent[1] && recent[1] <= recent[2]);
    return found ? std::optional<int>{word16(signed_shift(recent[1], 16))} : std::nullopt;
}
Json Signal::snapshot() const {
    Json::Array rows, h;
    for (auto& row : delays) {
        Json::Array r;
        for (auto v : row)
            r.emplace_back(double(v));
        rows.emplace_back(r);
    }
    for (auto v : recent)
        h.emplace_back(double(v));
    return Json::Object{{"b", int(coefficient)}, {"delays", rows}, {"recent", h}};
}
void Signal::restore(const Json& j) {
    int b = j.at("b").integer();
    if (b < 0 || b > 255 || j.at("delays").array().size() != 3 ||
        j.at("recent").array().size() != 3)
        throw std::runtime_error("invalid checkpoint filter");
    coefficient = unsigned(b);
    for (size_t i = 0; i < 3; ++i) {
        auto& r = j.at("delays").array()[i].array();
        if (r.size() != 4)
            throw std::runtime_error("invalid checkpoint filter delays");
        for (size_t k = 0; k < 4; ++k)
            delays[i][k] = r[k].integer();
        recent[i] = j.at("recent").array()[i].integer();
    }
}
void SensorHistory::seed(int raw) {
    fast.seed(raw);
    slow.seed(raw);
    slope.seed(0);
    slope_origin = slow.precise();
    missed = 0;
}
void SensorHistory::sample(int raw) {
    fast.push(word32(int64_t(raw) * 65536));
    slow.push(word32(int64_t(raw) * 65536));
    countdown = (countdown - 1) & 255;
    if (countdown == 4)
        slope_origin = slow.precise();
    if (countdown == 0) {
        int64_t diff = int64_t(slow.precise()) - slope_origin;
        auto upper = signed_shift(diff, 16);
        if (upper > 27)
            diff = 27 * 65536;
        else if (upper < -27)
            diff = -27 * 65536;
        slope.push(word32(diff * 1200));
        slope_origin = slow.precise();
        countdown = 3;
    }
}
Json SensorHistory::snapshot() const {
    return Json::Object{{"fast", fast.snapshot()},   {"slow", slow.snapshot()},
                        {"slope", slope.snapshot()}, {"countdown", int(countdown)},
                        {"missed", int(missed)},     {"origin", double(slope_origin)},
                        {"connected", connected}};
}
void SensorHistory::restore(const Json& j) {
    fast.restore(j.at("fast"));
    slow.restore(j.at("slow"));
    slope.restore(j.at("slope"));
    int c = j.at("countdown").integer(), m = j.at("missed").integer();
    if (c < 0 || c > 255 || m < 0 || m > 255)
        throw std::runtime_error("invalid checkpoint sensor counters");
    countdown = unsigned(c);
    missed = unsigned(m);
    slope_origin = j.at("origin").integer();
    connected = j.at("connected").boolean();
}

Plant::Plant() {
    configure(Json::Object{});
}
void Plant::configure(const Json& config) {
    const std::vector<std::string> known = {"instance_id",
                                            "initial_temperatures_c",
                                            "beer_liters",
                                            "beer_density_kg_per_m3",
                                            "beer_specific_heat_j_per_kg_k",
                                            "carboy_capacity_j_per_k",
                                            "chamber_liters",
                                            "cabinet_capacity_j_per_k",
                                            "air_capacity_j_per_m3_k",
                                            "beer_chamber_conductance_w_per_k",
                                            "chamber_room_conductance_w_per_k",
                                            "physical_loads",
                                            "door_pin",
                                            "door_open",
                                            "probe_quantization_c",
                                            "probe_lag_seconds",
                                            "noise_amplitude_c",
                                            "random_seed",
                                            "fermentation_enabled",
                                            "active_fermentation_profile",
                                            "speed_factor",
                                            "room_daily_amplitude_c",
                                            "room_daily_phase_hours",
                                            "door_extra_conductance_w_per_k",
                                            "fermentation_age_hours"};
    for (auto& field : config.object())
        if (std::find(known.begin(), known.end(), field.first) == known.end())
            throw std::runtime_error("unknown scenario field: " + field.first);
    if (config.has("instance_id") && config.at("instance_id").string() != "chamber1")
        throw std::runtime_error("alternate instance hardware identities are not configured");
    if (config.has("speed_factor") &&
        (config.at("speed_factor").number() < 0 || config.at("speed_factor").number() > 1000))
        throw std::runtime_error("invalid scenario speed factor");
    door_pin = config.has("door_pin") ? config.at("door_pin").integer() : 4;
    if (door_pin < 0 || door_pin > 255)
        throw std::runtime_error("invalid external door pin");
    scenario = config;
    auto num = [&](const char* k, double d) { return config.has(k) ? config.at(k).number() : d; };
    auto yes = [&](const char* k, bool d) { return config.has(k) ? config.at(k).boolean() : d; };
    // Validate physical components before combining them: a positive total must
    // not hide a negative volume, density, or heat capacity.
    for (auto name : {"beer_liters", "beer_density_kg_per_m3", "beer_specific_heat_j_per_kg_k",
                      "carboy_capacity_j_per_k", "chamber_liters", "cabinet_capacity_j_per_k",
                      "air_capacity_j_per_m3_k"})
        if (config.has(name) &&
            (!std::isfinite(config.at(name).number()) || config.at(name).number() < 0))
            throw std::runtime_error("invalid external scenario component: " + std::string(name));
    beer_capacity = num("beer_liters", 18.927) / 1000 * num("beer_density_kg_per_m3", 1000) *
                        num("beer_specific_heat_j_per_kg_k", 4180) +
                    num("carboy_capacity_j_per_k", 6000);
    chamber_capacity = num("chamber_liters", 400) / 1000 * num("air_capacity_j_per_m3_k", 1210) +
                       num("cabinet_capacity_j_per_k", 2000);
    bc = num("beer_chamber_conductance_w_per_k", 3);
    cr = num("chamber_room_conductance_w_per_k", 1.67);
    quantum = num("probe_quantization_c", .0625);
    lag = num("probe_lag_seconds", 0);
    noise = num("noise_amplitude_c", 0);
    room_amplitude = num("room_daily_amplitude_c", 0);
    room_phase = num("room_daily_phase_hours", 0);
    door_conductance = num("door_extra_conductance_w_per_k", 0);
    door = yes("door_open", false);
    ferment = yes("fermentation_enabled", false);
    int seed = config.has("random_seed") ? config.at("random_seed").integer() : 1;
    random = uint32_t(seed);
    if (beer_capacity <= 0 || chamber_capacity <= 0 || bc < 0 || cr < 0 || quantum <= 0 ||
        lag < 0 || noise < 0 || room_amplitude < 0 || door_conductance < 0)
        throw std::runtime_error("invalid external scenario parameter");
    temperature = {{20, 20, 20}};
    if (config.has("initial_temperatures_c"))
        for (size_t i = 0; i < 3; ++i)
            temperature[i] = config.at("initial_temperatures_c")
                                 .at(std::array<const char*, 3>{{"beer", "chamber", "room"}}[i])
                                 .number();
    for (double t : temperature)
        if (!std::isfinite(t) || t < -15 || t > 110)
            throw std::runtime_error("initial scenario temperature outside virtual probe range");
    fermentation_age_hours = num("fermentation_age_hours", 0);
    fermentation_points = {{{0, 0}}, {{8, 0}}, {{20, 5}}, {{44, 5}}, {{92, 0}}};
    if (config.has("active_fermentation_profile")) {
        const auto& profile = config.at("active_fermentation_profile");
        double maximum = profile.at("maximum_watts").number();
        if (maximum < 0)
            throw std::runtime_error("invalid fermentation maximum");
        fermentation_points.clear();
        for (auto& row : profile.at("breakpoints_hours_watts").array()) {
            const auto& a = row.array();
            if (a.size() != 2)
                throw std::runtime_error("invalid fermentation point");
            std::array<double, 2> point{{a[0].number(), a[1].number()}};
            if (point[0] < 0 || point[1] < 0 || point[1] > maximum ||
                (!fermentation_points.empty() && point[0] <= fermentation_points.back()[0]))
                throw std::runtime_error("invalid fermentation curve");
            fermentation_points.push_back(point);
        }
        if (fermentation_points.size() < 2 || fermentation_points.back()[1] != 0)
            throw std::runtime_error("fermentation curve must end at zero");
    }
    if (fermentation_age_hours < 0)
        throw std::runtime_error("invalid fermentation age");
    for (auto n : {beer_capacity, chamber_capacity, bc, cr, quantum, lag, noise, room_amplitude,
                   room_phase, door_conductance, fermentation_age_hours})
        if (!std::isfinite(n))
            throw std::runtime_error("nonfinite derived scenario parameter");
    if (.1 * (bc / beer_capacity + (bc + cr + door_conductance) / chamber_capacity) > 1)
        throw std::runtime_error(
            "external thermal parameters are too stiff for the fixed integration step");
    room_base = temperature[2];
    temperature[2] =
        room_base + room_amplitude * std::sin(2 * 3.14159265358979323846 * room_phase / 24);
    lagged = temperature;
    elapsed_ms = 0;
    energy_from_loads = energy_from_fermentation = energy_from_room = 0;
    available.fill(true);
    loads = {{5, 25, true}, {6, -60, true}, {2, 0, true}, {19, 0, true}};
    if (config.has("physical_loads")) {
        loads.clear();
        std::map<int, bool> used;
        for (auto& entry : config.at("physical_loads").array()) {
            int pin = entry.at("pin").integer();
            double watts = entry.at("watts").number();
            std::string kind = entry.at("kind").string();
            if (pin < 0 || pin > 255 || watts < 0 || used.count(pin) ||
                (kind != "heater" && kind != "cooler" && kind != "light" && kind != "fan"))
                throw std::runtime_error("invalid external load");
            used[pin] = true;
            loads.push_back(
                {pin, kind == "cooler" ? -watts : watts, entry.at("active_low").boolean()});
        }
    }
    sample_probes();
}
double Plant::fermentation(double seconds) const {
    if (!ferment)
        return 0;
    double h = seconds / 3600 + fermentation_age_hours;
    if (fermentation_points.empty() || h < fermentation_points.front()[0])
        return 0;
    for (size_t i = 1; i < fermentation_points.size(); ++i) {
        const auto& left = fermentation_points[i - 1];
        const auto& right = fermentation_points[i];
        if (h <= right[0])
            return left[1] + (right[1] - left[1]) * (h - left[0]) / (right[0] - left[0]);
    }
    return 0;
}

void Plant::sample_probes() {
    for (size_t i = 0; i < 3; ++i) {
        double n = 0;
        if (noise > 0) {
            random = random * 1664525u + 1013904223u;
            n = (double(random) / 4294967295.0 * 2 - 1) * noise;
        }
        double c = std::round((lagged[i] + n) / quantum) * quantum;
        probe[i] = absolute_raw(c);
    }
}
void Plant::step(const std::map<int, bool>& pins) {
    constexpr double dt = .1, pi = 3.14159265358979323846;
    double t = double(elapsed_ms) / 1000;
    auto room = [&](double s) {
        return room_base + room_amplitude * std::sin(2 * pi * (s / 86400 + room_phase / 24));
    };
    double watts = 0;
    for (auto& load : loads) {
        auto it = pins.find(load.pin);
        if (it != pins.end() && (it->second != load.low))
            watts += load.watts;
    }
    double conductance = cr + (door ? door_conductance : 0);
    double ferm = fermentation(t + dt / 2);
    double exchange = bc * (temperature[1] - temperature[0]);
    double bmid = temperature[0] + dt / 2 * (exchange + ferm) / beer_capacity;
    double cmid =
        temperature[1] +
        dt / 2 * (-exchange + conductance * (room(t) - temperature[1]) + watts) / chamber_capacity;
    double mid_exchange = bc * (cmid - bmid), ambient = conductance * (room(t + dt / 2) - cmid);
    temperature[0] += dt * (mid_exchange + ferm) / beer_capacity;
    temperature[1] += dt * (-mid_exchange + ambient + watts) / chamber_capacity;
    elapsed_ms += 100;
    temperature[2] = room(double(elapsed_ms) / 1000);
    energy_from_loads += watts * dt;
    energy_from_fermentation += ferm * dt;
    energy_from_room += ambient * dt;
    for (size_t i = 0; i < 3; ++i)
        lagged[i] = lag > 0 ? temperature[i] + (lagged[i] - temperature[i]) * std::exp(-dt / lag)
                            : temperature[i];
    if (elapsed_ms % 1000 == 0)
        sample_probes();
}
std::optional<int> Plant::read(size_t i) const {
    return available.at(i) ? std::optional<int>{probe.at(i)} : std::nullopt;
}
void Plant::set_temperature(size_t i, double c) {
    temperature.at(i) = c;
    lagged.at(i) = c;
    if (i == 2)
        room_base = c;
    sample_probes();
}
void Plant::set_connected(size_t i, bool yes) {
    available.at(i) = yes;
}
Json Plant::observations() const {
    Json::Array temps, probes, online;
    for (size_t i = 0; i < 3; ++i) {
        temps.emplace_back(temperature[i]);
        probes.emplace_back(probe[i]);
        online.emplace_back(available[i]);
    }
    return Json::Object{{"temperatures_c", temps},
                        {"probes_raw", probes},
                        {"connected", online},
                        {"age_ms", double(elapsed_ms)},
                        {"beer_capacity_j_per_k", beer_capacity},
                        {"chamber_capacity_j_per_k", chamber_capacity},
                        {"load_energy_j", energy_from_loads},
                        {"fermentation_energy_j", energy_from_fermentation},
                        {"room_energy_j", energy_from_room},
                        {"fermentation_watts", fermentation(double(elapsed_ms) / 1000)},
                        {"door_open", door}};
}
Json Plant::snapshot() const {
    Json j = observations();
    Json::Array lag_values;
    for (double v : lagged)
        lag_values.emplace_back(v);
    j["lagged"] = lag_values;
    j["scenario"] = scenario;
    j["random"] = double(random);
    j["room_base"] = room_base;
    return j;
}
void Plant::restore(const Json& j) {
    configure(j.at("scenario"));
    auto size3 = [](const Json& a) {
        if (a.array().size() != 3)
            throw std::runtime_error("invalid checkpoint plant vector");
    };
    for (auto name : {"temperatures_c", "probes_raw", "connected", "lagged"})
        size3(j.at(name));
    for (size_t i = 0; i < 3; ++i) {
        temperature[i] = j.at("temperatures_c").array()[i].number();
        lagged[i] = j.at("lagged").array()[i].number();
        probe[i] = j.at("probes_raw").array()[i].integer();
        if (probe[i] < -32766 || probe[i] > 32767)
            throw std::runtime_error("invalid checkpoint physical probe word");
        available[i] = j.at("connected").array()[i].boolean();
    }
    double time = j.at("age_ms").number(), rng = j.at("random").number();
    if (time < 0 || time > 9007199254740000.0 || time != std::floor(time) || rng < 0 ||
        rng > 4294967295.0 || rng != std::floor(rng))
        throw std::runtime_error("invalid checkpoint plant clock/random state");
    elapsed_ms = uint64_t(time);
    if (elapsed_ms % 100)
        throw std::runtime_error("invalid checkpoint physical step boundary");
    random = uint32_t(rng);
    energy_from_loads = j.at("load_energy_j").number();
    energy_from_fermentation = j.at("fermentation_energy_j").number();
    energy_from_room = j.at("room_energy_j").number();
    room_base = j.at("room_base").number();
    door = j.at("door_open").boolean();
}
} // namespace rmx
