// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "lcd.hpp"

#include "engine.hpp"
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
#ifdef _WIN32
#include "windows_channel.hpp"
#include "windows_console.hpp"
#include "windows_host.hpp"
#else
#include <fcntl.h>
#endif
#include <filesystem>
#ifndef _WIN32
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
#endif
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#ifndef _WIN32
extern char** environ;
#endif
namespace rmx {
LcdRows unicode_lcd(const LcdRows& raw, bool& replaced) {
    LcdRows result;
    replaced = false;
    for (size_t r = 0; r < raw.size(); ++r) {
        if (raw[r].size() != 20)
            throw std::runtime_error("LCD shadow must contain twenty-byte rows");
        for (char byte : raw[r]) {
            auto c = static_cast<unsigned char>(byte);
            if (c == 0xb0 || c == 0xdf)
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
#ifndef _WIN32
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
#endif
std::filesystem::path executable_path() {
#ifndef _WIN32
    char buffer[4096];
#endif
#ifdef _WIN32
    wchar_t path[32768];
    DWORD size = GetModuleFileNameW(nullptr, path, 32768);
    if (!size || size >= 32768)
        return {};
    return std::filesystem::canonical(path);
#elif defined(__APPLE__)
    uint32_t size = sizeof buffer;
    if (_NSGetExecutablePath(buffer, &size) != 0)
        return {};
#else
    ssize_t size = readlink("/proc/self/exe", buffer, sizeof buffer - 1);
    if (size <= 0 || size >= ssize_t(sizeof buffer - 1))
        return {};
    buffer[size] = 0;
#endif
#ifndef _WIN32
    return std::filesystem::canonical(buffer);
#endif
}
std::string helper_path() {
    auto exe = executable_path();
    auto installed = exe.parent_path() / RMX_LCD_INSTALLED_HELPER;
    if (std::filesystem::is_regular_file(installed))
        return installed.lexically_normal().u8string();
    // CMake places an original development copy next to its executable. Neither
    // lookup depends on the caller's working directory or embeds a build root.
    return (exe.parent_path() / "lcd-viewer.py").u8string();
}
std::string python_path() {
#ifdef _WIN32
    DWORD length = GetEnvironmentVariableW(L"PATH", nullptr, 0);
    if (!length || length > 32767)
        return {};
    std::wstring paths(length, L'\0');
    DWORD copied = GetEnvironmentVariableW(L"PATH", paths.data(), length);
    if (!copied || copied >= length)
        return {};
    paths.resize(copied);
    size_t start = 0;
    while (start <= paths.size()) {
        size_t end = paths.find(L';', start);
        auto directory = paths.substr(start, end - start);
        if (directory.size() >= 2 && directory.front() == L'"' && directory.back() == L'"')
            directory = directory.substr(1, directory.size() - 2);
        auto candidate = std::filesystem::absolute(
            std::filesystem::path(directory.empty() ? L"." : directory) / L"python.exe");
        if (std::filesystem::is_regular_file(candidate))
            return candidate.u8string();
        if (end == std::wstring::npos)
            break;
        start = end + 1;
    }
    return {};
#else
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
#endif
}
std::string message(const char* type) {
    return Json(Json::Object{{"version", 2}, {"type", type}}).dump();
}
} // namespace
struct LocalLcd::Impl {
    enum class State { headless, starting, gui, settling, terminal };
    State state = State::headless;
#ifdef _WIN32
    std::unique_ptr<WindowsConsole> console;
    std::unique_ptr<WindowsChannel> pipe;
    win::Handle process;
    int64_t child = -1;
#else
    int tty = -1, channel = -1, diagnostic_fd = -1;
    pid_t child = -1;
#endif
    bool terminating = false, term_sent = false, killed = false, ansi = false, region = false;
    bool small_reported = false, replacement_reported = false, suspended = false;
    bool shutdown_requested = false;
    unsigned width = 0, height = 0;
    uint64_t sequence = 0;
    std::exception_ptr controller_failure;
    Engine* engine = nullptr;
    bool writable = true, keep_on = false, dim = false, shown_dim = false;
    bool raw_input = false, dropping = false, last_cr = false, discard_input = false;
#ifndef _WIN32
    termios saved_tty{};
#endif
    std::string input, status = "cw ccw press help", shown_status;
    Time acknowledged{}, activity = Clock::now();
    std::string pending_failure;
    Time settle_at{};
    std::string session = std::to_string(Clock::now().time_since_epoch().count());
    uint64_t last_action = 0, shown_epoch = 0;
    bool shown_door = false;
    EquipmentStates shown_equipment{{-2, -2, -2, -2}};
    unsigned terminal_lines = 6;
    LcdRows latest{}, shown{};
    uint64_t wall_ms() const {
        return uint64_t(
            std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch())
                .count());
    }
    void restore_input() noexcept {
#ifdef _WIN32
        if (console)
            console->restore();
        raw_input = false;
        discard_input = true;
#else
        if (raw_input) {
            SignalMask mask;
            if (mask.valid) {
                int result;
                do {
                    result = tcsetattr(tty, TCSANOW, &saved_tty);
                } while (result < 0 && errno == EINTR);
                if (result == 0)
                    raw_input = false;
            }
            discard_input = true;
        }
#endif
    }
    void cancel() {
        if (engine)
            engine->local_cancel();
        input.clear();
        dropping = false;
        last_cr = false;
    }
    void action(const std::string& command) {
        activity = Clock::now();
        try {
            status = engine ? engine->local_action(command, wall_ms(), writable) : "Read-only LCD";
        } catch (...) {
            controller_failure = std::current_exception();
            throw;
        }
        acknowledged = Clock::now() + 750ms;
    }
    void terminal_input(Time now) {
#ifdef _WIN32
        console->enable();
        raw_input = true;
        auto bytes = console->input(discard_input);
        discard_input = false;
        auto n = bytes.size();
        const char* buffer = bytes.data();
#else
        if (!raw_input) {
            if (tcgetattr(tty, &saved_tty) != 0)
                throw std::runtime_error("cannot read terminal modes");
            auto edited = saved_tty;
            edited.c_lflag &= tcflag_t(~(ICANON | ECHO | ECHONL));
            edited.c_iflag &= tcflag_t(~(ICRNL | INLCR | IGNCR | IXON));
            edited.c_cc[VMIN] = 0;
            edited.c_cc[VTIME] = 0;
            if (tcsetattr(tty, TCSANOW, &edited) != 0)
                throw std::runtime_error("cannot enable command input");
            raw_input = true;
            // Only discard input after ownership returns to this foreground job.
            // Never drain a background shell's terminal input.
            if (discard_input && tcflush(tty, TCIFLUSH) != 0)
                throw std::runtime_error("cannot discard suspended control input");
            discard_input = false;
        }
        char buffer[256];
        ssize_t n = read(tty, buffer, sizeof buffer);
        if (n < 0 && errno != EAGAIN && errno != EINTR)
            throw std::runtime_error("terminal input failed");
#endif
        for (decltype(n) i = 0; i < n; ++i) {
            unsigned char c = static_cast<unsigned char>(buffer[i]);
            activity = now;
            if (c == '\n' && last_cr) {
                last_cr = false;
                continue;
            }
            last_cr = c == '\r';
            if (c == '\r' || c == '\n') {
                if (dropping) {
                    status = "Line rejected";
                    acknowledged = now + 750ms;
                } else if (!input.empty())
                    action(input);
                input.clear();
                dropping = false;
            } else if (!dropping) {
                acknowledged = Time{};
                if (c == 127 || c == 8) {
                    if (!input.empty())
                        input.pop_back();
                } else if (c == 21)
                    input.clear();
                else if (c >= 32 && c <= 126 && input.size() < 80)
                    input += char(c);
                else {
                    dropping = true;
                    input.clear();
                }
            }
        }
    }
    std::string terminal_output;
    size_t written = 0;
    Time next_frame{}, heartbeat{}, progress{}, started{}, terminate_at{}, output_progress{},
        gui_output_progress{};

    void start(const std::string& mode, const LcdRows& rows) {
        if (mode == "off")
            return;
#if !defined(__APPLE__) && !defined(_WIN32)
        // Linux permits a new open-file description for a redirected pipe.
        // Never set O_NONBLOCK on the caller's shared stderr description.
        diagnostic_fd = open("/proc/self/fd/2", O_WRONLY | O_NONBLOCK | O_CLOEXEC | O_NOCTTY);
#endif
#ifdef _WIN32
        try {
            console = std::make_unique<WindowsConsole>();
        } catch (const std::exception&) {
            // A GUI or headless session does not require a console.
        }
#else
        tty = open("/dev/tty", O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
#endif
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
#ifdef _WIN32
        try {
            if (console && terminal_output.empty() && console->output("LCD: " + safe + "\r\n"))
                region = false;
        } catch (const std::exception&) {
            // Optional diagnostics use only the bounded console worker.
        }
#else
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
#endif
    }

    void terminal() {
        discard_input = true;
        state = State::headless;
#ifdef _WIN32
        if (!console)
            return;
        try {
            console->enable();
        } catch (const std::exception&) {
            console->restore();
            console.reset();
            return;
        }
        ansi = true;
#else
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
#endif
        if (!ansi && engine)
            note("terminal controls require ANSI cursor rewriting; read-only display");
        state = State::terminal;
        next_frame = Time{};
        shown = {};
    }
    void close_channel() {
#ifdef _WIN32
        pipe.reset();
#else
        close_fd(channel);
#endif
    }
    void terminate_child() {
        close_channel();
        if (child > 0 && !terminating) {
            // A closed channel can precede waitpid's reserved exit status.
            // Do not replace that status with SIGTERM during interpreter exit.
            terminating = true;
            terminate_at = Clock::now() + 250ms;
        }
    }
    void request_shutdown() {
        cancel();
        shutdown_requested = true;
        state = State::headless;
        close_channel();
    }
    std::optional<std::string> receive_packet() {
#ifdef _WIN32
        if (!pipe || !pipe->accept(static_cast<uint32_t>(child)))
            return {};
        return pipe->receive();
#else
        char data[4097];
        ssize_t count = recv(channel, data, sizeof data, 0);
        if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
            return {};
        if (count <= 0 || count > 4096)
            throw std::runtime_error("invalid GUI message size");
        return std::string(data, size_t(count));
#endif
    }
    bool queued_close() {
        // On a channel error, retain explicit close intent but never replay actions.
        for (int i = 0; i < 6; ++i) {
            try {
                auto packet = receive_packet();
                if (!packet)
                    break;
                {
                    auto j = Json::parse(*packet);
                    if (j.object().size() == 2 && j.at("version").integer() == 2 &&
                        j.at("type").string() == "close")
                        return true;
                }
            } catch (const std::exception&) {
            }
        }
        return false;
    }
    void fallback(const std::string& reason) {
        cancel();
        pending_failure = reason;
        terminate_child();
        if (child > 0) {
            state = State::settling;
            settle_at = Clock::now() + 250ms;
        } else {
            note(reason + "; falling back to terminal");
            terminal();
        }
    }
    void launch() {
#ifdef _WIN32
        auto python = python_path(), helper = helper_path();
        if (python.empty() || !std::filesystem::is_regular_file(std::filesystem::u8path(helper))) {
            fallback("Python interpreter or LCD helper unavailable");
            return;
        }
        pipe = std::make_unique<WindowsChannel>();
        auto command = win::quote(win::wide(python)) + L" -I " + win::quote(win::wide(helper)) +
                       L" --pipe " + win::quote(pipe->name()) + L" --parent-pid " +
                       std::to_wstring(GetCurrentProcessId());
        STARTUPINFOW startup{};
        startup.cb = sizeof startup;
        PROCESS_INFORMATION result{};
        if (!CreateProcessW(win::wide(python).c_str(), command.data(), nullptr, nullptr, FALSE,
                            CREATE_NO_WINDOW, nullptr, nullptr, &startup, &result))
            throw win::error("launch LCD helper");
        CloseHandle(result.hThread);
        process = win::Handle(result.hProcess);
        child = result.dwProcessId;
        state = State::starting;
        started = progress = gui_output_progress = Clock::now();
        heartbeat = next_frame = Time{};
#else
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
#endif
    }
    void reap(Time now) {
        if (child <= 0)
            return;
#ifdef _WIN32
        DWORD exit_status = STILL_ACTIVE;
        if (!GetExitCodeProcess(process.get(), &exit_status))
            throw win::error("inspect LCD helper");
        if (WaitForSingleObject(process.get(), 0) == WAIT_OBJECT_0) {
            child = -1;
            process.reset();
            if (exit_status == 10)
                request_shutdown();
            if (state == State::starting || state == State::gui)
                fallback("graphical window closed or viewer exited");
        } else if (terminating && now >= terminate_at) {
            if (!TerminateProcess(process.get(), 1))
                throw win::error("stop owned LCD helper");
        }
#else
        int status = 0;
        pid_t result = waitpid(child, &status, WNOHANG);
        if (result == child || (result < 0 && errno == ECHILD)) {
            child = -1;
            // A deliberate window close is distinct from a crash or lost GUI.
            // Exit 10 also covers close intent racing with process reaping.
            if (result > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 10) {
                request_shutdown();
            }
            if (state == State::starting || state == State::gui)
                fallback("graphical window closed or viewer exited");
        } else if (terminating && !term_sent && now >= terminate_at) {
            kill(child, SIGTERM);
            term_sent = true;
            terminate_at = now + 2s;
        } else if (terminating && term_sent && !killed && now >= terminate_at) {
            kill(child, SIGKILL);
            killed = true;
        }
#endif
    }
    bool send_message(const std::string& bytes) {
#ifdef _WIN32
        if (!pipe || !pipe->accept(static_cast<uint32_t>(child)) || !pipe->send(bytes))
            return false;
        gui_output_progress = Clock::now();
        return true;
#else
        ssize_t count = send(channel, bytes.data(), bytes.size(), 0);
        if (count == ssize_t(bytes.size())) {
            gui_output_progress = Clock::now();
            return true;
        }
        if (count < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR))
            return false;
        throw std::runtime_error("GUI channel write failed");
#endif
    }
    void gui_tick(Time now) {
        for (int i = 0; i < 6; ++i) {
            auto packet = receive_packet();
            if (!packet)
                break;
            Json j = Json::parse(*packet);
            if (j.at("version").integer() != 2)
                throw std::runtime_error("invalid GUI message schema");
            std::string type = j.at("type").string();
            if (type == "action" && engine && state == State::gui) {
                if (j.object().size() != 6 || j.at("session").string() != session ||
                    j.at("id").number() != double(last_action + 1))
                    throw std::runtime_error("invalid or duplicate GUI action");
                auto id = ++last_action;
                if (j.at("epoch").number() != double(engine->local_revision())) {
                    status = "State changed; retry";
                } else {
                    auto command = j.at("command").string();
                    if (command != "cw" && command != "ccw" && command != "press" &&
                        command != "door open" && command != "door close")
                        throw std::runtime_error("invalid GUI command");
                    action(command);
                }
                if (!send_message(Json(Json::Object{{"version", 2},
                                                    {"type", "ack"},
                                                    {"session", session},
                                                    {"id", double(id)},
                                                    {"epoch", double(engine->local_revision())},
                                                    {"status", status}})
                                      .dump()))
                    throw std::runtime_error("GUI acknowledgment blocked; edit canceled");
            } else if (j.object().size() != 2) {
                throw std::runtime_error("invalid GUI lifecycle schema");
            } else if (type == "close") {
                request_shutdown();
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
        if (engine)
            latest = unicode_lcd(engine->lcd_rows(), replacement_reported);
        uint64_t epoch = engine ? engine->local_revision() : 0;
        bool door = engine && engine->local_door();
        const EquipmentStates equipment =
            engine ? engine->local_equipment() : EquipmentStates{{-1, -1, -1, -1}};
        if (state == State::gui && now >= next_frame &&
            (latest != shown || dim != shown_dim || epoch != shown_epoch || door != shown_door ||
             equipment != shown_equipment || status != shown_status)) {
            next_frame = now + 100ms;
            Json::Array rows;
            for (const auto& row : latest)
                rows.emplace_back(row);
            Json::Array outputs;
            for (int value : equipment)
                outputs.emplace_back(value);
            auto bytes = Json(Json::Object{{"version", 2},
                                           {"type", "frame"},
                                           {"sequence", double(++sequence)},
                                           {"rows", rows},
                                           {"dim", dim},
                                           {"door", door},
                                           {"equipment", outputs},
                                           {"status", status},
                                           {"session", session},
                                           {"epoch", double(epoch)}})
                             .dump();
            if (bytes.size() > 4096)
                throw std::runtime_error("oversized GUI frame");
            if (send_message(bytes)) {
                shown = latest;
                shown_dim = dim;
                shown_epoch = epoch;
                shown_door = door;
                shown_equipment = equipment;
                shown_status = status;
                next_frame = now + 100ms;
            }
        }
    }
    void terminal_tick(Time now) {
#ifdef _WIN32
        if (!console)
            throw std::runtime_error("console unavailable");
        console->check();
        auto dimensions = console->dimensions();
        unsigned columns = dimensions.first, rows = dimensions.second;
#else
        if (!foreground(tty)) {
            restore_input();
            cancel();
            suspended = true;
            return;
        }
        winsize size{};
        SignalMask mask;
        if (!mask.valid)
            throw std::runtime_error("cannot guard terminal operation");
        if (ioctl(tty, TIOCGWINSZ, &size) != 0 || size.ws_col == 0 || size.ws_row == 0)
            throw std::runtime_error("terminal dimensions unavailable");
        unsigned columns = size.ws_col, rows = size.ws_row;
#endif
        if (width != columns || height != rows || suspended) {
            width = columns;
            height = rows;
            terminal_output.clear();
            written = 0;
            region = false;
            shown = {};
            suspended = false;
            next_frame = Time{};
        }
        const unsigned minimum_rows = engine ? (ansi ? 15u : 11u) : 7u;
        if (width < 23 || height < minimum_rows) {
            restore_input();
            cancel();
            if (!small_reported) {
                note("terminal needs at least 23 columns and " + std::to_string(minimum_rows) +
                     " rows; display suspended");
                small_reported = true;
            }
            return;
        }
        small_reported = false;
        if (ansi && engine)
            terminal_input(now);
        dim = !keep_on && now - activity > 60s;
        if (engine)
            latest = unicode_lcd(engine->lcd_rows(), replacement_reported);
        const bool door = engine && engine->local_door();
        const EquipmentStates equipment =
            engine ? engine->local_equipment() : EquipmentStates{{-1, -1, -1, -1}};
        std::string prompt = acknowledged > now ? status : "> " + input;
        if (dropping)
            prompt = "Line too long/invalid";
        if (terminal_output.empty() &&
            (latest != shown || dim != shown_dim || door != shown_door ||
             equipment != shown_equipment || (ansi && engine && prompt != shown_status)) &&
            now >= next_frame) {
            std::string frame;
            if (ansi && region)
                frame = "\r\x1b[" + std::to_string(terminal_lines) + "A";
            else
                frame = "\r\n";
            if (!ansi) {
                char stamp[40];
                std::time_t t = std::time(nullptr);
                std::tm tm{};
#ifdef _WIN32
                gmtime_s(&tm, &t);
#else
                gmtime_r(&t, &tm);
#endif
                std::strftime(stamp, sizeof stamp, "%Y-%m-%d %H:%M:%SZ\r\n", &tm);
                frame += stamp;
            }
            unsigned lines = 0;
            auto line = [&](const std::string& text) {
                ++lines;
                frame += "\r";
                if (ansi)
                    frame += "\x1b[2K";
                frame += text + "\r\n";
            };
            line("+--------------------+");
            for (const auto& row : latest)
                line(std::string(dim && ansi ? "\x1b[2m" : "") + "|" + row + "|" +
                     (dim && ansi ? "\x1b[0m" : ""));
            line("+--------------------+");
            if (engine) {
                auto label = [&](size_t index) {
                    return equipment[index] < 0 ? "N/A" : equipment[index] ? "ON " : "OFF";
                };
                if (ansi)
                    line("");
                line(std::string("Heater ") + label(0) + "  Cooler " + label(1));
                line(std::string("Fan    ") + label(2) + "  Light  " + label(3));
                line(std::string("Door   ") + (door ? "OPEN" : "CLOSED"));
                if (ansi) {
                    line("");
                    line("ccw | press | cw");
                    line("door open | door close");
                }
            }
            if (ansi && engine)
                frame += "\r\x1b[2K" + prompt.substr(0, width - 1);

            terminal_output = std::move(frame);
            written = 0;
            output_progress = now;
            shown = latest;
            shown_dim = dim;
            shown_status = prompt;
            shown_equipment = equipment;
            shown_door = door;
            terminal_lines = lines;
            next_frame = now + (ansi ? 100ms : 1000ms);
            region = true;
        }
        if (!terminal_output.empty()) {
#ifdef _WIN32
            auto n = console->output(terminal_output) ? terminal_output.size() : size_t(0);
#else
            ssize_t n =
                write(tty, terminal_output.data() + written, terminal_output.size() - written);
#endif
            if (n > 0) {
                written += size_t(n);
                output_progress = now;
                if (written == terminal_output.size()) {
                    terminal_output.clear();
                    written = 0;
                }
            }
#ifndef _WIN32
            else if (n < 0 && errno == EIO) {
                suspended = true;
            } else if (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)
                throw std::runtime_error("terminal write failed");
#endif
            if (now - output_progress >= 5s)
                throw std::runtime_error("terminal output stalled");
        }
    }
    void tick(const LcdRows& raw) {
        Time now = Clock::now();
        if (engine)
            engine->local_tick(wall_ms());
        dim = !keep_on && now - activity > 60s;
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
            if (state == State::settling && (child < 0 || now >= settle_at)) {
                note(pending_failure + "; falling back to terminal");
                terminal();
            }
            if (state == State::terminal)
                terminal_tick(now);
        } catch (const std::exception& e) {
            if (controller_failure)
                std::rethrow_exception(controller_failure);
            if (state == State::starting || state == State::gui) {
                if (queued_close())
                    request_shutdown();
                else
                    fallback(e.what());
            } else {
                note(std::string(e.what()) + "; continuing headless");
                restore_input();
                cancel();
                state = State::headless;
                terminal_output.clear();
            }
        }
    }
    ~Impl() {
        restore_input();
        cancel();
        state = State::headless;
        terminate_child();
        // Engine checkpoint decisions have already completed before this RAII
        // cleanup. Poll in short slices; never advance simulated time here.
        Time deadline = Clock::now() + 2500ms;
        while (child > 0 && Clock::now() < deadline) {
            reap(Clock::now());
            if (child > 0)
#ifdef _WIN32
                Sleep(10);
#else
                poll(nullptr, 0, 10);
#endif
        }
        if (child > 0) {
#ifdef _WIN32
            TerminateProcess(process.get(), 1);
            WaitForSingleObject(process.get(), 5000);
#else
            kill(child, SIGKILL);
            while (waitpid(child, nullptr, 0) < 0 && errno == EINTR) {
            }
#endif
        }
#ifndef _WIN32
        if (foreground(tty)) {
            SignalMask mask;
            if (mask.valid)
                (void)write(tty, "\r\n", 2);
        }
        close_fd(tty);
        close_fd(diagnostic_fd);
#endif
    }
};
LocalLcd::LocalLcd(const std::string& mode, const LcdRows& initial, Engine* engine, bool keep_on) {
    impl = std::make_unique<Impl>();
    impl->engine = engine;
    impl->keep_on = keep_on;
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
void LocalLcd::suspend() noexcept {
    if (!impl)
        return;
    impl->restore_input();
    impl->cancel();
    impl->suspended = true;
}
void LocalLcd::tick(const LcdRows& rows, bool writable) {
    if (!impl)
        return;
    impl->writable = writable;
    try {
        impl->tick(rows);
    } catch (...) {
        if (impl->controller_failure)
            std::rethrow_exception(impl->controller_failure);
        impl->restore_input();
        impl->cancel();
        impl->note("display unavailable; continuing headless");
        impl->terminate_child();
        impl->state = Impl::State::headless;
    }
}
} // namespace rmx
