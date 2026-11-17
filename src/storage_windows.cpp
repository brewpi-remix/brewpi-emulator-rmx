// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "storage.hpp"
#include "windows_host.hpp"

#include <algorithm>
#include <iterator>

namespace rmx {
namespace storage_detail {
// A named exception type keeps MSVC RTTI independent of the source root.
// Internal helper types remain local to this translation unit.
struct MissingParent {};
} // namespace storage_detail
namespace {
using storage_detail::MissingParent;
// Hold every parent without delete sharing while using a pathname. This keeps
// cooperative Windows renames/reparse replacement from changing its ancestry.
// File locks are host ownership, not an authentication or hostile-admin boundary.
class Parents {
    std::vector<win::Handle> handles;

  public:
    std::filesystem::path file;
    explicit Parents(const std::filesystem::path& input, bool create) {
        auto absolute = std::filesystem::absolute(input).lexically_normal();
        auto root = absolute.root_path();
        auto root_text = root.native();
        if (root_text.size() != 3 || root_text[1] != L':' || root_text[2] != L'\\')
            throw std::runtime_error("Windows host files require a local drive path");
        std::filesystem::path current(L"\\\\?\\" + root_text);
        auto pin = [&](const std::filesystem::path& directory) {
            win::Handle handle(
                CreateFileW(directory.c_str(), FILE_READ_ATTRIBUTES,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING,
                            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
            if (!handle && !create &&
                (GetLastError() == ERROR_FILE_NOT_FOUND || GetLastError() == ERROR_PATH_NOT_FOUND))
                throw MissingParent{};
            if (!handle)
                throw win::error("pin host directory");
            BY_HANDLE_FILE_INFORMATION info{};
            if (!GetFileInformationByHandle(handle.get(), &info))
                throw win::error("inspect host directory");
            if (!(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
                info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)
                throw std::runtime_error("host directory is a reparse point or not a directory");
            handles.push_back(std::move(handle));
        };
        pin(current);
        auto relative = absolute.relative_path();
        for (auto part = relative.begin(); part != relative.end(); ++part) {
            const auto name = part->native();
            if (name.empty() || name == L"." || name == L".." ||
                name.find_first_of(L":\"<>|?*\r\n") != std::wstring::npos || name.back() == L'.' ||
                name.back() == L' ' || name.find(L'\0') != std::wstring::npos)
                throw std::runtime_error("ambiguous Windows host filename");
            current /= *part;
            if (std::next(part) == relative.end()) {
                file = current;
                break;
            }
            if (create) {
                win::PrivateSecurity security;
                if (!CreateDirectoryW(current.c_str(), security.get()) &&
                    GetLastError() != ERROR_ALREADY_EXISTS)
                    throw win::error("create host directory");
            }
            pin(current);
        }
        if (file.empty())
            throw std::runtime_error("host filename is missing");
    }
};
win::Handle read_handle(const std::filesystem::path& file, bool replacement = false) {
    win::Handle handle(CreateFileW(file.c_str(), GENERIC_READ | (replacement ? DELETE : DWORD(0)),
                                   FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
                                   FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (!handle && GetLastError() != ERROR_FILE_NOT_FOUND)
        throw win::error("open store");
    return handle;
}
std::optional<Json> read_pinned(const std::filesystem::path& file) {
    auto handle = read_handle(file);
    if (!handle)
        return {};
    auto info = win::regular(handle.get(), false);
    if (info.nFileSizeHigh || info.nFileSizeLow > 1024 * 1024)
        throw std::runtime_error("store is not a bounded regular file");
    std::string data;
    char buffer[4096];
    for (;;) {
        DWORD count = 0;
        if (!ReadFile(handle.get(), buffer, sizeof buffer, &count, nullptr))
            throw win::error("read store");
        if (!count)
            break;
        data.append(buffer, count);
        if (data.size() > 1024 * 1024)
            throw std::runtime_error("store grew beyond the host-file size limit");
    }
    return Json::parse(data);
}
} // namespace
struct Storage::Impl {
    Parents parents;
    win::Handle lock;
    explicit Impl(const std::filesystem::path& file) : parents(file, true) {
        win::PrivateSecurity security;
        // Normalize an existing leaf through its open handle so an 8.3 alias
        // cannot acquire a different sidecar lock for the same stored image.
        auto existing = read_handle(parents.file);
        if (existing) {
            win::regular(existing.get(), true);
            DWORD needed =
                GetFinalPathNameByHandleW(existing.get(), nullptr, 0, FILE_NAME_NORMALIZED);
            if (!needed || needed > 32767)
                throw win::error("size canonical store path");
            std::wstring canonical(static_cast<size_t>(needed), L'\0');
            DWORD count = GetFinalPathNameByHandleW(existing.get(), canonical.data(), needed,
                                                    FILE_NAME_NORMALIZED);
            if (!count || count >= needed)
                throw win::error("resolve canonical store path");
            canonical.resize(count);
            parents.file = canonical;
        }
        auto name = parents.file.native() + L".lock";
        lock = win::Handle(CreateFileW(name.c_str(), GENERIC_READ | GENERIC_WRITE | READ_CONTROL, 0,
                                       security.get(), OPEN_ALWAYS, FILE_FLAG_OPEN_REPARSE_POINT,
                                       nullptr));
        if (!lock)
            throw win::error("store already owned or cannot lock");
        win::regular(lock.get(), true);
        security.verify(lock.get());
    }
};
Storage::Storage(std::filesystem::path file)
    : path(std::move(file)), impl(std::make_unique<Impl>(path)) {}
Storage::~Storage() = default;
std::optional<Json> Storage::load() const {
    return read_pinned(impl->parents.file);
}
std::optional<Json> Storage::read(const std::filesystem::path& file) {
    try {
        Parents parents(file, false);
        return read_pinned(parents.file);
    } catch (const MissingParent&) {
        return {};
    }
}
void Storage::write(const Json& image) const {
    // A single store-image replacement is the unit of host atomicity. This does
    // not make a firmware command transactional or promise power-loss durability.
    auto existing = read_handle(impl->parents.file, true);
    if (existing)
        win::regular(existing.get(), true);
    auto temporary = impl->parents.file.native() + L".write-" + win::nonce();
    win::PrivateSecurity security;
    win::Handle output(CreateFileW(temporary.c_str(), GENERIC_WRITE | DELETE, 0, security.get(),
                                   CREATE_NEW, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_WRITE_THROUGH,
                                   nullptr));
    if (!output)
        throw win::error("create store replacement");
    bool replaced = false;
    try {
        auto data = image.dump() + "\n";
        size_t position = 0;
        while (position < data.size()) {
            DWORD count = 0;
            auto amount = static_cast<DWORD>(std::min<size_t>(data.size() - position, 65536));
            if (!WriteFile(output.get(), data.data() + position, amount, &count, nullptr) || !count)
                throw win::error("write store");
            position += count;
        }
        if (!FlushFileBuffers(output.get()))
            throw win::error("sync store replacement");
        auto name = impl->parents.file.native();
        size_t bytes = name.size() * sizeof(wchar_t);
        std::vector<BYTE> buffer(sizeof(FILE_RENAME_INFO) + bytes);
        auto* rename = reinterpret_cast<FILE_RENAME_INFO*>(buffer.data());
        rename->Flags = FILE_RENAME_FLAG_REPLACE_IF_EXISTS | FILE_RENAME_FLAG_POSIX_SEMANTICS;
        rename->RootDirectory = nullptr;
        rename->FileNameLength = static_cast<DWORD>(bytes);
        std::copy(name.begin(), name.end(), rename->FileName);
        // Keep DELETE access to the old image through replacement. Existing
        // readers must share deletion; the held access also refuses new readers
        // that would deny it. POSIX replacement preserves permitted readers'
        // old handles while publishing the new complete image atomically.
        if (!SetFileInformationByHandle(output.get(), FileRenameInfoEx, rename,
                                        static_cast<DWORD>(buffer.size())))
            throw win::error("replace store");
        replaced = true;
        // Native unprivileged Windows has no claimed equivalent of a whole-
        // volume metadata flush. Failure after rename has uncertain durability.
        if (!FlushFileBuffers(output.get()))
            throw win::error("sync replaced store; replacement already occurred");
    } catch (...) {
        if (!replaced) {
            FILE_DISPOSITION_INFO remove{};
            remove.DeleteFile = TRUE;
            (void)SetFileInformationByHandle(output.get(), FileDispositionInfo, &remove,
                                             sizeof remove);
        }
        throw;
    }
}
} // namespace rmx
