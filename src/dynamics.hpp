// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "json.hpp"
#include "profile.hpp"

#include <array>
#include <cstdint>
#include <map>
#include <optional>

namespace rmx {
// Heater, cooler, fan, light: -1 has no modeled load, 0 is inactive, 1 is active.
using EquipmentStates = std::array<int, 4>;
int word16(int64_t n);
int32_t word32(int64_t n);
int64_t signed_shift(int64_t n, unsigned bits);
int temperature_limit(int64_t n);
int absolute_raw(double c);

// Original delay-state realization of the specified fixed-point transfer function.
class Signal {
    std::array<std::array<int32_t, 4>, 3> delays{};
    std::array<int32_t, 3> recent{};

  public:
    unsigned coefficient = 2;
    void seed(int raw);
    int value() const;
    int32_t precise() const {
        return recent[0];
    }
    void push(int32_t precise_input);
    std::optional<int> turn(bool positive) const;
    Json snapshot() const;
    void restore(const Json& j);
};
struct SensorHistory {
    Signal fast, slow, slope;
    unsigned countdown = 255, missed = 255;
    int32_t slope_origin = 0;
    bool connected = false;
    void seed(int raw);
    void sample(int raw);
    Json snapshot() const;
    void restore(const Json& j);
};

// Independent equipment energy model; no controller decisions reside here.
class Plant {
    Profile profile;
    Json scenario;
    std::array<double, 3> temperature{{20, 20, 20}}, lagged{{20, 20, 20}};
    std::array<int, 3> probe{{-14336, -14336, -14336}};
    std::array<bool, 3> available{{true, true, true}}, probe_reset{{false, false, false}};
    uint32_t random = 1;
    double beer_capacity = 85114.86, chamber_capacity = 2484, bc = 3, cr = 1.67;
    double quantum = .0625, lag = 0, noise = 0, room_base = 20, room_amplitude = 0, room_phase = 0;
    bool ferment = false, door = false;
    double fermentation_age_hours = 0;
    std::vector<std::array<double, 2>> fermentation_points;
    double door_conductance = 0;
    int door_pin = 4;
    struct Load {
        int pin;
        double watts;
        bool low;
        size_t equipment;
    };
    std::vector<Load> loads;
    double fermentation(double age_seconds) const;
    void sample_probes();

  public:
    uint64_t elapsed_ms = 0;
    double energy_from_loads = 0, energy_from_fermentation = 0, energy_from_room = 0;
    explicit Plant(Profile profile = Profile::revc);
    void configure(const Json& config);
    void step(const std::map<int, bool>& pins); // fixed 100 ms
    EquipmentStates equipment_states(const std::map<int, bool>& pins) const;
    std::optional<int> read(size_t index) const;
    void set_temperature(size_t index, double c);
    void set_connected(size_t index, bool yes);
    bool needs_initialization(size_t index) const {
        return probe_reset.at(index);
    }
    void set_probe_reset(size_t index, bool reset) {
        probe_reset.at(index) = reset;
    }
    int door_input_pin() const {
        return door_pin;
    }
    bool door_open() const {
        return door;
    }
    void set_door(bool yes) {
        door = yes;
    }
    Json observations() const;
    Json snapshot() const;
    void restore(const Json& j);
};
} // namespace rmx
