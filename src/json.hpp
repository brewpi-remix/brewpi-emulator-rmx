// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace rmx {
// Local storage/test-envelope JSON. The Arduino wire reader is a separate stream grammar.
class Json {
  public:
    using Array = std::vector<Json>;
    using Object = std::vector<std::pair<std::string, Json>>;
    using Value = std::variant<std::nullptr_t, bool, double, std::string, Array, Object>;
    Value value = nullptr;
    Json() = default;
    Json(std::nullptr_t) {}
    Json(bool v) : value(v) {}
    Json(int v) : value(double(v)) {}
    Json(double v) : value(v) {}
    Json(const char* v) : value(std::string(v)) {}
    Json(std::string v) : value(std::move(v)) {}
    Json(Array v) : value(std::move(v)) {}
    Json(Object v) : value(std::move(v)) {}
    bool has(const std::string& key) const;
    const Json& at(const std::string& key) const;
    Json& operator[](const std::string& key);
    const Array& array() const;
    const Object& object() const;
    std::string string() const;
    double number() const;
    int integer() const;
    bool boolean() const;
    bool null() const;
    std::string dump() const;
    static Json parse(const std::string& text);
};
} // namespace rmx
