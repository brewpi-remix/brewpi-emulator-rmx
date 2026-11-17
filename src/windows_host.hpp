// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
// Windows base declarations precede dependent SDK headers.
// clang-format off
#include <windows.h>
// clang-format on
#include <aclapi.h>
#include <array>
#include <bcrypt.h>
#include <filesystem>
#include <sddl.h>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace rmx::win {
inline std::runtime_error error(const std::string& action) {
    return std::runtime_error(action + ": Windows error " + std::to_string(GetLastError()));
}
class Handle {
    HANDLE value = INVALID_HANDLE_VALUE;

  public:
    explicit Handle(HANDLE handle = INVALID_HANDLE_VALUE) : value(handle) {}
    ~Handle() {
        reset();
    }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    Handle(Handle&& other) noexcept : value(std::exchange(other.value, INVALID_HANDLE_VALUE)) {}
    Handle& operator=(Handle&& other) noexcept {
        if (this != &other) {
            reset();
            value = std::exchange(other.value, INVALID_HANDLE_VALUE);
        }
        return *this;
    }
    HANDLE get() const noexcept {
        return value;
    }
    explicit operator bool() const noexcept {
        return value && value != INVALID_HANDLE_VALUE;
    }
    void reset() noexcept {
        if (*this)
            CloseHandle(value);
        value = INVALID_HANDLE_VALUE;
    }
};
inline std::wstring wide(const std::string& text) {
    if (text.empty())
        return {};
    if (text.size() > 32767 || text.find('\0') != std::string::npos)
        throw std::runtime_error("invalid UTF-8 host text length");
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(),
                                    static_cast<int>(text.size()), nullptr, 0);
    if (count <= 0)
        throw error("decode UTF-8 host text");
    std::wstring result(static_cast<size_t>(count), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(),
                            static_cast<int>(text.size()), result.data(), count) != count)
        throw error("decode UTF-8 host text");
    return result;
}
inline std::string utf8(const std::wstring& text) {
    if (text.empty())
        return {};
    if (text.size() > 32767 || text.find(L'\0') != std::wstring::npos)
        throw std::runtime_error("invalid Windows host text length");
    int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
                                    static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    if (count <= 0)
        throw error("encode Windows host text");
    std::string result(static_cast<size_t>(count), '\0');
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, text.data(),
                            static_cast<int>(text.size()), result.data(), count, nullptr,
                            nullptr) != count)
        throw error("encode Windows host text");
    return result;
}
// Quote one Windows command-line argument without invoking a shell.
inline std::wstring quote(const std::wstring& text) {
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t c : text) {
        if (c == L'\\') {
            ++slashes;
            continue;
        }
        result.append(slashes * (c == L'"' ? 2 : 1), L'\\');
        if (c == L'"')
            result += L'\\';
        result += c;
        slashes = 0;
    }
    result.append(slashes * 2, L'\\');
    return result + L"\"";
}
inline std::wstring nonce() {
    std::array<unsigned char, 16> bytes{};
    if (BCryptGenRandom(nullptr, bytes.data(), static_cast<ULONG>(bytes.size()),
                        BCRYPT_USE_SYSTEM_PREFERRED_RNG) != 0)
        throw std::runtime_error("cannot obtain private host identifier");
    std::wstring result;
    for (auto byte : bytes) {
        result += L"0123456789abcdef"[byte >> 4];
        result += L"0123456789abcdef"[byte & 15];
    }
    return result;
}
class PrivateSecurity {
    std::vector<BYTE> token_user;
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    SECURITY_ATTRIBUTES attributes{};

  public:
    PrivateSecurity() {
        HANDLE raw = nullptr;
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &raw))
            throw error("read current account identity");
        Handle token(raw);
        DWORD size = 0;
        GetTokenInformation(token.get(), TokenUser, nullptr, 0, &size);
        if (GetLastError() != ERROR_INSUFFICIENT_BUFFER || size == 0)
            throw error("size current account identity");
        token_user.resize(size);
        if (!GetTokenInformation(token.get(), TokenUser, token_user.data(), size, &size))
            throw error("read current account identity");
        LPWSTR encoded = nullptr;
        if (!ConvertSidToStringSidW(sid(), &encoded))
            throw error("encode current account identity");
        std::wstring text = L"O:" + std::wstring(encoded) + L"D:P(A;;FA;;;" + encoded + L")";
        LocalFree(encoded);
        if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(text.c_str(), SDDL_REVISION_1,
                                                                  &descriptor, nullptr))
            throw error("create private host permissions");
        attributes.nLength = sizeof attributes;
        attributes.lpSecurityDescriptor = descriptor;
        attributes.bInheritHandle = FALSE;
    }
    ~PrivateSecurity() {
        LocalFree(descriptor);
    }
    PrivateSecurity(const PrivateSecurity&) = delete;
    PrivateSecurity& operator=(const PrivateSecurity&) = delete;
    PSID sid() const {
        return reinterpret_cast<const TOKEN_USER*>(token_user.data())->User.Sid;
    }
    SECURITY_ATTRIBUTES* get() {
        return &attributes;
    }
    void verify(HANDLE handle) const {
        PSID owner = nullptr;
        PACL acl = nullptr;
        PSECURITY_DESCRIPTOR actual = nullptr;
        DWORD code = GetSecurityInfo(handle, SE_FILE_OBJECT,
                                     OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION, &owner,
                                     nullptr, &acl, nullptr, &actual);
        if (code != ERROR_SUCCESS) {
            SetLastError(code);
            throw error("read private host permissions");
        }
        bool valid = owner && EqualSid(owner, sid()) && acl && acl->AceCount > 0;
        for (DWORD i = 0; valid && i < acl->AceCount; ++i) {
            void* data = nullptr;
            if (!GetAce(acl, i, &data)) {
                valid = false;
                break;
            }
            auto* ace = static_cast<ACCESS_ALLOWED_ACE*>(data);
            valid = ace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE &&
                    !(ace->Header.AceFlags & (INHERITED_ACE | INHERIT_ONLY_ACE)) &&
                    EqualSid(reinterpret_cast<PSID>(&ace->SidStart), sid());
        }
        LocalFree(actual);
        if (!valid)
            throw std::runtime_error("host ownership file is not private to the current account");
    }
};
inline BY_HANDLE_FILE_INFORMATION regular(HANDLE handle, bool single_link) {
    BY_HANDLE_FILE_INFORMATION info{};
    if (GetFileType(handle) != FILE_TYPE_DISK || !GetFileInformationByHandle(handle, &info))
        throw error("inspect host file");
    if (info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT) ||
        (single_link && info.nNumberOfLinks != 1))
        throw std::runtime_error("host file is not an ordinary unaliased file");
    return info;
}
} // namespace rmx::win
