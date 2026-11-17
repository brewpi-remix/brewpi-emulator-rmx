// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#include "storage.hpp"
#include "windows_host.hpp"

#include <fstream>
#include <iostream>

namespace {
void require(bool value, const char* reason) {
    if (!value)
        throw std::runtime_error(reason);
}
template <class Operation> void rejects(Operation operation, const char* reason) {
    bool refused = false;
    try {
        operation();
    } catch (const std::exception&) {
        refused = true;
    }
    require(refused, reason);
}
struct Directory {
    std::filesystem::path path;
    explicit Directory(const std::filesystem::path& parent)
        : path(parent / (L"storage-" + rmx::win::nonce())) {
        require(std::filesystem::create_directory(path), "test directory collision");
    }
    ~Directory() {
        std::error_code ignored;
        std::filesystem::remove_all(path, ignored);
    }
};
} // namespace
int wmain(int argc, wchar_t** argv) {
    try {
        require(argc == 2, "supply the approved isolated test parent");
        Directory directory{std::filesystem::path(argv[1])};
        auto root = directory.path;
        auto file = root / std::filesystem::u8path("Unicode \xc3\xa9 space") / "controller.json";
        require(!rmx::Storage::read(root / "not-created" / "missing.json"),
                "missing parent was not treated as missing input");
        {
            rmx::Storage store(file);
            require(!store.load(), "new store unexpectedly existed");
            rejects([&] { rmx::Storage duplicate(file); },
                    "same-process duplicate ownership accepted");
            for (int i = 0; i < 100; ++i) {
                auto image = rmx::Json(rmx::Json::Object{{"iteration", i}, {"wire", "original"}});
                store.write(image);
                require(store.load()->dump() == image.dump(), "replacement content differs");
            }
            {
                auto previous = store.load()->dump();
                rmx::win::Handle reader(
                    CreateFileW(file.c_str(), GENERIC_READ,
                                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                                OPEN_EXISTING, 0, nullptr));
                require(bool(reader), "shared-reader test setup failed");
                store.write(
                    rmx::Json::Object{{"iteration", 99}, {"wire", "shared-reader replacement"}});
                require(store.load()->at("wire").string() == "shared-reader replacement",
                        "new pathname did not expose replaced store");
                char data[4096];
                DWORD count = 0;
                require(ReadFile(reader.get(), data, sizeof data, &count, nullptr) != FALSE,
                        "old shared reader became invalid");
                require(rmx::Json::parse(std::string(data, count)).dump() == previous,
                        "existing shared reader did not retain old image");
            }
            auto alias = file.parent_path() / "CONTROLLER.JSON";
            rejects([&] { rmx::Storage duplicate(alias); }, "case alias acquired a different lock");
            require(!MoveFileExW(file.parent_path().c_str(), (root / "renamed").c_str(), 0),
                    "owned parent directory was renamed");
            auto hardlink = root / "alias.json";
            require(CreateHardLinkW(hardlink.c_str(), file.c_str(), nullptr) != FALSE,
                    "hard-link test setup failed");
            rejects([&] { rmx::Storage duplicate(hardlink); },
                    "hard-linked writable alias accepted");
            rejects([&] { store.write(rmx::Json::Object{{"changed", true}}); },
                    "replacement accepted a newly hard-linked image");
            std::filesystem::remove(hardlink);
            auto before = store.load()->dump();
            require(SetFileAttributesW(file.c_str(), FILE_ATTRIBUTE_READONLY) != FALSE,
                    "read-only test setup failed");
            rejects([&] { store.write(rmx::Json::Object{{"changed", true}}); },
                    "read-only replacement unexpectedly succeeded");
            require(store.load()->dump() == before, "failed replacement changed the store");
            require(SetFileAttributesW(file.c_str(), FILE_ATTRIBUTE_NORMAL) != FALSE,
                    "read-only test cleanup failed");
            {
                rmx::win::Handle reader(CreateFileW(file.c_str(), GENERIC_READ, FILE_SHARE_READ,
                                                    nullptr, OPEN_EXISTING, 0, nullptr));
                require(bool(reader), "busy-file test setup failed");
                rejects([&] { store.write(rmx::Json::Object{{"changed", true}}); },
                        "replacement ignored an external reader denying delete sharing");
            }
            require(store.load()->dump() == before, "busy-file failure changed the store");
            for (const auto& item : std::filesystem::directory_iterator(file.parent_path()))
                require(item.path().filename().native().find(L".write-") == std::wstring::npos,
                        "failed replacement left its temporary file");
        }
        {
            rmx::Storage reopened(file);
            require(reopened.load()->at("iteration").integer() == 99, "reopen lost saved state");
        }
        auto large = root / "oversized.json";
        {
            std::ofstream output(large, std::ios::binary);
            output << std::string(1024 * 1024 + 1, ' ');
            require(bool(output), "oversized-file setup failed");
        }
        rejects([&] { (void)rmx::Storage::read(large); }, "oversized file accepted");
        rejects([&] { (void)rmx::Storage::read(root); }, "directory accepted as JSON input");
        auto target = root / "target";
        std::filesystem::create_directory(target);
        auto link = root / "reparse";
        require(CreateSymbolicLinkW(link.c_str(), target.c_str(),
                                    SYMBOLIC_LINK_FLAG_DIRECTORY | 2) != FALSE,
                "reparse test setup needs Windows symlink permission");
        rejects([&] { rmx::Storage invalid(link / "image.json"); }, "reparse parent accepted");
        std::filesystem::remove(link);
        std::cout << "Windows storage: Unicode, replacement, ownership, case/hard-link aliases, "
                     "read-only failures, cleanup, bounded input, and reparse rejection passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
