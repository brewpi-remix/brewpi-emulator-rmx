// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include "json.hpp"

#include <filesystem>
#include <optional>
namespace rmx {
class Storage {
    std::filesystem::path path;
    int lock_fd = -1;

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
