// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "json.hpp"

#include <array>
#include <functional>
#include <map>
#include <optional>
#include <string>

namespace rmx {
struct Device {
    int c = 0, b = 0, f = 0, h = 0, d = 0, p = 0, x = 0, cal = 0;
    std::string rom = "0000000000000000";
};
class Engine {
  public:
    using Sink = std::function<void(const std::string&)>;
    explicit Engine(Sink sink);
    void feed(const std::string& bytes);
    void read_timeout();
    bool reading() const {
        return phase != Phase::dispatch;
    }
    bool restarting() const {
        return restart_requested;
    }
    void boot();
    void restart();
    void load_store(const Json& image);
    Json store_image() const;
    void on_save(std::function<void(const Json&)> fn) {
        save_callback = std::move(fn);
    }
    // Test construction is isolated in the test driver, not a wire command or runtime API.
    void construct(const Json& state);
    void precondition(const Json& fields);
    Json observations() const;

  private:
    enum class Phase { dispatch, brace, key, value };
    Sink output;
    std::function<void(const Json&)> save_callback;
    std::map<std::string, int> settings, constants, variables, saved_settings, saved_constants;
    std::array<Device, 16> slots{};
    std::map<int, Device> targets;
    std::map<int, bool> pins;
    bool valid = false, restart_requested = false, alarm = false, camera = false, fallback = false;
    int state = 0, last_saved_target = -32767;
    Phase phase = Phase::dispatch;
    char command = 0;
    std::string key, value;
    std::map<char, int> fields;
    std::optional<std::string> address;
    void byte(unsigned char c);
    void token(std::optional<unsigned char> c);
    void pair();
    void finish();
    void frame(char prefix, const std::string& body);
    void diagnostic(char type, int id, Json::Array args = {});
    void defaults(bool cs, bool cc);
    void save(bool cc);
    void setting(const std::string& k, const std::string& v);
    void mode(int m);
    void command_evaluation();
    bool fahrenheit() const;
    std::string number(int raw, int decimals, int category) const;
    std::optional<int> convert(const std::string& text, int category) const;
    std::string settings_wire() const;
    std::string constants_wire() const;
    std::string variables_wire() const;
    void telemetry(const std::string& beer = "", const std::string& fridge = "");
    std::string lcd() const;
    int validate(const Device& d);
    void install(const Device& d);
    bool live_target(const Device& d) const;
    std::optional<int> reading_raw(const Device& d, bool filtered = false) const;
    std::string device_wire(const Device& d, int index, std::optional<std::string> val = {}) const;
    void update_device();
    void query_slots();
    void discover();
    static Device decode_device(const Json& j);
    static Json encode_device(const Device& d);
};
} // namespace rmx
