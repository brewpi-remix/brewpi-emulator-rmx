// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
// Test-only Linux supervisor. Never linked into the candidate executable.
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted = 0;
static volatile sig_atomic_t child_pid = 0;
static void stop_child(int signum) {
    interrupted = signum;
    if (child_pid > 0)
        kill(static_cast<pid_t>(child_pid), SIGTERM);
}
static double now() {
    timespec stamp{};
    if (clock_gettime(CLOCK_MONOTONIC, &stamp))
        _exit(95);
    return static_cast<double>(stamp.tv_sec) + static_cast<double>(stamp.tv_nsec) / 1e9;
}
int main(int argc, char** argv) {
    if (argc < 4 || geteuid() == 0)
        return 96;
    const pid_t parent = getppid();
    struct sigaction action{};
    action.sa_handler = stop_child;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTERM, &action, nullptr) || sigaction(SIGINT, &action, nullptr) ||
        prctl(PR_SET_PDEATHSIG, SIGTERM) || getppid() != parent)
        return 97;
    const int pid_fd = open(argv[1], O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    const int result_fd = open(argv[2], O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (pid_fd < 0 || result_fd < 0 || interrupted)
        return 98;
    const double started = now();
    const pid_t supervisor = getpid();
    const pid_t child = fork();
    if (child < 0)
        return 99;
    if (child == 0) {
        if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != supervisor)
            _exit(126);
        close(pid_fd);
        close(result_fd);
        struct sigaction normal{};
        normal.sa_handler = SIG_DFL;
        sigemptyset(&normal.sa_mask);
        sigaction(SIGINT, &normal, nullptr);
        sigaction(SIGTERM, &normal, nullptr);
        execv(argv[3], argv + 3);
        _exit(127);
    }
    child_pid = static_cast<sig_atomic_t>(child);
    if (dprintf(pid_fd, "%ld\n", static_cast<long>(child)) < 0 || fsync(pid_fd)) {
        kill(child, SIGKILL);
        interrupted = SIGTERM;
    }
    close(pid_fd);
    rusage usage{};
    int status = 0;
    double interruption_started = 0;
    while (true) {
        const pid_t result = wait4(child, &status, WNOHANG, &usage);
        if (result == child)
            break;
        if (result < 0 && errno != EINTR)
            return 100;
        if (interrupted) {
            if (!interruption_started) {
                interruption_started = now();
                kill(child, SIGTERM);
            }
            if (now() - interruption_started > 5)
                kill(child, SIGKILL);
        }
        timespec pause{0, 100000000};
        nanosleep(&pause, nullptr);
    }
    child_pid = 0;
    const int exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
    const int bytes = dprintf(result_fd,
        "{\"emulator_pid\":%ld,\"wait4_collected\":true,\"exit_code\":%d,"
        "\"interrupted\":%d,\"maxrss_kib\":%ld,\"wall_seconds\":%.9f,"
        "\"user_seconds\":%.6f,\"system_seconds\":%.6f}\n",
        static_cast<long>(child), exit_code, static_cast<int>(interrupted), usage.ru_maxrss,
        now() - started,
        static_cast<double>(usage.ru_utime.tv_sec) + static_cast<double>(usage.ru_utime.tv_usec) / 1e6,
        static_cast<double>(usage.ru_stime.tv_sec) + static_cast<double>(usage.ru_stime.tv_usec) / 1e6);
    const bool saved = bytes > 0 && fsync(result_fd) == 0;
    close(result_fd);
    return saved && exit_code == 0 && !interrupted ? 0 : 1;
}
