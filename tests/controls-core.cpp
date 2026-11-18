// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"

#include <iostream>
#include <stdexcept>
#include <vector>
using namespace rmx;
void require(bool ok, const char* message) {
    if (!ok)
        throw std::runtime_error(message);
}
void profile_doors() {
    for (auto profile : {Profile::revc, Profile::i2c}) {
        std::string wire;
        Engine door([&](const std::string& text) { wire += text; }, profile);
        int inversion = profile == Profile::i2c ? 1 : 0;
        door.feed("EU{i:5,f:4,h:1,p:2,x:1}U{i:7,f:1,h:1,p:4,x:" + std::to_string(inversion) +
                  "}j{mode:o}");
        auto reading = [&](int slot) {
            wire.clear();
            door.feed("d{i:" + std::to_string(slot) + ",r:1}");
            return Json::parse(wire.substr(2)).array()[0].at("v").integer();
        };
        door.advance_ms(1000);
        require(!door.local_door() && reading(7) == 0 && reading(5) == 0,
                "closed physical door did not release its configured contact");
        for (bool open : {true, false}) {
            door.local_action(open ? "door open" : "door close", 1);
            door.advance_ms(1000);
            require(door.local_door() == open && reading(7) == int(open) && reading(5) == int(open),
                    "physical door action disagrees with controller door/light readback");
        }
        door.feed("U{i:7,f:1,x:" + std::to_string(1 - inversion) + "}");
        require(reading(7) == 1, "door wiring fix bypassed firmware inversion");
    }
}
struct Bench {
    std::string wire;
    std::vector<Json> saves;
    Engine engine;
    explicit Bench(Profile profile) : engine([&](const std::string& s) { wire += s; }, profile) {
        engine.feed("Ej{mode:b,beerSet:20.023,fridgeSet:19}");
        engine.advance_ms(0);
        engine.on_save([&](const Json& j) { saves.push_back(j); });
        wire.clear();
    }
    void act(const std::string& command) {
        engine.local_action(command, 0);
    }
    void top(int item) {
        act("press");
        for (int n = 0; n < item; ++n)
            act("cw");
        act("press");
    }
    Json snap() const {
        return engine.checkpoint();
    }
    int setting(const char* key) const {
        return snap().at("settings").at(key).integer();
    }
    void elapse(int ms) {
        engine.advance_ms(unsigned(ms));
    }
};
void menu_mutations(Profile profile) {
    Bench b(profile);
    int original = b.setting("beerSet");
    b.top(0);
    b.act("cw");
    require(b.setting("mode") == 'f' && !b.saves.empty(), "mode rotation is still a draft");
    b.act("cw");
    require(b.setting("mode") == 'p', "mode order changed");
    b.act("cw");
    require(b.setting("mode") == 'o' && b.setting("beerSet") == -32767,
            "off preview did not disable targets");
    b.elapse(9900);
    require(b.engine.dispatch_suspended(), "menu timeout fired before clock boundary");
    b.elapse(100);
    require(!b.engine.dispatch_suspended() && b.setting("mode") == 'b',
            "mode timeout did not restore mode");
    require(b.setting("beerSet") == -32767, "mode timeout invented target rollback");
    require(!b.saves.empty(), "mode timeout omitted source store");
    b.engine.feed("R");
    b.engine.restart(false);
    require(b.setting("mode") == 'b' && b.setting("beerSet") == -32767,
            "mode timeout store did not survive restart");
    b.engine.feed("j{mode:p,beerSet:20.023}");
    b.top(1);
    require(b.setting("mode") == 'b', "temperature entry did not set mode");
    require(b.setting("beerSet") == original, "temperature entry changed target");
    size_t before = b.saves.size();
    b.act("cw");
    require(b.setting("beerSet") == original && b.saves.size() == before,
            "temperature rotation persisted candidate");
    b.elapse(10000);
    require(b.setting("mode") == 'b' && b.setting("beerSet") == original,
            "temperature timeout reverted entry mode or committed candidate");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(20), "unrotated confirmation did not quantize");
    require(b.wire.find("\"BeerAnn\":\"Beer temp set to  20.0 in Menu.\"") != std::string::npos,
            "menu annotation missing");
    b.engine.feed("j{mode:f,fridgeSet:19,mode:p}");
    b.top(2);
    require(b.setting("mode") == 'f', "fridge entry did not set mode");
    b.act("ccw");
    b.act("press");
    require(b.setting("fridgeSet") == -14899, "fridge tenth conversion differs"); // 18.9 C
    b.engine.feed("R");
    b.engine.restart(false);
    require(b.setting("mode") == 'f' && b.setting("fridgeSet") == -14899,
            "confirmed menu value did not persist");
    for (const std::string selection : {"p", "o"}) {
        b.engine.feed("j{mode:" + selection + "}");
        b.top(0);
        b.act("press");
        require(!b.engine.dispatch_suspended(), "mode confirmation did not exit");
    }
    require(b.wire.find("Changed to profile mode in menu") != std::string::npos &&
                b.wire.find("Temp control turned off in menu") != std::string::npos,
            "mode annotations missing");
}
void menu_numbers(Profile profile) {
    Bench b(profile);
    b.engine.feed("j{beerSet:30}");
    b.top(1);
    b.act("cw");
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(1), "upper range failed to wrap");
    b.top(1);
    b.act("ccw");
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(30), "lower range failed to wrap");
    b.engine.feed("j{beerSet:31}");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(31), "unrotated start was clamped to bounds");
    b.engine.feed("j{beerSet:20,tempSetMin:20.01,tempSetMax:20.02}");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(20), "rounded range gained new validity rule");
    b.engine.feed("j{tempFormat:F,tempSetMin:33.8,tempSetMax:86,beerSet:68.023}");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(20), "F unrotated confirmation not quantized");
    b.engine.feed("j{hs:1}");
    b.top(1);
    b.act("cw");
    b.act("press");
    require(b.setting("beerSet") == -14308, "F tenth conversion differs");
    b.engine.feed("j{tempFormat:C,tempSetMin:-5,tempSetMax:30,beerSet:-2.023}");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == -25599,
            "negative tenths conversion lost its signed truncation");
    b.engine.feed("j{mode:o}");
    b.top(1);
    b.act("press");
    require(b.setting("beerSet") == absolute_raw(20), "disabled target did not start at20C");
    b.engine.feed("j{mode:x}");
    b.act("press");
    require(b.engine.local_action("press", 0).find("Fidelity gap") != std::string::npos,
            "invalid mode lookup was normalized or executed");
    b.act("cancel");
}
void menu_blocking(Profile profile) {
    Bench b(profile);
    b.engine.feed(std::string("U{i:0,f:1,h:1,p:4,x:") + (profile == Profile::i2c ? "1" : "0") +
                  "}U{i:1,f:4,h:1,p:2,x:0}j{mode:t}");
    b.engine.feed("d{i:1,w:1}");
    // Temperature path works even if mode browsing itself would be undefined.
    b.top(1);
    auto start = b.snap();
    b.wire.clear();
    b.engine.feed("nsc");
    b.act("door open");
    b.elapse(5000);
    auto held = b.snap();
    require(b.wire.empty(), "serial dispatch ran inside menu");
    for (const auto* key : {"histories", "pins", "integral_counter", "door", "last_evaluation_ms"})
        require(start.at(key).dump() == held.at(key).dump(), "ordinary work ran inside menu");
    require(held.at("controller_ms").integer() == start.at("controller_ms").integer() + 5000,
            "menu froze firmware clock");
    require(held.at("plant").dump() != start.at("plant").dump(), "menu froze external plant");
    b.elapse(5000);
    require(!b.engine.dispatch_suspended(), "temperature timeout did not resume");
    require(b.wire.find("N:") != std::string::npos && b.wire.find("N:") < b.wire.find("S:") &&
                b.wire.find("S:") < b.wire.find("C:"),
            "queued reply order changed");
    require(b.snap().at("door").boolean() && b.wire.find("Fridge door opened") < b.wire.find("N:"),
            "deferred door sensing did not precede serial dispatch");
    require(b.snap().at("integral_counter").integer() == start.at("integral_counter").integer() + 1,
            "menu resume invented catch-up evaluations");
    b.wire.clear();
    b.engine.feed("j{");
    b.act("press");
    require(!b.engine.dispatch_suspended(), "local press interrupted partial serial parser");
    b.engine.read_timeout();
    b.engine.advance_ms(0);
    require(b.engine.dispatch_suspended(), "pending encoder push was lost during parser wait");
    b.act("cancel");
    b.engine.feed("n");
    require(b.wire.find("N:") != std::string::npos, "cancel stranded serial input");
}
void menu_checkpoint(Profile profile) {
    Bench b(profile);
    b.top(0);
    b.act("ccw"); // off is persisted immediately
    b.engine.feed("n");
    b.elapse(2300);
    auto before_backpressure = b.snap();
    b.engine.local_action("press", 0, false);
    Engine pending([](const std::string&) {}, profile);
    pending.restore_checkpoint(b.snap());
    require(pending.checkpoint().dump() == b.snap().dump(),
            "pending encoder latch was not resumable");
    b.engine.restore_checkpoint(before_backpressure);
    auto saved = b.snap();
    Engine resumed([](const std::string&) {}, profile);
    resumed.restore_checkpoint(saved);
    require(resumed.checkpoint().dump() == saved.dump() &&
                resumed.lcd_rows() == b.engine.lcd_rows(),
            "checkpoint dropped menu state");
    b.elapse(7700);
    resumed.advance_ms(7700);
    require(resumed.checkpoint().dump() == b.snap().dump(), "resumed timeout diverged");
    for (const auto* field : {"page", "changed", "old_mode", "blink_started", "queued_hex"}) {
        auto bad = saved;
        if (std::string(field) == "queued_hex")
            bad["menu"][field] = "0Z";
        else
            bad["menu"][field] = -1;
        auto before = resumed.checkpoint().dump();
        bool rejected = false;
        try {
            resumed.restore_checkpoint(bad);
        } catch (const std::exception&) {
            rejected = true;
        }
        require(rejected && resumed.checkpoint().dump() == before,
                "bad menu snapshot mutated engine");
    }
    auto conflict = saved;
    conflict["startup"] = "display";
    bool rejected = false;
    try {
        resumed.restore_checkpoint(conflict);
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "incompatible continuation accepted");
    auto legacy = b.snap();
    // A pre-menu fixture contains neither optional field.
    Json clean(Json::Object{});
    for (const auto& entry : legacy.object())
        if (entry.first != "menu" && entry.first != "encoder")
            clean[entry.first] = entry.second;
    legacy = clean;
    resumed.restore_checkpoint(legacy);
    require(!resumed.dispatch_suspended(), "legacy checkpoint did not load idle");
}
void menu_clock(Profile profile) {
    Bench b(profile);
    auto state = b.snap();
    state["controller_ms"] = 65535900;
    state["last_evaluation_ms"] = 65535900;
    state["last_lcd_reset"] = 65535;
    b.engine.restore_checkpoint(state);
    b.act("press");
    b.engine.local_tick(999999999);
    require(b.engine.dispatch_suspended(), "wall time expired paused menu");
    b.elapse(9000); // second65535 to second8: elapsed9
    require(b.engine.dispatch_suspended(), "wrapped timeout fired early");
    b.elapse(100);
    // At65545000, wrapped seconds9: elapsed10 despite only9.1 elapsed seconds.
    require(!b.snap().has("menu"), "truncated-second timeout boundary differs");
    b.engine.advance_ms(2300); // finish the independently scheduled display reset
    state = b.snap();
    state["controller_ms"] = 4294967200.0;
    state["last_evaluation_ms"] = 4294967200.0;
    state["last_lcd_reset"] = 35127;
    b.engine.restore_checkpoint(state);
    b.act("press");
    require(b.snap().has("menu"), "menu entry failed before millis wrap");
    b.elapse(100);
    require(!b.snap().has("menu"),
            "millis wrap was normalized instead of preserving seconds discontinuity");
}
void startup_input_order(Profile profile) {
    Bench b(profile);
    int pin = profile == Profile::i2c ? 14 : 18;
    b.engine.feed("U{i:0,f:9,h:2,p:" + std::to_string(pin) + ",a:28A10100000001E6}");
    b.engine.precondition(Json::Object{{"probe_reset", Json::Array{true, false, false}}});
    b.engine.feed("R");
    b.engine.restart(true);
    b.elapse(profile == Profile::i2c ? 2200 : 2300);
    b.act("press");
    b.wire.clear();
    b.engine.feed("n");
    b.elapse(800);
    require(b.wire.empty() && b.snap().has("menu") &&
                b.snap().at("last_evaluation_ms").number() == 4294966296.0,
            "startup conversion resumed evaluation/serial before retained UI input");
    b.act("cancel");
    require(b.wire.find("N:") != std::string::npos, "startup menu exit lost queued identity");
}
void queued_resets(Profile profile) {
    Bench b(profile);
    b.engine.feed("j{mode:p}");
    int original = b.setting("beerSet");
    b.top(1);
    b.act("cw");
    b.engine.feed("R");
    require(!b.engine.restarting(), "R ran inside the menu");
    b.elapse(10000);
    require(b.engine.restarting(), "queued R did not resume");
    b.engine.restart(false);
    require(b.setting("mode") == 'b' && b.setting("beerSet") == original,
            "R lost entry-mode save or persisted the timed-out candidate");
    b.top(1);
    b.engine.feed("E");
    require(b.engine.dispatch_suspended(), "E ran inside menu");
    b.elapse(10000);
    require(!b.engine.dispatch_suspended() && b.setting("mode") == 'o',
            "queued E did not initialize after menu exit");
}
void startup_events(Profile profile) {
    Bench b(profile);
    b.engine.feed("R");
    b.engine.restart(true);
    b.wire.clear();
    b.engine.feed(std::string(100, 'n'));
    auto before_uart = b.snap();
    require(before_uart.at("display_reset").at("queued_hex").string().empty(),
            "disabled application UART retained early input");
    auto impossible = before_uart;
    impossible["display_reset"]["queued_hex"] = "6E";
    bool rejected = false;
    try {
        b.engine.restore_checkpoint(impossible);
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected && b.snap().dump() == before_uart.dump(),
            "checkpoint accepted input before UART enable");
    require(b.engine.local_action("press", 0) == "Encoder unavailable during startup",
            "logical encoder ran before UI initialization");
    b.elapse(2300);
    require(!b.snap().has("menu"), "pre-init push was replayed after startup");
    require(b.wire.find("N:") == std::string::npos,
            "pre-enable bytes were dispatched after startup");
    b.wire.clear();
    b.engine.feed("n");
    require(b.wire.rfind("N:", 0) == 0, "RX was not enabled after display initialization");
    b.engine.feed("j{");
    b.act("press");
    auto pending = b.engine.local_action("cw", 0);
    require(pending == "Encoder event retained", "initialized encoder event was not retained");
    b.engine.read_timeout();
    b.elapse(0);
    require(b.snap().has("menu"), "post-init pending push was lost");
    b.act("cancel");
}
void receive_limits(Profile profile) {
    for (const std::string suspension : {"menu", "display_reset", "sensor_initialization"}) {
        Bench b(profile);
        if (suspension == "menu")
            b.act("press");
        else if (suspension == "display_reset") {
            auto snapshot = b.snap();
            snapshot["controller_ms"] = 3600000;
            snapshot["last_evaluation_ms"] = 3600000;
            snapshot["last_lcd_reset"] = 3600;
            snapshot["display_reset"] = Json::Object{{"started_ms", 3600000}, {"queued_hex", ""}};
            b.engine.restore_checkpoint(snapshot);
        } else {
            b.engine.precondition(Json::Object{{"probe_reset", Json::Array{true, false, false}}});
            int bus = profile == Profile::i2c ? 14 : 18;
            b.engine.feed("U{i:0,f:9,h:2,p:" + std::to_string(bus) + ",a:28A10100000001E6}");
        }
        require(b.engine.dispatch_suspended(), "RX test did not establish a blocked consumer");
        b.wire.clear();
        // All these decoded byte arrivals occur while the consumer is blocked.
        b.engine.feed(std::string(62, 'n'));
        require(b.snap().at(suspension).at("queued_hex").string().size() == 124,
                "62-byte UART prefix was not retained");
        b.engine.feed("sc"); // byte63 fits; byte64 must be discarded independently
        auto full = b.snap();
        require(full.at(suspension).at("queued_hex").string().size() == 126,
                "artifact RX capacity is not63 bytes");
        b.engine.feed("v");
        require(b.snap().dump() == full.dump() && b.wire.empty(),
                "full UART RX did not silently discard newest arrivals");
        Engine resumed([](const std::string&) {}, profile);
        resumed.restore_checkpoint(full);
        require(resumed.checkpoint().dump() == full.dump(), "full RX queue did not resume exactly");
        auto oversized = full;
        oversized[suspension]["queued_hex"] = std::string(128, '6');
        bool rejected = false;
        try {
            resumed.restore_checkpoint(oversized);
        } catch (const std::exception&) {
            rejected = true;
        }
        require(rejected && resumed.checkpoint().dump() == full.dump(),
                "oversized UART snapshot was clipped or mutated the engine");
        if (suspension == "menu")
            b.act("cancel");
        else
            b.elapse(suspension == "display_reset" ? 2300 : 800);
        std::string prefixes;
        size_t start = 0;
        while (start < b.wire.size()) {
            prefixes += b.wire[start];
            auto end = b.wire.find("\r\n", start);
            require(end != std::string::npos, "unterminated resumed UART reply");
            start = end + 2;
        }
        require(prefixes ==
                    (suspension == "sensor_initialization" ? "U" : "") + std::string(62, 'N') + "S",
                "RX queue did not retain oldest bytes or fabricated an overflow diagnostic");
        b.wire.clear();
        b.engine.feed("v");
        require(b.wire.rfind("V:", 0) == 0, "RX did not accept input after draining");
    }
    Bench partial(profile);
    partial.act("press");
    partial.engine.feed(std::string(57, ' ') + "j{Kp:7}"); // closing brace is byte64
    partial.act("cancel");
    require(partial.engine.reading() && partial.wire.empty(),
            "RX overflow invented framing recovery");
    partial.engine.read_timeout();
    require(!partial.engine.reading() &&
                partial.snap().at("constants").at("Kp").integer() == 3584 &&
                partial.wire.find("\"logID\":12") != std::string::npos,
            "truncated RX token did not follow ordinary parser timeout/application");
    Bench b(profile);
    std::string bulk;
    for (int i = 0; i < 100; ++i)
        bulk += "ns";
    b.wire.clear();
    b.engine.feed(bulk);
    std::string expected = b.wire;
    b.wire.clear();
    for (char c : bulk)
        b.engine.feed(std::string(1, c));
    require(b.wire == expected, "unblocked ingress was truncated by host batch size");
}
void transmit_limits(Profile profile) {
    std::string expected;
    Engine logical([&](const std::string& text) { expected += text; }, profile);
    logical.feed("nn");
    require(expected.size() == 122, "unexpected identity length for TX boundary case");
    std::string wire;
    Engine timed([&](const std::string& text) { wire += text; }, profile);
    auto idle = timed.checkpoint();
    size_t waits = 0;
    timed.enable_uart([&](uint64_t us) {
        ++waits;
        require(timed.uart_waiting() && us == 170, "TX did not wait at its next nominal frame");
        bool rejected = false;
        try {
            timed.restore_checkpoint(idle);
        } catch (const std::exception&) {
            rejected = true;
        }
        require(rejected, "restore replaced a suspended TX continuation");
        timed.advance_uart_us(us);
    });
    timed.feed("n");
    require(wire.empty() && waits == 0, "short TX bypassed nominal serialization");
    timed.local_action("press", 0);
    require(timed.dispatch_suspended() && !timed.uart_waiting(),
            "background TX prevented a menu from starting");
    timed.advance_uart_us(169);
    require(wire.empty(), "TX completed before its full frame time");
    timed.advance_uart_us(1);
    require(wire == "N", "TX did not complete at170 microseconds");
    timed.advance_uart_us(170 * 60);
    require(wire == expected.substr(0, 61) && timed.checkpoint().has("menu"),
            "background TX drain changed byte order or bypassed the menu");
    timed.local_cancel();
    wire.clear();
    timed.feed("nn");
    require(waits == 57 && wire == expected.substr(0, 57),
            "TX did not retain63 software bytes plus two hardware positions");
    bool rejected = false;
    try {
        timed.checkpoint();
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "checkpoint lost queued TX or frame phase");
    timed.advance_uart_us(170 * 65 - 1);
    require(wire.size() == 121, "partial final TX frame was rounded away");
    timed.advance_uart_us(1);
    require(wire == expected && !timed.uart_pending(), "TX lost output while full or draining");
    timed.restore_checkpoint(idle);
    // R's existing reset boundary must preserve the preceding accepted output.
    wire.clear();
    timed.feed("nRn");
    require(timed.restarting() && wire == expected.substr(0, 61) && !timed.uart_pending(),
            "reset discarded accepted TX or executed bytes beyond its barrier");
    timed.restart(false);
    timed.advance_uart_us(100000);
    wire.clear();

    Bench b(profile);
    int heater = profile == Profile::i2c ? 6 : 5;
    b.engine.feed("U{i:3,f:2,h:1,p:" + std::to_string(heater) + ",x:1}j{mode:t}d{i:3,w:1}");
    b.engine.precondition(Json::Object{{"mode", "b"}});
    b.wire.clear();
    const auto before = b.engine.observations();
    const auto old_gain = b.snap().at("constants").at("Kp").integer();
    bool injected = false;
    b.engine.enable_uart([&](uint64_t us) {
        if (!injected) {
            injected = true;
            require(b.engine.store_image().at("constants_raw").at("Kp").integer() == old_gain,
                    "mutation ran past its blocked preceding diagnostic");
            b.engine.feed("d{i:3,r:1}" + std::string(52, 'n'));
            b.engine.feed("vs"); // v fits at63; s and the later h must disappear silently.
            b.engine.feed("h");
            b.engine.advance_ms(2500);
            const auto during = b.engine.observations();
            require(during.at("controller_millis").integer() == 2500 &&
                        during.at("integral_evaluation_count").dump() ==
                            before.at("integral_evaluation_count").dump() &&
                        during.at("pins").dump() == before.at("pins").dump(),
                    "TX stall ran ordinary controller work or changed latched outputs");
            require(during.at("plant").dump() != before.at("plant").dump(),
                    "TX stall froze external plant time");
            b.engine.advance_uart_us(us);
        } else
            b.engine.advance_uart_us(us);
    });
    b.engine.feed("n"); // 61 accepted bytes leave four immediate positions for I12.
    b.engine.feed("j{Kp:7}");
    b.engine.advance_uart_us(100000);
    auto after = b.snap();
    require(injected && after.at("constants").at("Kp").integer() == 3584 &&
                after.at("last_evaluation_ms").integer() == 2500,
            "blocked mutation did not resume before one overdue evaluation");
    std::string prefixes;
    bool read_active = false;
    size_t start = 0;
    while (start < b.wire.size()) {
        prefixes += b.wire[start];
        auto end = b.wire.find("\r\n", start);
        require(end != std::string::npos, "TX emitted a partial final reply");
        if (b.wire[start] == 'd')
            read_active = Json::parse(b.wire.substr(start + 2, end - start - 2))
                              .array()[0]
                              .at("v")
                              .integer() == 1;
        start = end + 2;
    }
    require(read_active && b.engine.observations().at("pins").dump() != before.at("pins").dump(),
            "ordinary outputs ran before queued RX or failed to resume afterward");
    require(prefixes == "NDSCd" + std::string(52, 'N') + "V",
            "RX during TX did not retain oldest63 bytes and silently drop new arrivals");
    b.wire.clear();
    b.engine.feed("s");
    b.engine.advance_uart_us(100000);
    require(b.wire.rfind("S:", 0) == 0, "RX did not recover after TX-stalled overflow");

    Bench ordered(profile), oracle(profile);
    oracle.engine.feed("cvs");
    bool later = false;
    ordered.engine.enable_uart([&](uint64_t us) {
        if (!later) {
            later = true;
            ordered.engine.feed("s");
        }
        ordered.engine.advance_uart_us(us);
    });
    ordered.engine.feed("cv");
    ordered.engine.advance_uart_us(100000);
    require(later && ordered.wire == oracle.wire,
            "TX stall reordered the unconsumed batch suffix behind later RX");
    Bench overflow(profile);
    overflow.engine.enable_uart([&](uint64_t us) { overflow.engine.advance_uart_us(us); });
    overflow.engine.feed("c" + std::string(62, 'n') + "vs");
    overflow.engine.advance_uart_us(100000);
    size_t rows = 0;
    for (size_t pos = 0; (pos = overflow.wire.find("\r\n", pos)) != std::string::npos; pos += 2)
        ++rows;
    require(rows == 64 && overflow.wire.rfind("C:", 0) == 0 &&
                overflow.wire.find("\r\nS:") == std::string::npos,
            "TX did not bound already-delivered batch input at its blocked boundary");
    Bench partial(profile);
    bool timeout_phase = false, queued = false;
    partial.engine.enable_uart([&](uint64_t us) {
        if (timeout_phase && !queued) {
            queued = true;
            partial.engine.feed("n");
        }
        partial.engine.advance_uart_us(us);
    });
    partial.engine.feed("c" + std::string(57, ' ') + "j{Kp:7}");
    partial.engine.advance_uart_us(100000);
    require(partial.engine.reading(), "TX-stalled overflow invented delimiter recovery");
    timeout_phase = true;
    partial.engine.read_timeout();
    partial.engine.advance_uart_us(100000);
    require(queued && !partial.engine.reading() &&
                partial.snap().at("constants").at("Kp").integer() == 3584 &&
                partial.wire.find("\r\nN:") != std::string::npos,
            "parser timeout failed to resume RX collected during blocked replies");
    Engine failed([](const std::string&) {}, profile);
    failed.enable_uart([](uint64_t) {});
    rejected = false;
    try {
        failed.feed("nn");
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "nonprogressing TX wait did not fail locally");
    failed.advance_uart_us(100000);
    rejected = false;
    try {
        failed.checkpoint();
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "failed TX continuation became a successful checkpoint");
}
void transmit_scheduling(Profile profile) {
    Bench input(profile);
    input.engine.enable_uart([&](uint64_t us) {
        auto completed = input.engine.uart_completed();
        input.engine.advance_uart_us(0);
        if (completed == input.engine.uart_completed())
            input.engine.advance_uart_us(us);
    });
    input.engine.queue_uart_rx("n");
    bool rejected = false;
    try {
        input.engine.checkpoint();
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "checkpoint omitted an unfinished RX frame");
    input.engine.advance_uart_us(169);
    require(input.wire.empty() && !input.engine.uart_pending(),
            "RX arrived before its frame completed");
    input.engine.advance_uart_us(1);
    require(input.wire.empty() && input.engine.uart_pending(),
            "RX was not decoded at its frame boundary");
    input.engine.advance_uart_us(61 * 170);
    require(input.wire.rfind("N:", 0) == 0 && !input.engine.uart_pending(),
            "full-duplex UART did not drain its identity");
    input.wire.clear();
    input.engine.queue_uart_rx(std::string(65536, ' '));
    rejected = false;
    try {
        input.engine.queue_uart_rx("n");
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected && input.engine.uart_input_space() == 0,
            "native wire admission overflow mutated or silently dropped input");
    input.engine.advance_uart_us(65536 * 170);
    require(input.wire.empty() && input.engine.uart_input_space() == 65536,
            "unblocked serialized input was capped at RX ring capacity");

    Bench streamed(profile), oracle(profile);
    int bus = profile == Profile::i2c ? 14 : 18;
    std::string patch = "U{ i:0, c:1, b:1, f:9, h:2, p:" + std::to_string(bus) +
                        ", a:28A10100000001E6, j:0.0625, n:0 }";
    require(patch.size() > 63, "paced RX test did not exceed one ringful");
    oracle.engine.feed("nn" + patch + "n");
    streamed.engine.enable_uart([&](uint64_t us) {
        auto completed = streamed.engine.uart_completed();
        streamed.engine.advance_uart_us(0);
        if (completed == streamed.engine.uart_completed())
            streamed.engine.advance_uart_us(us);
    });
    streamed.engine.queue_uart_rx("nn" + patch + "n");
    streamed.engine.advance_uart_us(100000);
    require(streamed.wire == oracle.wire &&
                streamed.engine.store_image().dump() == oracle.engine.store_image().dump() &&
                !streamed.engine.uart_pending() && !streamed.engine.uart_input_pending(),
            "OS batch size corrupted a paced ROM or spent elapsed credit past the blocked CPU");

    Bench sustained(profile);
    sustained.engine.feed("U{i:0,f:9,h:2,p:" + std::to_string(bus) +
                          ",a:28A10100000001E6}U{i:1,f:5,h:2,p:" + std::to_string(bus) +
                          ",a:28A1010000000204}");
    sustained.engine.advance_ms(0);
    sustained.wire.clear();
    sustained.engine.feed("c");
    const size_t reply_size = sustained.wire.size();
    sustained.wire.clear();
    int initial = sustained.engine.observations().at("integral_evaluation_count").integer();
    uint64_t elapsed = 0, fraction = 0;
    sustained.engine.enable_uart(
        [&](uint64_t us) {
            auto completed = sustained.engine.uart_completed();
            sustained.engine.advance_uart_us(0);
            if (completed == sustained.engine.uart_completed())
                sustained.engine.advance_uart_us(us);
        },
        [&](uint64_t us) {
            elapsed += us;
            fraction += us;
            auto ms = fraction / 1000;
            fraction %= 1000;
            sustained.engine.advance_ms(ms);
            if (sustained.engine.uart_waiting() && sustained.wire.size() <= 64 * reply_size - 65 &&
                elapsed / 100000 != (elapsed - us) / 100000)
                require(sustained.engine.observations().at("integral_evaluation_count").integer() ==
                            initial,
                        "ordinary PID work ran inside a nominal TX-stalled receive loop");
        });
    sustained.engine.queue_uart_rx(std::string(64, 'c'));
    sustained.engine.advance_uart_us(5000000);
    auto after = sustained.snap();
    require(elapsed == 5000000 && after.at("controller_ms").integer() == 5000 &&
                after.at("integral_counter").integer() == initial + 1 &&
                after.at("last_evaluation_ms").integer() >= 4000,
            "nominal TX time was counted twice or missed evaluations were replayed");
}
void streamed_transmit_actions(Profile profile) {
    for (char query : {'d', 'h'}) {
        Bench partial(profile);
        partial.engine.feed(std::string(1, query) + "{");
        require(partial.wire == std::string(1, query) + ":[" && partial.engine.reading(),
                "list prefix did not precede query parsing");
        partial.engine.read_timeout();
        require(partial.wire.find("\r\n") == partial.wire.size() - 2,
                "list parsing timeout duplicated or closed the prefix early");
    }
    Bench outputs(profile);
    int heater = profile == Profile::i2c ? 6 : 5;
    int cooler = profile == Profile::i2c ? 5 : 6;
    outputs.engine.feed("U{i:3,f:2,h:1,p:" + std::to_string(heater) + ",x:1}U{i:4,f:3,h:1,p:" +
                        std::to_string(cooler) + ",x:1}U{i:5,f:4,h:1,p:2,x:1}j{mode:t}");
    outputs.wire.clear();
    auto high = [&](int pin) {
        auto pins = outputs.engine.observations().at("pins").array();
        for (const auto& item : pins)
            if (item.array()[0].integer() == pin)
                return item.array()[1].boolean();
        throw std::runtime_error("missing output pin in streamed write case");
    };
    bool blocked = false;
    outputs.engine.enable_uart([&](uint64_t us) {
        if (!blocked) {
            blocked = true;
            require(!high(heater) && high(cooler) && high(2),
                    "later slot writes ran ahead of the first row's blocked output");
        }
        outputs.engine.advance_uart_us(us);
    });
    outputs.engine.feed("n"); // 61 bytes plus the three-byte d prefix leave one free position.
    outputs.engine.feed("d{w:1}");
    outputs.engine.advance_uart_us(100000);
    require(blocked && !high(heater) && !high(cooler) && !high(2),
            "streamed slot writes did not finish their original continuation");

    Bench ambient(profile);
    int bus = profile == Profile::i2c ? 14 : 18;
    ambient.engine.feed("U{i:2,f:6,h:2,p:" + std::to_string(bus) + ",a:28A101000000035A}");
    ambient.wire.clear();
    bool lost = false;
    ambient.engine.enable_uart([&](uint64_t us) {
        if (!lost) {
            lost = true;
            ambient.engine.precondition(Json::Object{{"required_probe_connected", false}});
        }
        ambient.engine.advance_uart_us(us);
    });
    ambient.engine.feed("t");
    ambient.engine.advance_uart_us(100000);
    require(lost && ambient.wire.rfind("T:{", 0) == 0 &&
                ambient.wire.find("D:{\"logType\":\"W\",\"logID\":2") != std::string::npos &&
                ambient.wire.find("RoomTemp") == std::string::npos,
            "ambient read ran ahead of its blocked telemetry prefix");
}
int main(int argc, char** argv) {
    try {
        profile_doors();
        for (auto profile : {Profile::revc, Profile::i2c}) {
            std::string group = argc > 1 ? argv[1] : "all";
            if (group == "all" || group == "mutations")
                menu_mutations(profile);
            if (group == "all" || group == "numbers")
                menu_numbers(profile);
            if (group == "all" || group == "blocking")
                menu_blocking(profile);
            if (group == "all" || group == "checkpoint")
                menu_checkpoint(profile);
            if (group == "all" || group == "clock")
                menu_clock(profile);
            if (group == "all") {
                startup_events(profile);
                queued_resets(profile);
                startup_input_order(profile);
            }
            if (group == "all" || group == "transmit") {
                transmit_limits(profile);
                transmit_scheduling(profile);
                streamed_transmit_actions(profile);
            }
            if (group == "all" || group == "receive")
                receive_limits(profile);
        }
        std::cout << "Source-defined menu mutation, quantization, blocking, clock, persistence and "
                     "continuation checks passed\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
