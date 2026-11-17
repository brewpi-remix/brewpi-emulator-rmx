// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "dynamics.hpp"
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
    explicit Engine(Sink sink, Profile profile = Profile::revc);
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
    void configure_plant(const Json& scenario);
    void advance_ms(uint64_t milliseconds, bool controller_allowed = true);
    void service_controller(bool allowed = true);
    void evaluate_pid();
    void evaluate_state();
    void update_outputs();
    void update_sensors();
    void detect_peaks();
    Json checkpoint() const;
    std::array<std::string, 4> lcd_rows() const {
        return local_rows();
    }
    // Local physical-action boundary, separate from serial parsing and EEPROM.
    std::string local_action(const std::string& action, uint64_t wall_ms, bool writable = true);
    void local_tick(uint64_t wall_ms);
    void local_cancel();
    uint64_t local_revision() const {
        return local_epoch;
    }
    bool local_door() const {
        return plant.door_open();
    }
    EquipmentStates local_equipment() const {
        return plant.equipment_states(pins);
    }
    std::array<std::string, 4> local_rows() const;
    void restore_checkpoint(const Json& snapshot);
    uint16_t seconds() const {
        return uint16_t(controller_ms / 1000);
    }

  private:
    Profile profile;
    uint64_t local_epoch = 0;
    struct LocalMenu {
        enum Page { idle, setting, mode, beer, fridge } page = idle;
        int index = 0, proposed_mode = 0, target = 0, low = 0, high = 0;
        bool rotated = false;
        uint64_t changed = 0, now = 0;
    } menu;
    std::array<int, 5> local_dependencies() const;
    std::string local_temperature(bool beer);
    int local_tenth(int tenth) const;
    int local_to_tenths(int raw) const;
    enum class Phase { dispatch, brace, key, value };
    Sink output;
    std::function<void(const Json&)> save_callback;
    std::map<std::string, int> settings, constants, variables, saved_settings, saved_constants;
    std::array<Device, 16> slots{};
    std::map<int, Device> targets;
    std::map<int, bool> pins;
    bool valid = false, restart_requested = false, alarm = false, camera = false, fallback = false;
    int state = 0, last_saved_target = -32767;
    Plant plant;
    std::map<int, SensorHistory> sensors{{5, {}}, {6, {}}, {9, {}}};
    uint32_t controller_ms = 0, last_evaluation_ms = uint32_t(-1000), last_lcd_reset = 0;
    uint64_t pending_ms = 0, integral_branches = 0;
    uint16_t last_idle = 0, last_heat = 0, last_cool = 0, wait_seconds = 0, camera_last = 0;
    unsigned integral_counter = 0;
    bool positive_pending = false, negative_pending = false, door_open = false;
    std::array<std::string, 4> screen;
    int screen_state = -1;
    bool screen_room = false;
    void apply_filter_constants();
    void render_display();
    void render_state();
    void stationary_display();
    void reset_display();
    void loop_evaluation();
    void write_actuator(int function, bool active);
    bool configured_actuator(int function) const;
    bool sense_switch(const Device& device) const;
    int filtered(int function, int kind) const;
    uint16_t since(uint16_t timestamp) const {
        return uint16_t(seconds() - timestamp);
    }
    static std::optional<size_t> physical_index(const Device& d);
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
