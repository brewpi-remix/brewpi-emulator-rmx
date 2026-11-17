// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "json.hpp"

#include <filesystem>
#include <memory>
#include <optional>
namespace rmx {
class Storage {
    std::filesystem::path path;
#ifdef _WIN32
    struct Impl;
    std::unique_ptr<Impl> impl;
#else
    int lock_fd = -1;
#endif

  public:
    explicit Storage(std::filesystem::path file);
    ~Storage();
    Storage(const Storage&) = delete;
    Storage& operator=(const Storage&) = delete;
    std::optional<Json> load() const;
    static std::optional<Json> read(const std::filesystem::path& file);
    void write(const Json& image) const;
};
} // namespace rmx
