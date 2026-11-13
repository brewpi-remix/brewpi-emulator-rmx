// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "storage.hpp"

#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace rmx {
namespace {
std::runtime_error error(const std::string& action) {
    return std::runtime_error(action + ": " + std::strerror(errno));
}
} // namespace
Storage::Storage(std::filesystem::path file) : path(std::move(file)) {
    if (!path.parent_path().empty())
        std::filesystem::create_directories(path.parent_path());
    lock_fd =
        ::open((path.string() + ".lock").c_str(), O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (lock_fd < 0)
        throw error("open store lock");
    if (::flock(lock_fd, LOCK_EX | LOCK_NB) != 0) {
        ::close(lock_fd);
        lock_fd = -1;
        throw error("store already owned or cannot lock");
    }
}
Storage::~Storage() {
    if (lock_fd >= 0)
        ::close(lock_fd);
}
std::optional<Json> Storage::load() const {
    int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) {
        if (errno == ENOENT)
            return {};
        throw error("open store");
    }
    struct stat st{};
    if (::fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_size > 1024 * 1024) {
        ::close(fd);
        throw std::runtime_error("store is not a bounded regular file");
    }
    std::string data;
    char buf[4096];
    for (;;) {
        ssize_t n = ::read(fd, buf, sizeof buf);
        if (n > 0) {
            data.append(buf, size_t(n));
            if (data.size() > 1024 * 1024) {
                ::close(fd);
                throw std::runtime_error("store grew beyond the host-file size limit");
            }
        } else if (n == 0)
            break;
        else if (errno != EINTR) {
            ::close(fd);
            throw error("read store");
        }
    }
    ::close(fd);
    return Json::parse(data);
}
void Storage::write(const Json& image) const {
    // Host-file replacement protects the representation of each individual
    // firmware-like store operation; it does not make a j object transactional.
    std::string pattern = path.string() + ".write-XXXXXX";
    std::vector<char> name(pattern.begin(), pattern.end());
    name.push_back(0);
    int fd = ::mkstemp(name.data());
    if (fd < 0)
        throw error("create store replacement");
    try {
        std::string data = image.dump() + "\n";
        size_t pos = 0;
        while (pos < data.size()) {
            ssize_t n = ::write(fd, data.data() + pos, data.size() - pos);
            if (n > 0)
                pos += size_t(n);
            else if (n < 0 && errno == EINTR)
                continue;
            else
                throw error("write store");
        }
        if (::fsync(fd) < 0)
            throw error("sync store");
        if (::close(fd) < 0) {
            fd = -1;
            throw error("close store");
        }
        fd = -1;
        if (::rename(name.data(), path.c_str()) < 0)
            throw error("replace store");
        auto parent = path.parent_path().empty() ? std::filesystem::path(".") : path.parent_path();
        int dir = ::open(parent.c_str(), O_RDONLY | O_CLOEXEC);
        if (dir < 0)
            throw error("open store directory");
        int result = ::fsync(dir);
        int saved_errno = errno;
        ::close(dir);
        if (result < 0) {
            errno = saved_errno;
            throw error("sync store directory");
        }
    } catch (...) {
        if (fd >= 0)
            ::close(fd);
        ::unlink(name.data());
        throw;
    }
}
} // namespace rmx
