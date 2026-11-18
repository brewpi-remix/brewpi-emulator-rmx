// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <array>
#include <stdexcept>
#include <string>

namespace rmx {
enum class Profile { revc, i2c };
inline const char* profile_name(Profile profile) {
    return profile == Profile::i2c ? "i2c" : "revc";
}
// Both selected prebuilt Uno images carry this stamp. The source reference
// commit is separate from the emulated artifact identity.
inline const char* profile_revision(Profile) {
    return "da7e14a9";
}
inline Profile parse_profile(const std::string& name) {
    if (name == "revc")
        return Profile::revc;
    if (name == "i2c")
        return Profile::i2c;
    throw std::runtime_error("invalid controller profile: " + name);
}
struct ProfileHardware {
    int shield, probe;
    std::array<int, 4> outputs;
    int heater, cooler, light, fan;
    bool door_active_low;
};
inline ProfileHardware profile_hardware(Profile profile) {
    return profile == Profile::i2c ? ProfileHardware{5, 14, {5, 6, 2, 10}, 6, 5, 2, 10, true}
                                   : ProfileHardware{2, 18, {2, 5, 6, 19}, 5, 6, 2, 19, false};
}
inline int probe_pin(Profile profile) {
    return profile_hardware(profile).probe;
}
inline std::array<int, 4> output_pins(Profile profile) {
    return profile_hardware(profile).outputs;
}
} // namespace rmx
