// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "dynamics.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace rmx;
void require(bool condition, const char* message) {
    if (!condition)
        throw std::runtime_error(message);
}
int main() {
    try {
        // Closed-form independent oracle: with b=0 the triple cascade is
        // (1+z^-1)^6 / [4096*(1-z^-1/2)^6]. Expand this binomial transfer
        // function for a 2^25 precise-unit impulse; the first nine outputs
        // are integral, so no quantization approximation is needed.
        const int expected[] = {8192,    73728,   313344,  847872, 1668096,
                                2589696, 3361536, 3806208, 3877344};
        Signal impulse;
        impulse.coefficient = 0;
        impulse.seed(0);
        for (size_t i = 0; i < 9; ++i) {
            impulse.push(i == 0 ? 33554432 : 0);
            require(impulse.precise() == expected[i],
                    "filter differs from independent binomial impulse oracle");
        }
        for (unsigned b = 0; b <= 8; ++b) {
            Signal s;
            s.coefficient = b;
            s.seed(-14336);
            for (int i = 0; i < 1000; ++i)
                s.push(-939524096);
            require(s.value() == -14336, "constant filter history drifted");
        }
        Signal restored;
        restored.restore(impulse.snapshot());
        for (int i = 0; i < 100; ++i) {
            impulse.push(100000);
            restored.push(100000);
            require(impulse.snapshot().dump() == restored.snapshot().dump(),
                    "filter history was not restored exactly");
        }
        Signal unsafe;
        unsafe.coefficient = 255;
        bool gap = false;
        try {
            unsafe.push(0);
        } catch (const std::runtime_error&) {
            gap = true;
        }
        require(gap, "undefined reference shift was executed natively");
        Plant plain, lagged;
        plain.configure(Json::Object{{"beer_chamber_conductance_w_per_k", 0},
                                     {"chamber_room_conductance_w_per_k", 0}});
        lagged.configure(Json::Object{{"beer_chamber_conductance_w_per_k", 0},
                                      {"chamber_room_conductance_w_per_k", 0},
                                      {"probe_lag_seconds", 10}});
        for (int i = 0; i < 1000; ++i) {
            plain.step({{5, false}});
            lagged.step({{5, false}});
        }
        double chamber = plain.observations().at("temperatures_c").array()[1].number();
        require(std::abs((*plain.read(1) / 512.0 + 48) - chamber) <= .03125,
                "probe quantization is outside half-step error");
        require(*lagged.read(1) < *plain.read(1) && *lagged.read(1) > -14336,
                "probe lag does not track a physical ramp");
        Plant noise;
        noise.configure(Json::Object{{"noise_amplitude_c", .15}, {"random_seed", 11}});
        bool changed = false;
        for (int i = 0; i < 100; ++i) {
            noise.step({});
            for (size_t p = 0; p < 3; ++p) {
                int raw = *noise.read(p);
                require(raw % 32 == 0, "probe is not on the declared DS18B20 grid");
                require(std::abs(raw / 512.0 + 48 - 20) <= .18125,
                        "noise exceeds declared bound plus quantization");
                changed |= raw != -14336;
            }
        }
        require(changed, "noise scenario did not perturb readings");
        Plant weather;
        weather.configure(
            Json::Object{{"room_daily_amplitude_c", 2}, {"room_daily_phase_hours", 6}});
        require(*weather.read(2) == -13312, "room curve's explicit phase is incorrect");
        for (auto name : {"beer_liters", "beer_density_kg_per_m3", "beer_specific_heat_j_per_kg_k",
                          "carboy_capacity_j_per_k", "chamber_liters", "cabinet_capacity_j_per_k",
                          "air_capacity_j_per_m3_k"}) {
            bool rejected = false;
            try {
                Plant invalid;
                invalid.configure(Json::Object{{name, -1}});
            } catch (const std::runtime_error&) {
                rejected = true;
            }
            require(rejected, "positive derived capacity concealed a negative physical component");
        }
        std::cout << "Independent filter impulse/DC/history, shift guard, lag/quantization/noise, "
                     "and room phase passed.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
