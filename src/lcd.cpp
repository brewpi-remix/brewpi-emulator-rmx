// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "lcd.hpp"

#include "json.hpp"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <clocale>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <cwchar>
#include <fcntl.h>
#include <filesystem>
#include <langinfo.h>
#include <locale.h>
#include <poll.h>
#include <spawn.h>
#include <stdexcept>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <termios.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

extern char** environ;
namespace rmx {
LcdRows unicode_lcd(const LcdRows& raw, bool& replaced) {
    LcdRows result;
    replaced = false;
    for (size_t r = 0; r < raw.size(); ++r) {
        if (raw[r].size() != 20)
            throw std::runtime_error("LCD shadow must contain twenty-byte rows");
        for (char byte : raw[r]) {
            auto c = static_cast<unsigned char>(byte);
            if (c == 0xb0)
                result[r] += "\xc2\xb0";
            else if (c >= 32 && c <= 126)
                result[r] += char(c);
            else {
                result[r] += '?';
                replaced = true;
            }
        }
    }
    return result;
}
namespace {
using Clock = std::chrono::steady_clock;
using Time = Clock::time_point;
using namespace std::chrono_literals;
struct SignalMask {
    sigset_t old{};
    bool valid;
    SignalMask() {
        sigset_t set;
        sigemptyset(&set);
        sigaddset(&set, SIGTTOU);
        valid = sigprocmask(SIG_BLOCK, &set, &old) == 0;
    }
    ~SignalMask() {
        if (valid)
            sigprocmask(SIG_SETMASK, &old, nullptr);
    }
};
void close_fd(int& fd) {
    if (fd >= 0)
        close(fd);
    fd = -1;
}
bool foreground(int fd) {
    return fd >= 0 && tcgetpgrp(fd) == getpgrp();
}
bool utf8_terminal() {
    locale_t loc = newlocale(LC_CTYPE_MASK, "", nullptr);
    if (!loc)
        return false;
    const char* code = nl_langinfo_l(CODESET, loc);
    bool utf8 = !strcmp(code, "UTF-8") || !strcmp(code, "UTF8");
    locale_t old = uselocale(loc);
    bool ok = old != nullptr && utf8 && wcwidth(L'\u00b0') == 1;
    if (old)
        uselocale(old);
    freelocale(loc);
    return ok;
}
std::filesystem::path executable_path() {
    char buffer[4096];
#ifdef __APPLE__
    uint32_t size = sizeof buffer;
    if (_NSGetExecutablePath(buffer, &size) != 0)
        return {};
#else
    ssize_t size = readlink("/proc/self/exe", buffer, sizeof buffer - 1);
    if (size <= 0 || size >= ssize_t(sizeof buffer - 1))
        return {};
    buffer[size] = 0;
#endif
    return std::filesystem::canonical(buffer);
}
std::string helper_path() {
    auto exe = executable_path();
    auto installed = exe.parent_path() / RMX_LCD_INSTALLED_HELPER;
    if (std::filesystem::is_regular_file(installed))
        return installed.lexically_normal().string();
    // CMake places an original development copy next to its executable. Neither
    // lookup depends on the caller's working directory or embeds a build root.
    return (exe.parent_path() / "lcd-viewer.py").string();
}
std::string python_path() {
    const char* env = getenv("PATH");
    std::string paths = env ? env : "/usr/bin:/bin";
    size_t start = 0;
    while (start <= paths.size()) {
        size_t end = paths.find(':', start);
        std::string directory = paths.substr(start, end - start);
        // Match ordinary PATH behavior, including a caller's explicit '.' entry.
        auto candidate = std::filesystem::absolute(
            std::filesystem::path(directory.empty() ? "." : directory) / "python3");
        if (access(candidate.c_str(), X_OK) == 0 && !std::filesystem::is_directory(candidate))
            return candidate.string();
        if (end == std::string::npos)
            break;
        start = end + 1;
    }
    return {};
}
std::string message(const char* type) {
    return Json(Json::Object{{"version", 1}, {"type", type}}).dump();
}
} // namespace
struct LocalLcd::Impl {
    enum class State { headless, starting, gui, terminal };
    State state = State::headless;
    int tty = -1, channel = -1, diagnostic_fd = -1;
    pid_t child = -1;
    bool terminating = false, killed = false, ansi = false, region = false;
    bool small_reported = false, replacement_reported = false, suspended = false;
    bool shutdown_requested = false;
    unsigned width = 0, height = 0;
    uint64_t sequence = 0;
    LcdRows latest{}, shown{};
    std::string terminal_output;
    size_t written = 0;
    Time next_frame{}, heartbeat{}, progress{}, started{}, terminate_at{}, output_progress{},
        gui_output_progress{};

    void start(const std::string& mode, const LcdRows& rows) {
        if (mode == "off")
            return;
#ifndef __APPLE__
        // Linux permits a new open-file description for a redirected pipe.
        // Never set O_NONBLOCK on the caller's shared stderr description.
        diagnostic_fd = open("/proc/self/fd/2", O_WRONLY | O_NONBLOCK | O_CLOEXEC | O_NOCTTY);
#endif
        tty = open("/dev/tty", O_WRONLY | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
        bool replaced;
        latest = unicode_lcd(rows, replaced);
        replacement_reported = replaced;
        if (replaced)
            note("unsupported LCD cells shown as ?");
        if (mode == "terminal")
            terminal();
        else
            launch();
    }
    // Viewer diagnostics are deliberately best effort and bounded. Do not add a
    // blocking write to a redirected application log or change its status flags.
    void note(const std::string& reason) noexcept {
        std::string safe = reason.substr(0, 400);
        for (char& c : safe)
            if (static_cast<unsigned char>(c) < 32 || static_cast<unsigned char>(c) > 126)
                c = '?';
        std::string line = "LCD: " + safe + "\n";
        if (foreground(tty) && terminal_output.empty()) {
            SignalMask mask;
            if (mask.valid)
                (void)write(tty, line.data(), line.size());
            region = false;
        } else if (tty < 0) {
            if (diagnostic_fd >= 0) {
                (void)write(diagnostic_fd, line.data(), line.size());
                return;
            }
            // A regular log file is not a pipe consumer; only already
            // nonblocking redirected streams are safe for optional diagnostics.
            int flags = fcntl(STDERR_FILENO, F_GETFL);
            struct stat status{};
            if (flags >= 0 && ((flags & O_NONBLOCK) ||
                               (fstat(STDERR_FILENO, &status) == 0 && S_ISREG(status.st_mode))))
                (void)write(STDERR_FILENO, line.data(), line.size());
        }
    }
    void terminal() {
        state = State::headless;
        if (!foreground(tty)) {
            note("no foreground controlling terminal; continuing headless");
            return;
        }
        if (!utf8_terminal()) {
            note("terminal needs UTF-8 and a single-cell degree glyph; continuing headless");
            return;
        }
        const char* term = getenv("TERM");
        std::string name = term ? term : "";
        ansi = name == "xterm" || name.rfind("xterm-", 0) == 0 || name == "screen" ||
               name.rfind("screen-", 0) == 0 || name == "tmux" || name.rfind("tmux-", 0) == 0 ||
               name == "vt100" || name == "vt220";
        state = State::terminal;
        next_frame = Time{};
        shown = {};
    }
    void terminate_child() {
        close_fd(channel);
        if (child > 0 && !terminating) {
            kill(child, SIGTERM);
            terminating = true;
            terminate_at = Clock::now() + 2s;
        }
    }
    void fallback(const std::string& reason) {
        note(reason + "; falling back to terminal");
        terminate_child();
        terminal();
    }
    void launch() {
        std::string helper = helper_path(), python = python_path();
        if (python.empty() || access(helper.c_str(), R_OK) != 0) {
            fallback("Python interpreter or LCD helper unavailable");
            return;
        }
        // Enumerate before allocating spawn resources, so a filesystem failure
        // cannot leak an action list or the child's temporary descriptor.
        std::filesystem::path fd_dir = "/dev/fd";
#ifndef __APPLE__
        fd_dir = "/proc/self/fd";
#endif
        std::vector<int> descriptors;
        for (const auto& entry : std::filesystem::directory_iterator(fd_dir)) {
            std::string name = entry.path().filename().string();
            if (!name.empty() && name.find_first_not_of("0123456789") == std::string::npos) {
                int fd = std::stoi(name);
                if (fd > 3)
                    descriptors.push_back(fd);
            }
        }
        descriptors.reserve(descriptors.size() + 2);
        int pair[2];
        if (socketpair(AF_UNIX, SOCK_DGRAM, 0, pair) != 0) {
            fallback("cannot create private GUI channel");
            return;
        }
        channel = pair[0];
        int send_buffer = 8192;
        if (fcntl(channel, F_SETFD, FD_CLOEXEC) < 0 || fcntl(channel, F_SETFL, O_NONBLOCK) < 0 ||
            setsockopt(channel, SOL_SOCKET, SO_SNDBUF, &send_buffer, sizeof send_buffer) < 0) {
            close(pair[1]);
            fallback("cannot configure nonblocking GUI channel");
            return;
        }
        // Put both temporary descriptors above the child's fixed descriptor 3.
        int child_fd = fcntl(pair[1], F_DUPFD_CLOEXEC, 4);
        close(pair[1]);
        if (child_fd < 0) {
            fallback("cannot prepare GUI descriptor");
            return;
        }
        posix_spawn_file_actions_t actions;
        int err = posix_spawn_file_actions_init(&actions);
        bool initialized = err == 0;
        auto action = [&](int result) {
            if (!err)
                err = result;
        };
        if (initialized) {
            action(posix_spawn_file_actions_addopen(&actions, 0, "/dev/null", O_RDONLY, 0));
            action(posix_spawn_file_actions_addopen(&actions, 1, "/dev/null", O_WRONLY, 0));
            action(posix_spawn_file_actions_addopen(&actions, 2, "/dev/null", O_WRONLY, 0));
            action(posix_spawn_file_actions_adddup2(&actions, child_fd, 3));
            // Close caller-provided non-CLOEXEC descriptors as well as our
            // temporary spawn descriptors; descriptor 3 is now the GUI socket.
            descriptors.push_back(channel);
            descriptors.push_back(child_fd);
            std::sort(descriptors.begin(), descriptors.end());
            descriptors.erase(std::unique(descriptors.begin(), descriptors.end()),
                              descriptors.end());
            for (int fd : descriptors)
                if (fd > 3 && fcntl(fd, F_GETFD) >= 0)
                    action(posix_spawn_file_actions_addclose(&actions, fd));
        }
        char* args[] = {python.data(),          const_cast<char*>("-I"),
                        helper.data(),          const_cast<char*>("--fd"),
                        const_cast<char*>("3"), nullptr};
        if (!err)
            err = posix_spawn(&child, python.c_str(), &actions, nullptr, args, environ);
        if (initialized)
            posix_spawn_file_actions_destroy(&actions);
        close(child_fd);
        if (err) {
            child = -1;
            fallback("GUI spawn failed");
            return;
        }
        state = State::starting;
        started = progress = gui_output_progress = Clock::now();
        heartbeat = next_frame = Time{};
        socklen_t size = sizeof send_buffer;
        if (getsockopt(channel, SOL_SOCKET, SO_SNDBUF, &send_buffer, &size) == 0)
            note("GUI interpreter " + python + "; send buffer " + std::to_string(send_buffer) +
                 " bytes");
    }
    void reap(Time now) {
        if (child <= 0)
            return;
        int status = 0;
        pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child || (result < 0 && errno == ECHILD)) {
            child = -1;
            // A deliberate window close is distinct from a crash or lost GUI.
            // Exit 10 also covers close intent racing with process reaping.
            if (result > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 10) {
                shutdown_requested = true;
                state = State::headless;
                close_fd(channel);
            }
            if (state == State::starting || state == State::gui)
                fallback("graphical window closed or viewer exited");
        } else if (terminating && !killed && now >= terminate_at) {
            kill(child, SIGKILL);
            killed = true;
        }
    }
    bool send_message(const std::string& bytes) {
        ssize_t count = send(channel, bytes.data(), bytes.size(), 0);
        if (count == ssize_t(bytes.size())) {
            gui_output_progress = Clock::now();
            return true;
        }
        if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
            return false;
        throw std::runtime_error("GUI channel write failed");
    }
    void gui_tick(Time now) {
        for (int i = 0; i < 6; ++i) {
            char data[4097];
            ssize_t count = recv(channel, data, sizeof data, 0);
            if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
                break;
            if (count <= 0 || count > 4096)
                throw std::runtime_error("invalid GUI message size");
            Json j = Json::parse(std::string(data, size_t(count)));
            if (j.object().size() != 2 || j.at("version").number() != 1)
                throw std::runtime_error("invalid GUI message schema");
            std::string type = j.at("type").string();
            if (type == "close") {
                shutdown_requested = true;
                state = State::headless;
                close_fd(channel);
                return;
            } else if (type == "ready" && state == State::starting) {
                state = State::gui;
                progress = now;
            } else if (type == "progress" && state == State::gui)
                progress = now;
            else
                throw std::runtime_error("GUI error or unexpected lifecycle message");
            if (i == 5)
                throw std::runtime_error("excessive GUI messages");
        }
        if (now - (state == State::starting ? started : progress) >= 5s)
            throw std::runtime_error("GUI readiness/progress timed out");
        if (now - gui_output_progress >= 5s)
            throw std::runtime_error("GUI output stalled");
        if (now >= heartbeat) {
            send_message(message("heartbeat"));
            heartbeat = now + 1s;
        }
        if (state == State::gui && now >= next_frame && latest != shown) {
            next_frame = now + 100ms;
            Json::Array rows;
            for (const auto& row : latest)
                rows.emplace_back(row);
            auto bytes = Json(Json::Object{{"version", 1},
                                           {"type", "frame"},
                                           {"sequence", double(++sequence)},
                                           {"rows", rows}})
                             .dump();
            if (bytes.size() > 4096)
                throw std::runtime_error("oversized GUI frame");
            if (send_message(bytes)) {
                shown = latest;
                next_frame = now + 100ms;
            }
        }
    }
    void terminal_tick(Time now) {
        if (!foreground(tty)) {
            suspended = true;
            return;
        }
        winsize size{};
        SignalMask mask;
        if (!mask.valid)
            throw std::runtime_error("cannot guard terminal operation");
        if (ioctl(tty, TIOCGWINSZ, &size) != 0 || size.ws_col == 0 || size.ws_row == 0)
            throw std::runtime_error("terminal dimensions unavailable");
        if (width != size.ws_col || height != size.ws_row || suspended) {
            width = size.ws_col;
            height = size.ws_row;
            terminal_output.clear();
            written = 0;
            region = false;
            shown = {};
            suspended = false;
            next_frame = Time{};
        }
        if (width < 23 || height < 7) {
            if (!small_reported) {
                note("terminal needs at least 23 columns and 7 rows; display suspended");
                small_reported = true;
            }
            return;
        }
        small_reported = false;
        if (terminal_output.empty() && latest != shown && now >= next_frame) {
            std::string frame;
            if (ansi && region)
                frame = "\r\x1b[6A";
            else
                frame = "\r\n";
            if (!ansi) {
                char stamp[40];
                std::time_t t = std::time(nullptr);
                std::tm tm{};
                gmtime_r(&t, &tm);
                std::strftime(stamp, sizeof stamp, "%Y-%m-%d %H:%M:%SZ\r\n", &tm);
                frame += stamp;
            }
            auto line = [&](const std::string& text) {
                frame += "\r";
                if (ansi)
                    frame += "\x1b[2K";
                frame += text + "\r\n";
            };
            line("+--------------------+");
            for (const auto& row : latest)
                line("|" + row + "|");
            line("+--------------------+");
            terminal_output = std::move(frame);
            written = 0;
            output_progress = now;
            shown = latest;
            next_frame = now + (ansi ? 100ms : 1000ms);
            region = true;
        }
        if (!terminal_output.empty()) {
            ssize_t n =
                write(tty, terminal_output.data() + written, terminal_output.size() - written);
            if (n > 0) {
                written += size_t(n);
                output_progress = now;
                if (written == terminal_output.size()) {
                    terminal_output.clear();
                    written = 0;
                }
            } else if (n < 0 && errno == EIO) {
                suspended = true;
            } else if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)
                throw std::runtime_error("terminal write failed");
            if (now - output_progress >= 5s)
                throw std::runtime_error("terminal output stalled");
        }
    }
    void tick(const LcdRows& raw) {
        Time now = Clock::now();
        if (state == State::headless) {
            reap(now);
            return;
        }
        bool replaced;
        latest = unicode_lcd(raw, replaced);
        if (replaced && !replacement_reported) {
            replacement_reported = true;
            note("unsupported LCD cells shown as ?");
        }
        try {
            if (state == State::starting || state == State::gui)
                gui_tick(now);
            // Consume queued close intent before observing child exit. The
            // reserved status still covers backpressure or a failed send.
            reap(now);
            if (state == State::terminal)
                terminal_tick(now);
        } catch (const std::exception& e) {
            if (state == State::starting || state == State::gui)
                fallback(e.what());
            else {
                note(std::string(e.what()) + "; continuing headless");
                state = State::headless;
                terminal_output.clear();
            }
        }
    }
    ~Impl() {
        state = State::headless;
        terminate_child();
        // Engine checkpoint decisions have already completed before this RAII
        // cleanup. Poll in short slices; never advance simulated time here.
        Time deadline = Clock::now() + 2s;
        while (child > 0 && Clock::now() < deadline) {
            reap(Clock::now());
            if (child > 0)
                poll(nullptr, 0, 10);
        }
        if (child > 0) {
            kill(child, SIGKILL);
            while (waitpid(child, nullptr, 0) < 0 && errno == EINTR) {
            }
        }
        if (foreground(tty)) {
            SignalMask mask;
            if (mask.valid)
                (void)write(tty, "\r\n", 2);
        }
        close_fd(tty);
        close_fd(diagnostic_fd);
    }
};
LocalLcd::LocalLcd(const std::string& mode, const LcdRows& initial) {
    impl = std::make_unique<Impl>();
    try {
        impl->start(mode, initial);
    } catch (const std::exception& e) {
        impl->fallback(e.what());
    }
    tick(initial);
}
LocalLcd::~LocalLcd() = default;
bool LocalLcd::shutdown_requested() const noexcept {
    return impl && impl->shutdown_requested;
}
void LocalLcd::tick(const LcdRows& rows) noexcept {
    if (!impl)
        return;
    try {
        impl->tick(rows);
    } catch (...) {
        impl->note("display unavailable; continuing headless");
        impl->terminate_child();
        impl->state = Impl::State::headless;
    }
}
} // namespace rmx
