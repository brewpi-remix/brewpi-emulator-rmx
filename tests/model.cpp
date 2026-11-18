// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace rmx;
void require(bool condition, const char* message) {
    if (!condition)
        throw std::runtime_error(message);
}
Json without_profile(const Json& value) {
    Json::Object fields;
    for (const auto& entry : value.object())
        if (entry.first != "profile")
            fields.push_back(entry);
    return fields;
}
void profiles() {
    std::string implicit_output, explicit_output;
    Engine implicit([&](const std::string& s) { implicit_output += s; });
    Engine explicit_revc([&](const std::string& s) { explicit_output += s; }, Profile::revc);
    implicit.feed("Enh{}");
    explicit_revc.feed("Enh{}");
    require(implicit_output == explicit_output &&
                implicit.checkpoint().dump() == explicit_revc.checkpoint().dump(),
            "default and explicit RevC differ");
    for (auto profile : {Profile::revc, Profile::i2c}) {
        bool i2c = profile == Profile::i2c;
        int bus = i2c ? 14 : 18;
        std::string output;
        Engine engine([&](const std::string& s) { output += s; }, profile);
        auto request = [&](const std::string& command) {
            output.clear();
            engine.feed(command);
            return Json::parse(output.substr(2));
        };
        const Json expected_identity =
            Json::Object{{"v", "0.2.13"}, {"n", "da7e14a9"}, {"s", i2c ? 5 : 2},
                         {"y", 0},        {"b", "s"},        {"l", "3"}};
        require(request("n").dump() == expected_identity.dump(), "wrong profile identity");
        engine.feed("E");
        auto inventory = request("h{}").array();
        require(inventory.size() == 7, "profile inventory size changed");
        const std::array<int, 4> expected =
            i2c ? std::array<int, 4>{5, 6, 2, 10} : std::array<int, 4>{2, 5, 6, 19};
        const std::array<std::string, 3> roms{"28A1010000000204", "28A10100000001E6",
                                              "28A101000000035A"};
        for (size_t i = 0; i < 3; ++i) {
            require(inventory[i].at("p").integer() == bus, "wrong probe bus inventory");
            require(inventory[i].at("a").string() == roms[i], "probe search order changed");
        }
        for (size_t i = 0; i < 4; ++i)
            require(inventory[i + 3].at("p").integer() == expected[i], "wrong output order");
        auto installed = request("U{i:0,f:9,h:2,p:" + std::to_string(bus) + ",a:28A10100000001E6}");
        require(installed.at("p").integer() == bus && installed.at("f").integer() == 9,
                "profile probe assignment failed");
        require(request("t").at("BeerTemp").number() == 20, "assigned probe did not read");
        output.clear();
        engine.feed("U{i:0,f:9,h:2,p:" + std::to_string(i2c ? 18 : 14) + ",a:28A10100000001E6}");
        require(output.find("\"logID\":9") != std::string::npos,
                "other profile's OneWire bus was accepted");
        require(request("d{i:0}").array()[0].at("p").integer() == bus,
                "failed assignment changed slot");
        // Digital acceptance remains firmware-like, not restricted to discovery.
        auto digital = request("U{i:1,f:2,h:1,p:18,x:1}");
        require(digital.at("p").integer() == 18, "profile tightened digital validation");
        // Exercise the real controller/output/plant path as well as the plant
        // equation below; advancing time must heat on the selected profile pin.
        request("U{i:2,f:2,h:1,p:" + std::to_string(i2c ? 6 : 5) + ",x:1}");
        engine.feed("j{mode:t}d{i:2,w:1}");
        engine.advance_ms(1000);
        require(engine.observations().at("plant").at("load_energy_j").number() == 25,
                "profile actuator did not drive its physical load");
        // Continue a running, energized system, including histories and thermal state.
        Engine active_copy([](const std::string&) {}, profile);
        active_copy.restore_checkpoint(engine.checkpoint());
        engine.advance_ms(1300);
        active_copy.advance_ms(1300);
        require(active_copy.checkpoint().dump() == engine.checkpoint().dump(),
                "active profile checkpoint continuation diverged");
        Engine cooler([](const std::string&) {}, profile);
        cooler.feed("EU{i:0,f:3,h:1,p:" + std::to_string(i2c ? 5 : 6) + ",x:1}j{mode:t}d{i:0,w:1}");
        cooler.advance_ms(1000);
        require(cooler.observations().at("plant").at("load_energy_j").number() == -60,
                "profile cooling actuator did not drive its physical load");
        auto before_restart = engine.store_image();
        engine.feed("R");
        engine.restart(false);
        require(engine.store_image().dump() == before_restart.dump(), "R changed saved profile");
        auto store = engine.store_image();
        require(store.at("profile").string() == profile_name(profile), "store lost profile");
        require(store.at("format").string() ==
                    (i2c ? "brewpi-emulator-store-v2" : "brewpi-emulator-store-v1"),
                "I2C store is not protected from older executables");
        Engine loaded([](const std::string&) {}, profile);
        loaded.load_store(store);
        loaded.boot(false);
        require(loaded.store_image().dump() == store.dump(), "store reload changed assignments");
        // A saved record on the other bus is discarded by firmware-style boot validation.
        auto wrong_bus = store;
        auto devices = wrong_bus.at("devices").array();
        devices[0]["p"] = i2c ? 18 : 14;
        wrong_bus["devices"] = devices;
        Engine invalid_slot([](const std::string&) {}, profile);
        invalid_slot.load_store(wrong_bus);
        invalid_slot.boot(false);
        require(invalid_slot.store_image().at("devices").array()[0].at("f").integer() == 0,
                "saved probe bypassed selected-bus validation");
        // An invalid saved record is cleared durably before a later sensor waits.
        auto partial = wrong_bus;
        auto partial_devices = partial.at("devices").array();
        partial_devices[1] = store.at("devices").array()[0];
        partial_devices[1]["f"] = 5;
        partial_devices[1]["b"] = 0;
        partial_devices[1]["rom"] = "28A1010000000204";
        partial["devices"] = partial_devices;
        Engine initializing([](const std::string&) {}, profile);
        initializing.load_store(partial);
        initializing.configure_plant(
            Json::Object{{"probe_reset", Json::Array{false, true, false}}});
        Json durable;
        initializing.on_save([&](const Json& image) { durable = image; });
        initializing.boot();
        initializing.advance_ms(i2c ? 2200 : 2300);
        require(initializing.dispatch_suspended(), "cold probe did not suspend boot");
        require(initializing.store_image().at("devices").array()[0].at("f").integer() == 0,
                "invalid record not cleared before conversion wait");
        require(durable.dump() == initializing.store_image().dump(),
                "boot checkpoint diverged from durable records during conversion wait");
        Engine boot_copy([](const std::string&) {}, profile);
        boot_copy.restore_checkpoint(initializing.checkpoint());
        initializing.advance_ms(800);
        boot_copy.advance_ms(800);
        require(boot_copy.checkpoint().dump() == initializing.checkpoint().dump(),
                "boot initialization continuation diverged");
        auto checkpoint = engine.checkpoint();
        Engine continued([](const std::string&) {}, profile);
        continued.restore_checkpoint(checkpoint);
        require(continued.checkpoint().dump() == checkpoint.dump(),
                "checkpoint changed profile state");
        engine.restart(false);
        require(request("n").at("s").integer() == (i2c ? 5 : 2), "restart lost profile");
        require(request("d{i:0}").array()[0].at("p").integer() == bus, "restart lost probe");
        Engine other([](const std::string&) {}, i2c ? Profile::revc : Profile::i2c);
        auto before = other.checkpoint().dump();
        for (bool snapshot : {false, true}) {
            bool rejected = false;
            try {
                if (snapshot)
                    other.restore_checkpoint(checkpoint);
                else
                    other.load_store(store);
            } catch (const std::runtime_error&) {
                rejected = true;
            }
            require(rejected && other.checkpoint().dump() == before,
                    "profile mismatch was accepted or mutated state");
        }
        auto legacy_store = without_profile(store);
        auto legacy_checkpoint = without_profile(checkpoint);
        legacy_checkpoint["store"] = legacy_store;
        Engine legacy([](const std::string&) {}, profile);
        for (bool snapshot : {false, true}) {
            bool rejected = false;
            try {
                if (snapshot)
                    legacy.restore_checkpoint(legacy_checkpoint);
                else
                    legacy.load_store(legacy_store);
            } catch (const std::runtime_error&) {
                rejected = true;
            }
            require(rejected == i2c, "legacy profile interpretation changed");
        }
        if (i2c) {
            Engine revc([](const std::string&) {});
            bool refused = false;
            try {
                revc.load_store(legacy_store);
            } catch (const std::runtime_error&) {
                refused = true;
            }
            require(refused, "untagged I2C store was interpreted as RevC");
        }
        for (const auto& bad_tag : {Json("bogus"), Json(5), Json(nullptr)}) {
            auto malformed = store;
            malformed["profile"] = bad_tag;
            bool rejected = false;
            try {
                loaded.load_store(malformed);
            } catch (const std::exception&) {
                rejected = true;
            }
            require(rejected && loaded.store_image().dump() == store.dump(),
                    "invalid profile metadata was accepted or changed saved state");
            auto malformed_checkpoint = checkpoint;
            malformed_checkpoint["profile"] = bad_tag;
            const auto unchanged = continued.checkpoint().dump();
            rejected = false;
            try {
                continued.restore_checkpoint(malformed_checkpoint);
            } catch (const std::exception&) {
                rejected = true;
            }
            require(rejected && continued.checkpoint().dump() == unchanged,
                    "invalid checkpoint profile was accepted or changed live state");
        }
        auto conflicting_format = store;
        conflicting_format["format"] =
            i2c ? "brewpi-emulator-store-v1" : "brewpi-emulator-store-v2";
        bool format_rejected = false;
        try {
            loaded.load_store(conflicting_format);
        } catch (const std::runtime_error&) {
            format_rejected = true;
        }
        require(format_rejected && loaded.store_image().dump() == store.dump(),
                "conflicting format/profile was accepted or changed saved state");
        auto contradictory = checkpoint;
        contradictory["store"]["profile"] = i2c ? "revc" : "i2c";
        auto original = continued.checkpoint().dump();
        bool rejected = false;
        try {
            continued.restore_checkpoint(contradictory);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        require(rejected && continued.checkpoint().dump() == original,
                "contradictory checkpoint tags were accepted or changed live state");
        Plant plant(profile);
        plant.configure(Json::Object{{"beer_chamber_conductance_w_per_k", 0},
                                     {"chamber_room_conductance_w_per_k", 0}});
        for (int i = 0; i < 10; ++i)
            plant.step({{i2c ? 6 : 5, false}});
        require(plant.observations().at("load_energy_j").number() == 25,
                "profile heater wiring did not deliver expected energy");
        Plant cooling(profile);
        for (int i = 0; i < 10; ++i)
            cooling.step({{i2c ? 5 : 6, false}});
        require(cooling.observations().at("load_energy_j").number() == -60,
                "profile cooler wiring did not remove expected energy");
        // Explicit physical wiring remains an operator choice in either profile.
        plant.configure(Json::Object{
            {"physical_loads",
             Json::Array{Json::Object{
                 {"pin", 19}, {"kind", "heater"}, {"watts", 10}, {"active_low", true}}}}});
        plant.step({{19, false}, {5, false}, {6, false}});
        require(plant.observations().at("load_energy_j").number() == 1,
                "profile replaced explicit scenario wiring");
        plant.configure(Json::Object{{"physical_loads", Json::Array{}}});
        plant.step({{19, false}, {5, false}, {6, false}});
        require(plant.observations().at("load_energy_j").number() == 0,
                "profile ignored explicit empty physical loads");
    }
}
void duplicate_actuator_fallback() {
    // These four I2C histories were observed on D6/D10 through independent inputs.
    // Raw bench captures remain external; these expectations are original descriptions.
    for (bool initially_active : {false, true}) {
        for (bool remove_older_first : {false, true}) {
            std::string output;
            Engine engine([&](const std::string& text) { output += text; }, Profile::i2c);
            auto request = [&](const std::string& command) {
                output.clear();
                engine.feed(command);
                return Json::parse(output.substr(2));
            };
            auto pin = [&](int number) {
                auto observed = engine.observations();
                for (const auto& row : observed.at("pins").array())
                    if (row.array()[0].integer() == number)
                        return row.array()[1].boolean();
                throw std::runtime_error("expected actuator pin is missing");
            };
            engine.feed("Ej{mode:t}U{i:4,f:2,h:1,p:6,x:1,d:0}");
            request(std::string("d{i:4,w:") + (initially_active ? "1}" : "0}"));
            request("U{i:8,f:2,h:1,p:10,x:1,d:0}");
            require(pin(6) == !initially_active && pin(10), "duplicate changed old pin history");
            for (int slot : {4, 8}) {
                for (int active : {1, 0}) {
                    request("d{i:" + std::to_string(slot) + ",w:" + std::to_string(active) + "}");
                    for (int alias : {4, 8})
                        require(request("d{i:" + std::to_string(alias) + ",r:1}")
                                        .array()[0]
                                        .at("v")
                                        .integer() == active,
                                "duplicate alias did not read the shared live actuator");
                    require(pin(6) == !initially_active && pin(10) == !active,
                            "duplicate alias drove the wrong physical pin");
                }
            }
            request("d{i:8,w:1}");
            int removed = remove_older_first ? 4 : 8;
            int survivor = remove_older_first ? 8 : 4;
            request("U{i:" + std::to_string(removed) + ",f:0}");
            require(
                request("d{i:" + std::to_string(survivor) + ",r:1}").array()[0].at("v").integer() ==
                    0,
                "surviving alias omitted the fallback's initial reading");
            for (int active : {1, 0}) {
                request("d{i:" + std::to_string(survivor) + ",w:" + std::to_string(active) + "}");
                require(request("d{i:" + std::to_string(survivor) + ",r:1}")
                                .array()[0]
                                .at("v")
                                .integer() == active,
                        "surviving alias did not read/write the fallback");
                require(pin(6) == !initially_active && !pin(10),
                        "fallback write changed an orphaned physical pin");
            }
            request("U{i:" + std::to_string(survivor) + ",f:0}");
            require(pin(6) == !initially_active && !pin(10),
                    "assignment removal reset an orphaned pin");
        }
    }
}

int main() {
    require(word32(2147483648LL) == -2147483647 - 1, "positive long wrap differs");
    require(word32(-2147483649LL) == 2147483647, "negative long wrap differs");
    require(word32(4294967296LL) == 0, "whole long modulus differs");
    require(word32(2147483647LL * 512) == -512, "long product must wrap before shifting");
    for (const auto& sample : {std::array<int64_t, 3>{32767, -2147352576LL, -235929600},
                               std::array<int64_t, 3>{-32766, 2147418112LL, 235929600}}) {
        SensorHistory history;
        history.seed(static_cast<int>(sample[0]));
        history.slope_origin = static_cast<int32_t>(sample[1]);
        history.countdown = 1;
        history.sample(static_cast<int>(sample[0]));
        const auto first_input =
            history.slope.snapshot().at("delays").array()[0].array()[0].integer();
        require(first_input == sample[2], "slope difference must wrap before its clamp");
    }

    try {
        profiles();
        duplicate_actuator_fallback();
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
