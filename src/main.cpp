// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "engine.hpp"
#include "lcd.hpp"
#include "storage.hpp"

#include <cerrno>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdlib>
#include <cstring>
#ifdef _WIN32
#include "windows_host.hpp"
#include "windows_ready.hpp"
#include "windows_serial.hpp"

#include <atomic>
#else
#include <fcntl.h>
#endif
#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <thread>
#ifndef _WIN32
#include <poll.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <termios.h>
#include <unistd.h>
#endif

#ifndef RMX_VERSION
#define RMX_VERSION "development"
#endif

namespace {
#ifdef _WIN32
std::atomic<bool> stopping{false};
#else
volatile std::sig_atomic_t stopping = 0;
#endif
#ifndef _WIN32
volatile std::sig_atomic_t suspending = 0;
void suspend_request(int) {
    suspending = 1;
}
#endif
void stop(int) {
    stopping = 1;
}
bool same_file(const std::filesystem::path& a, const std::filesystem::path& b) {
    if (std::filesystem::weakly_canonical(a) == std::filesystem::weakly_canonical(b))
        return true;
    std::error_code ec;
    return std::filesystem::equivalent(a, b, ec) && !ec;
}
#ifndef _WIN32
class Pty {
    std::filesystem::path link;
    int master = -1, slave = -1, owner = -1;
    std::string target;
    bool published = false;
    struct stat link_identity{};

  public:
    explicit Pty(std::filesystem::path path) : link(std::move(path)) {
        try {
            if (!link.parent_path().empty())
                std::filesystem::create_directories(link.parent_path());
            owner = ::open((link.string() + ".lock").c_str(),
                           O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
            if (owner < 0 || ::flock(owner, LOCK_EX | LOCK_NB) < 0)
                throw std::runtime_error("serial path already owned or cannot lock");
            auto status = std::filesystem::symlink_status(link);
            if (status.type() != std::filesystem::file_type::not_found)
                throw std::runtime_error("serial path exists; refusing to replace it");
            master = ::posix_openpt(O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
            if (master < 0 || ::grantpt(master) < 0 || ::unlockpt(master) < 0)
                throw std::runtime_error("cannot allocate PTY");
            char* name = ::ptsname(master);
            if (!name)
                throw std::runtime_error("cannot resolve PTY");
            target = name;
            slave = ::open(target.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
            if (slave < 0)
                throw std::runtime_error("cannot open PTY slave");
            termios tty{};
            if (::tcgetattr(slave, &tty) < 0)
                throw std::runtime_error("cannot read PTY attributes");
            ::cfmakeraw(&tty);
            ::cfsetispeed(&tty, B57600);
            ::cfsetospeed(&tty, B57600);
            tty.c_cflag |= CLOCAL | CREAD;
            if (::tcsetattr(slave, TCSANOW, &tty) < 0)
                throw std::runtime_error("cannot configure PTY");
            // Keeping our slave descriptor open preserves the master across client closes.
            std::filesystem::create_symlink(target, link);
            published = true;
            if (::lstat(link.c_str(), &link_identity) < 0)
                throw std::runtime_error("cannot inspect owned link");
        } catch (...) {
            cleanup();
            throw;
        }
    }
    void cleanup() noexcept {
        if (published) {
            std::error_code ec;
            auto actual = std::filesystem::read_symlink(link, ec);
            struct stat current{};
            if (!ec && actual == target && ::lstat(link.c_str(), &current) == 0 &&
                current.st_ino == link_identity.st_ino && current.st_dev == link_identity.st_dev)
                std::filesystem::remove(link, ec);
            published = false;
        }
        if (slave >= 0) {
            ::close(slave);
            slave = -1;
        }
        if (master >= 0) {
            ::close(master);
            master = -1;
        }
        if (owner >= 0) {
            ::close(owner);
            owner = -1;
        }
    }
    ~Pty() {
        cleanup();
    }
    int fd() const {
        return master;
    }
    const std::string& slave_path() const {
        return target;
    }
};
#endif
#ifdef _WIN32
BOOL WINAPI console_stop(DWORD reason) {
    if (reason == CTRL_C_EVENT || reason == CTRL_BREAK_EVENT) {
        stopping = 1;
        return TRUE;
    }
    return FALSE;
}
#endif
} // namespace
int application_main(int argc, char** argv) {
    try {
#ifdef _WIN32
        std::string serial, store, pair_path;
#else
        std::string serial = "/run/brewpi-emulator/chamber1/serial",
                    store = "/var/lib/brewpi-emulator/chamber1/controller.json";
#endif
        std::string scenario_path, resume_path, checkpoint_path, lcd_mode = "off";
        rmx::Profile profile = rmx::Profile::revc;
        double speed = 1, pacing_fraction = 0;
        bool speed_supplied = false, lcd_keep_on = false;
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--help") {
                std::cout << "Usage: brewpi-emulator-rmx [--serial PATH] [--state PATH] "
                             "[--scenario PATH] [--profile revc|i2c]\n"
                             "       [--speed FACTOR] [--resume PATH] [--checkpoint PATH]\n"
                             "       [--lcd off|terminal|gui|auto] [--lcd-keep-on]\n"
#ifdef _WIN32
                             "Windows requires --serial COMn --serial-pair PATH --state PATH.\n"
#endif
                             "LCD gui/auto falls back to a Unicode terminal, then headless.\n"
                             "Speed 1 is real time; 0 pauses simulated time. Checkpoints save on "
                             "clean shutdown.\n";
                return 0;
            }
            if (arg == "--version") {
                std::cout << "brewpi-emulator-rmx " RMX_VERSION "\n";
                return 0;
            }
            if (arg == "--lcd-keep-on") {
                lcd_keep_on = true;
                continue;
            }
            if (i + 1 == argc)
                throw std::runtime_error("incomplete option: " + arg);
            std::string val = argv[++i];
            if (arg == "--serial")
                serial = val;
#ifdef _WIN32
            else if (arg == "--serial-pair")
                pair_path = val;
#endif
            else if (arg == "--state")
                store = val;
            else if (arg == "--profile")
                profile = rmx::parse_profile(val);
            else if (arg == "--scenario")
                scenario_path = val;
            else if (arg == "--resume")
                resume_path = val;
            else if (arg == "--checkpoint")
                checkpoint_path = val;
            else if (arg == "--lcd") {
                if (val != "off" && val != "terminal" && val != "gui" && val != "auto")
                    throw std::runtime_error("invalid LCD mode: " + val);
                lcd_mode = val;
            } else if (arg == "--speed") {
                size_t used = 0;
                speed = std::stod(val, &used);
                if (used != val.size() || !std::isfinite(speed) || speed < 0 || speed > 1000)
                    throw std::runtime_error("invalid speed factor");
                speed_supplied = true;
            } else
                throw std::runtime_error("unknown option: " + arg);
        }
#ifdef _WIN32
        if (serial.empty() || store.empty() || pair_path.empty())
            throw std::runtime_error(
                "Windows requires --serial COMn, --serial-pair PATH, and --state PATH");
#endif
#ifdef _WIN32
        for (const auto& output : {store, checkpoint_path, store + ".ready"}) {
            if (!output.empty() &&
                (same_file(std::filesystem::u8path(pair_path), std::filesystem::u8path(output)) ||
                 same_file(std::filesystem::u8path(pair_path),
                           std::filesystem::u8path(output + ".lock"))))
                throw std::runtime_error("serial pair record overlaps a runtime output path");
        }
#endif
        if (!resume_path.empty() && !scenario_path.empty())
            throw std::runtime_error("scenario override is incompatible with checkpoint resume");
        if (!scenario_path.empty()) {
            std::vector<std::string> outputs{store, checkpoint_path};
#ifdef _WIN32
            outputs.push_back(store + ".ready");
#else
            outputs.push_back(serial);
#endif
            for (const auto& writable : outputs) {
                if (!writable.empty() && (same_file(std::filesystem::u8path(scenario_path),
                                                    std::filesystem::u8path(writable)) ||
                                          same_file(std::filesystem::u8path(scenario_path),
                                                    std::filesystem::u8path(writable + ".lock"))))
                    throw std::runtime_error("scenario input overlaps a runtime output path");
            }
        }
#ifdef _WIN32
        if (!resume_path.empty() && (same_file(std::filesystem::u8path(resume_path),
                                               std::filesystem::u8path(store + ".ready")) ||
                                     same_file(std::filesystem::u8path(resume_path),
                                               std::filesystem::u8path(store + ".ready.lock"))))
            throw std::runtime_error("checkpoint input overlaps readiness publication");
#endif
        rmx::Storage storage(std::filesystem::u8path(store));
        std::unique_ptr<rmx::Storage> checkpoint_file;
        if (!checkpoint_path.empty())
            checkpoint_file =
                std::make_unique<rmx::Storage>(std::filesystem::u8path(checkpoint_path));
        std::string pending;
        rmx::Engine engine([&](const std::string& s) { pending += s; }, profile);
        auto saved = storage.load();
        if (!resume_path.empty()) {
            std::optional<rmx::Json> snapshot;
            if (resume_path == checkpoint_path)
                snapshot = checkpoint_file->load();
            else {
                snapshot = rmx::Storage::read(std::filesystem::u8path(resume_path));
            }
            if (!snapshot || snapshot->at("format").string() != "brewpi-emulator-checkpoint-v1")
                throw std::runtime_error("missing or incompatible checkpoint");
            engine.restore_checkpoint(snapshot->at("engine"));
            if (saved) {
                rmx::Engine current([](const std::string&) {}, profile);
                current.load_store(*saved);
                if (current.store_image().dump() != engine.store_image().dump())
                    throw std::runtime_error("checkpoint does not match saved controller store");
            }

            if (!speed_supplied)
                speed = snapshot->at("speed").number();
            if (!std::isfinite(speed) || speed < 0 || speed > 1000)
                throw std::runtime_error("invalid checkpoint speed");
            pacing_fraction = snapshot->at("pacing_fraction_ms").number();
            if (pacing_fraction < 0 || pacing_fraction >= 1)
                throw std::runtime_error("invalid checkpoint pacing fraction");
            if (!saved)
                storage.write(engine.store_image());
        } else {
            if (!scenario_path.empty()) {
                auto config = rmx::Storage::read(std::filesystem::u8path(scenario_path));
                if (!config)
                    throw std::runtime_error("missing scenario file");
                engine.configure_plant(*config);
                if (!speed_supplied && config->has("speed_factor"))
                    speed = config->at("speed_factor").number();
            }
            if (saved)
                engine.load_store(*saved);
        }
        engine.on_save([&](const rmx::Json& image) { storage.write(image); });
#ifdef _WIN32
        auto pair = rmx::Storage::read(std::filesystem::u8path(pair_path));
        if (!pair)
            throw std::runtime_error("missing serial pair record");
        rmx::WindowsSerial port(*pair, serial);
#else
        Pty pty(serial);
#endif
        if (resume_path.empty())
            engine.boot(true);
        std::signal(SIGINT, stop);
        std::signal(SIGTERM, stop);
#ifdef _WIN32
        if (!SetConsoleCtrlHandler(console_stop, TRUE))
            throw rmx::win::error("install console interruption handler");
        std::cerr << "serial=" << serial << " peer=" << port.peer() << "\n";
#else
        std::signal(SIGPIPE, SIG_IGN);
        if (lcd_mode != "off")
            std::signal(SIGTSTP, suspend_request);
        std::cerr << "serial=" << serial << " slave=" << pty.slave_path() << "\n";
#endif
        rmx::LocalLcd lcd(lcd_mode, engine.lcd_rows(), &engine, lcd_keep_on);
#ifdef _WIN32
        rmx::WindowsReady readiness(std::filesystem::u8path(store), serial);
#endif
        using Clock = std::chrono::steady_clock;
        auto deadline = Clock::now() + std::chrono::seconds(1);
        size_t sent = 0;
        auto wall_anchor = Clock::now();
        auto dispatch_epoch = engine.dispatch_epoch();
        double uart_fraction_us = 0;
        bool clock_allowed = true;
        auto controller_fraction_us = uint64_t(std::floor(pacing_fraction * 1000));
        double legacy_sub_us = pacing_fraction * 1000 - double(controller_fraction_us);
        auto advance_controller = [&](uint64_t us) {
            bool starting_up = engine.starting_up();
            if (speed > 0 || starting_up) {
                auto total_fraction_us = controller_fraction_us + us % 1000;
                auto simulated = us / 1000 + total_fraction_us / 1000;
                controller_fraction_us = total_fraction_us % 1000;
                pacing_fraction = (double(controller_fraction_us) + legacy_sub_us) / 1000;
                engine.advance_ms(simulated, clock_allowed && pending.size() - sent < 65536,
                                  speed == 0);
                if (starting_up && !engine.starting_up() && speed == 0) {
                    controller_fraction_us = 0;
                    legacy_sub_us = pacing_fraction = 0;
                }
            }
        };
        auto advance_wall = [&](bool controller_allowed = true) {
            auto wall_now = Clock::now();
            double elapsed =
                std::chrono::duration<double, std::milli>(wall_now - wall_anchor).count();
            wall_anchor = wall_now;
            uart_fraction_us += elapsed * 1000 * (speed > 0 ? speed : 1);
            auto uart_elapsed = uint64_t(std::floor(uart_fraction_us));
            uart_fraction_us -= double(uart_elapsed);
            bool previous = clock_allowed;
            clock_allowed = controller_allowed;
            engine.advance_uart_us(uart_elapsed, controller_allowed);
            clock_allowed = previous;
            if (dispatch_epoch != engine.dispatch_epoch()) {
                dispatch_epoch = engine.dispatch_epoch();
                deadline = Clock::now() + std::chrono::seconds(1);
            }
        };
        auto pump_serial = [&](int wait, bool receive) {
            auto accepting = [&]() {
                return receive && engine.uart_caught_up() && engine.uart_input_space() >= 1024 &&
                       pending.size() - sent < 65536;
            };
#ifndef _WIN32
            short events = accepting() ? POLLIN : 0;
            if (sent < pending.size())
                events |= POLLOUT;
            pollfd f{pty.fd(), events, 0};
#endif
#ifdef _WIN32
            unsigned ready =
                port.wait(accepting(), sent < pending.size(), static_cast<unsigned>(wait));
            advance_wall(receive);
            if (ready & rmx::WindowsSerial::writable) {
                auto w = port.write(pending.data() + sent, pending.size() - sent);
                sent += w;
                if (sent == pending.size()) {
                    pending.clear();
                    sent = 0;
                } else if (sent > 65536) {
                    pending.erase(0, sent);
                    sent = 0;
                }
            }
            if ((ready & rmx::WindowsSerial::readable) && accepting()) {
                char buf[1024];
                auto r = port.read(buf, sizeof buf);
                if (r) {
                    engine.queue_uart_rx(std::string(buf, r));
                    deadline = Clock::now() + std::chrono::seconds(1);
                }
            }
#else
            int n = ::poll(&f, 1, wait);
            if (n < 0) {
                if (errno == EINTR)
                    return;
                throw std::runtime_error("PTY poll failed");
            }
            advance_wall(receive);
            if (f.revents & (POLLERR | POLLNVAL | POLLHUP))
                throw std::runtime_error("PTY disconnected unexpectedly");
            if (f.revents & POLLOUT) {
                ssize_t w = ::write(pty.fd(), pending.data() + sent, pending.size() - sent);
                if (w > 0) {
                    sent += size_t(w);
                    if (sent == pending.size()) {
                        pending.clear();
                        sent = 0;
                    } else if (sent > 65536) {
                        pending.erase(0, sent);
                        sent = 0;
                    }
                } else if (w < 0 && errno != EAGAIN && errno != EINTR)
                    throw std::runtime_error("PTY write failed");
            }
            if ((f.revents & POLLIN) && accepting()) {
                char buf[1024];
                ssize_t r = ::read(pty.fd(), buf, std::min(sizeof buf, engine.uart_input_space()));
                if (r > 0) {
                    engine.queue_uart_rx(std::string(buf, size_t(r)));
                    deadline = Clock::now() + std::chrono::seconds(1);
                } else if (r < 0 && errno != EAGAIN && errno != EINTR)
                    throw std::runtime_error("PTY read failed");
            }
#endif
        };
        bool presenting = false;
        auto next_wait_lcd = Clock::now();
        auto tick_lcd = [&](bool writable) {
            if (presenting)
                return;
            presenting = true;
            try {
                // Headless ticks still service logical inputs, but need no row copies.
                if (lcd_mode == "off")
                    lcd.tick({}, writable);
                else
                    lcd.tick(engine.lcd_rows(), writable);
            } catch (...) {
                presenting = false;
                throw;
            }
            presenting = false;
            next_wait_lcd = Clock::now() + std::chrono::milliseconds(100);
        };
        engine.enable_uart(
            [&](uint64_t) {
                auto completed = engine.uart_completed();
                while (completed == engine.uart_completed()) {
                    if (Clock::now() >= next_wait_lcd)
                        tick_lcd(false);
                    if (lcd.shutdown_requested())
                        stopping = 1;
                    if (stopping)
                        throw std::runtime_error("interrupted UART transmit continuation");
                    engine.advance_uart_us(0);
                    if (completed != engine.uart_completed())
                        break;
                    pump_serial(0, true);
                    if (completed != engine.uart_completed())
                        break;
                    // Clamp before conversion: very small positive pacing must remain
                    // interruptible.
                    double delay =
                        std::ceil(double(engine.uart_next_us()) / (speed > 0 ? speed : 1));
                    auto wall_us = uint64_t(std::max(1.0, std::min(1000.0, delay)));
                    std::this_thread::sleep_for(std::chrono::microseconds(wall_us));
                }
            },
            advance_controller);
        while (!stopping) {
#ifdef _WIN32
            readiness.tick();
#endif
#ifndef _WIN32
            if (suspending) {
                lcd.suspend();
                suspending = 0;
                // SIGSTOP guarantees a stop even for an orphaned process group.
                raise(SIGSTOP);
            }
#endif
            advance_wall();
            if (engine.restarting())
                engine.restart(true);
            // Stop accepting input while the reader is backpressured; retain every output byte.
            int wait =
                speed > 0 ? int(std::max(1.0, std::min(100.0, std::ceil(100 / speed)))) : 100;
            if (engine.reading())
                wait = std::max(
                    0, std::min(100, int(std::chrono::duration_cast<std::chrono::milliseconds>(
                                             deadline - Clock::now())
                                             .count())));
            if (engine.uart_pending() || engine.uart_input_pending()) {
                double next =
                    std::ceil(double(engine.uart_next_us()) / (1000 * (speed > 0 ? speed : 1)));
                wait = std::min(wait, int(std::max(1.0, std::min(100.0, next))));
            }
            pump_serial(wait, true);
            if (engine.reading() && Clock::now() >= deadline) {
                engine.read_timeout();
                deadline = Clock::now() + std::chrono::seconds(1);
            }
            tick_lcd(pending.size() - sent < 65536);
            if (lcd.shutdown_requested())
                stopping = 1;
        }
        // Administrative shutdown drains already accepted TX without executing more commands.
        auto drain_deadline = Clock::now() + std::chrono::seconds(2);
        while (engine.uart_pending() || engine.uart_input_pending() || sent != pending.size()
#ifdef _WIN32
               || !port.drained()
#endif
        ) {
            if (Clock::now() >= drain_deadline)
                throw std::runtime_error("shutdown could not drain serial output");
            pump_serial(1, false);
        }
        if (checkpoint_file) {
            if (sent != pending.size()
#ifdef _WIN32
                || !port.drained()
#endif
            )
                throw std::runtime_error("checkpoint requires drained serial output");
            checkpoint_file->write(rmx::Json::Object{{"format", "brewpi-emulator-checkpoint-v1"},
                                                     {"engine", engine.checkpoint()},
                                                     {"speed", speed},
                                                     {"pacing_fraction_ms", pacing_fraction}});
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "brewpi-emulator-rmx: " << e.what() << '\n';
        return 1;
    }
}

#ifdef _WIN32
int wmain(int argc, wchar_t** argv) {
    try {
        std::vector<std::string> arguments;
        for (int i = 0; i < argc; ++i)
            arguments.push_back(rmx::win::utf8(argv[i]));
        std::vector<char*> pointers;
        for (auto& argument : arguments)
            pointers.push_back(argument.data());
        return application_main(argc, pointers.data());
    } catch (const std::exception& e) {
        std::cerr << "brewpi-emulator-rmx: " << e.what() << '\n';
        return 1;
    }
}
#else
int main(int argc, char** argv) {
    return application_main(argc, argv);
}
#endif
