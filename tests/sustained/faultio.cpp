// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
// Test-only POSIX I/O fault injection for owned temporary paths.
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <unistd.h>
static bool replaced = false;
extern "C" int rename(const char* old_path, const char* new_path) {
    auto original = reinterpret_cast<int (*)(const char*, const char*)>(dlsym(RTLD_NEXT, "rename"));
    const int result = original(old_path, new_path);
    const char* target = getenv("RMX_FAULT_TARGET");
    if (!result && target && getenv("RMX_FAULT_ARM") && access(getenv("RMX_FAULT_ARM"), F_OK) == 0 && !strcmp(target, new_path))
        replaced = true;
    return result;
}
extern "C" int fsync(int fd) {
    auto original = reinterpret_cast<int (*)(int)>(dlsym(RTLD_NEXT, "fsync"));
    const char* target = getenv("RMX_FAULT_TARGET");
    const char* stage = getenv("RMX_FAULT_STAGE");
    const char* arm = getenv("RMX_FAULT_ARM");
    if (!arm || access(arm, F_OK)) { replaced = false; return original(fd); }
    char link[64], path[4096];
    snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
    const auto length = readlink(link, path, sizeof(path)-1);
    if (target && stage && length > 0) {
        path[length] = 0;
        if ((!strcmp(stage, "before") && !strncmp(path, target, strlen(target)) && strstr(path, ".write-")) ||
            (!strcmp(stage, "after") && replaced)) {
            errno = EIO;
            return -1;
        }
    }
    return original(fd);
}
