// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "json.hpp"

#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace rmx {
bool Json::has(const std::string& key) const {
    if (auto p = std::get_if<Object>(&value)) {
        for (auto& entry : *p)
            if (entry.first == key)
                return true;
    }
    return false;
}
const Json& Json::at(const std::string& key) const {
    for (auto& entry : object())
        if (entry.first == key)
            return entry.second;
    throw std::runtime_error("missing JSON field: " + key);
}
Json& Json::operator[](const std::string& key) {
    if (null())
        value = Object{};
    auto& o = std::get<Object>(value);
    for (auto& entry : o)
        if (entry.first == key)
            return entry.second;
    o.emplace_back(key, Json{});
    return o.back().second;
}
const Json::Array& Json::array() const {
    return std::get<Array>(value);
}
const Json::Object& Json::object() const {
    return std::get<Object>(value);
}
std::string Json::string() const {
    return std::get<std::string>(value);
}
double Json::number() const {
    return std::get<double>(value);
}
int Json::integer() const {
    double n = number();
    if (!std::isfinite(n) || n < std::numeric_limits<int>::min() ||
        n > std::numeric_limits<int>::max() || n != std::trunc(n))
        throw std::runtime_error("JSON integer out of range");
    return static_cast<int>(n);
}
bool Json::boolean() const {
    return std::get<bool>(value);
}
bool Json::null() const {
    return std::holds_alternative<std::nullptr_t>(value);
}
std::string Json::dump() const {
    if (null())
        return "null";
    if (auto p = std::get_if<bool>(&value))
        return *p ? "true" : "false";
    if (auto p = std::get_if<double>(&value)) {
        if (!std::isfinite(*p))
            throw std::runtime_error("nonfinite JSON number");
        std::ostringstream s;
        s << std::setprecision(17) << *p;
        return s.str();
    }
    if (auto p = std::get_if<std::string>(&value)) {
        std::string s = "\"";
        const char* hex = "0123456789abcdef";
        for (char ch : *p) {
            auto c = static_cast<unsigned char>(ch);
            if (c == '"' || c == '\\') {
                s += '\\';
                s += char(c);
            } else if (c < 32) {
                s += "\\u00";
                s += hex[c >> 4];
                s += hex[c & 15];
            } else
                s += char(c);
        }
        return s + '"';
    }
    if (auto p = std::get_if<Array>(&value)) {
        std::string s = "[";
        for (auto& v : *p) {
            if (s.size() > 1)
                s += ',';
            s += v.dump();
        }
        return s + ']';
    }
    std::string s = "{";
    for (auto& e : object()) {
        if (s.size() > 1)
            s += ',';
        s += Json(e.first).dump() + ':' + e.second.dump();
    }
    return s + '}';
}
namespace {
class Reader {
    const std::string& s;
    size_t pos = 0;
    [[noreturn]] void fail() const {
        throw std::runtime_error("invalid local JSON at byte " + std::to_string(pos));
    }
    void space() {
        while (pos < s.size() &&
               (s[pos] == ' ' || s[pos] == '\n' || s[pos] == '\r' || s[pos] == '\t'))
            ++pos;
    }
    bool take(char c) {
        space();
        if (pos < s.size() && s[pos] == c) {
            ++pos;
            return true;
        }
        return false;
    }
    unsigned hex4() {
        unsigned n = 0;
        for (int i = 0; i < 4; ++i) {
            if (pos == s.size())
                fail();
            char c = s[pos++];
            int d = c >= '0' && c <= '9'   ? c - '0'
                    : c >= 'a' && c <= 'f' ? c - 'a' + 10
                    : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                           : -1;
            if (d < 0)
                fail();
            n = n * 16 + unsigned(d);
        }
        return n;
    }
    void utf8(std::string& out, unsigned cp) {
        if (cp < 128)
            out += char(cp);
        else if (cp < 2048) {
            out += char(0xc0 | (cp >> 6));
            out += char(0x80 | (cp & 63));
        } else if (cp < 65536) {
            out += char(0xe0 | (cp >> 12));
            out += char(0x80 | ((cp >> 6) & 63));
            out += char(0x80 | (cp & 63));
        } else {
            out += char(0xf0 | (cp >> 18));
            out += char(0x80 | ((cp >> 12) & 63));
            out += char(0x80 | ((cp >> 6) & 63));
            out += char(0x80 | (cp & 63));
        }
    }
    std::string str() {
        if (!take('"'))
            fail();
        std::string out;
        while (pos < s.size()) {
            unsigned char c = static_cast<unsigned char>(s[pos++]);
            if (c == '"')
                return out;
            if (c < 32)
                fail();
            if (c != '\\') {
                if (c < 128)
                    out += char(c);
                else {
                    unsigned count = c >= 0xc2 && c <= 0xdf   ? 1
                                     : c >= 0xe0 && c <= 0xef ? 2
                                     : c >= 0xf0 && c <= 0xf4 ? 3
                                                              : 0;
                    if (!count)
                        fail();
                    unsigned cp = c & (0x7fU >> (count + 1));
                    for (unsigned i = 0; i < count; ++i) {
                        if (pos == s.size())
                            fail();
                        unsigned char next = static_cast<unsigned char>(s[pos++]);
                        if ((next & 0xc0) != 0x80)
                            fail();
                        cp = (cp << 6) | (next & 0x3f);
                    }
                    unsigned minimum = count == 1 ? 0x80 : count == 2 ? 0x800 : 0x10000;
                    if (cp < minimum || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff))
                        fail();
                    utf8(out, cp);
                }
                continue;
            }
            if (pos == s.size())
                fail();
            char e = s[pos++];
            if (e == '"' || e == '\\' || e == '/')
                out += e;
            else if (e == 'b')
                out += '\b';
            else if (e == 'f')
                out += '\f';
            else if (e == 'n')
                out += '\n';
            else if (e == 'r')
                out += '\r';
            else if (e == 't')
                out += '\t';
            else if (e == 'u') {
                unsigned cp = hex4();
                if (cp >= 0xd800 && cp <= 0xdbff) {
                    if (pos + 2 > s.size() || s.substr(pos, 2) != "\\u")
                        fail();
                    pos += 2;
                    unsigned low = hex4();
                    if (low < 0xdc00 || low > 0xdfff)
                        fail();
                    cp = 0x10000 + (cp - 0xd800) * 1024 + low - 0xdc00;
                } else if (cp >= 0xdc00 && cp <= 0xdfff)
                    fail();
                utf8(out, cp);
            } else
                fail();
        }
        fail();
    }
    Json read(unsigned depth) {
        if (depth > 64)
            fail();
        space();
        if (pos == s.size())
            fail();
        if (s[pos] == '"')
            return str();
        if (take('{')) {
            Json o(Json::Object{});
            if (take('}'))
                return o;
            do {
                std::string k = str();
                if (o.has(k) || !take(':'))
                    fail();
                o[k] = read(depth + 1);
            } while (take(','));
            if (!take('}'))
                fail();
            return o;
        }
        if (take('[')) {
            Json::Array a;
            if (take(']'))
                return a;
            do {
                a.push_back(read(depth + 1));
            } while (take(','));
            if (!take(']'))
                fail();
            return a;
        }
        for (auto lit : {"null", "true", "false"}) {
            std::string l = lit;
            if (s.compare(pos, l.size(), l) == 0) {
                pos += l.size();
                return l == "null" ? Json{} : Json(l == "true");
            }
        }
        size_t start = pos;
        if (s[pos] == '-')
            ++pos;
        if (pos == s.size())
            fail();
        if (s[pos] == '0')
            ++pos;
        else {
            if (s[pos] < '1' || s[pos] > '9')
                fail();
            while (pos < s.size() && s[pos] >= '0' && s[pos] <= '9')
                ++pos;
        }
        if (pos < s.size() && s[pos] == '.') {
            ++pos;
            size_t d = pos;
            while (pos < s.size() && s[pos] >= '0' && s[pos] <= '9')
                ++pos;
            if (d == pos)
                fail();
        }
        if (pos < s.size() && (s[pos] == 'e' || s[pos] == 'E')) {
            ++pos;
            if (pos < s.size() && (s[pos] == '+' || s[pos] == '-'))
                ++pos;
            size_t d = pos;
            while (pos < s.size() && s[pos] >= '0' && s[pos] <= '9')
                ++pos;
            if (d == pos)
                fail();
        }
        try {
            double v = std::stod(s.substr(start, pos - start));
            if (!std::isfinite(v))
                fail();
            return v;
        } catch (...) {
            fail();
        }
    }

  public:
    explicit Reader(const std::string& text) : s(text) {}
    Json run() {
        Json j = read(0);
        space();
        if (pos != s.size())
            fail();
        return j;
    }
};
} // namespace
Json Json::parse(const std::string& text) {
    return Reader(text).run();
}
} // namespace rmx
