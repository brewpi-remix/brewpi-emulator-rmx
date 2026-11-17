// Copyright 2026 Lee Bussy
// SPDX-License-Identifier: MIT
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
// SDK declarations and GUID instantiation require this include order.
// clang-format off
#include <windows.h>
#include <initguid.h>
#include <devpkey.h>
#include <ntddser.h>
#include <setupapi.h>
// clang-format on
#include "windows_serial.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <set>
#include <stdexcept>
#include <vector>

namespace rmx {
namespace {
std::runtime_error failure(const std::string& action) {
    return std::runtime_error(action + ": Windows error " + std::to_string(GetLastError()));
}
std::wstring wide(const std::string& text) {
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), int(text.size()),
                                    nullptr, 0);
    if (count <= 0)
        throw failure("decode device identity");
    std::wstring result(size_t(count), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), int(text.size()),
                            result.data(), count) != count)
        throw failure("decode device identity");
    return result;
}
bool same(const std::wstring& a, const std::wstring& b) {
    return CompareStringOrdinal(a.c_str(), int(a.size()), b.c_str(), int(b.size()), TRUE) ==
           CSTR_EQUAL;
}
void keys(const Json& value, std::initializer_list<const char*> expected) {
    std::set<std::string> names;
    for (const auto& item : value.object()) {
        if (!names.insert(item.first).second)
            throw std::runtime_error("duplicate pair-record key");
    }
    std::set<std::string> required;
    for (auto name : expected)
        required.insert(name);
    if (names != required)
        throw std::runtime_error("unexpected pair-record fields");
}
std::string field(const Json& value, const char* name) {
    auto result = value.at(name).string();
    if (result.empty() || result.size() > 512 ||
        std::any_of(result.begin(), result.end(),
                    [](unsigned char c) { return c < 32 || c == 127; }))
        throw std::runtime_error("invalid pair-record text");
    return result;
}
bool canonical_port(const std::string& name) {
    return name.size() >= 4 && name.size() <= 16 && name.substr(0, 3) == "COM" && name[3] >= '1' &&
           name[3] <= '9' &&
           std::all_of(name.begin() + 4, name.end(), [](char c) { return c >= '0' && c <= '9'; });
}
struct Identity {
    std::string port, instance, hardware, provider, version;
    std::wstring interface_path;
};
struct DeviceSet {
    HDEVINFO value = SetupDiGetClassDevsW(&GUID_DEVINTERFACE_COMPORT, nullptr, nullptr,
                                          DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    DeviceSet() {
        if (value == INVALID_HANDLE_VALUE)
            throw failure("enumerate serial interfaces");
    }
    ~DeviceSet() {
        SetupDiDestroyDeviceInfoList(value);
    }
};
std::wstring property(HDEVINFO set, SP_DEVINFO_DATA& device, const DEVPROPKEY& key) {
    std::array<wchar_t, 2048> data{};
    DEVPROPTYPE type = 0;
    DWORD bytes = 0;
    if (!SetupDiGetDevicePropertyW(set, &device, &key, &type, reinterpret_cast<BYTE*>(data.data()),
                                   DWORD(sizeof data), &bytes, 0) ||
        type != DEVPROP_TYPE_STRING || bytes < sizeof(wchar_t) || bytes > sizeof data ||
        bytes % sizeof(wchar_t) || data[bytes / sizeof(wchar_t) - 1] != L'\0')
        throw failure("read virtual device property");
    return data.data();
}
std::array<Identity, 2> parse_pair(const Json& record) {
    keys(record, {"format", "provider", "provider_version", "endpoints"});
    if (field(record, "format") != "brewpi-emulator-serial-pair-v1" ||
        field(record, "provider") != "hhd-vspt" ||
        field(record, "provider_version") != "7.35.01.1760" ||
        record.at("endpoints").array().size() != 2)
        throw std::runtime_error("unsupported provisioned pair profile");
    std::array<Identity, 2> result;
    for (size_t i = 0; i < result.size(); ++i) {
        const auto& value = record.at("endpoints").array()[i];
        keys(value, {"port", "instance_id", "hardware_id", "driver_provider", "driver_version"});
        result[i] = {field(value, "port"),           field(value, "instance_id"),
                     field(value, "hardware_id"),    field(value, "driver_provider"),
                     field(value, "driver_version"), {}};
        if (!canonical_port(result[i].port) || result[i].hardware != "HHDVIRT\\UniversalSerial4" ||
            result[i].provider != "HHD Software Ltd." || result[i].version != "7.35.0.1753")
            throw std::runtime_error("pair record is not the qualified virtual-device profile");
    }
    if (result[0].port == result[1].port ||
        same(wide(result[0].instance), wide(result[1].instance)))
        throw std::runtime_error("pair endpoints must be distinct");
    return result;
}
void resolve(std::array<Identity, 2>& pair) {
    DeviceSet devices;
    std::array<unsigned, 2> found{};
    for (DWORD index = 0;; ++index) {
        SP_DEVICE_INTERFACE_DATA item{};
        item.cbSize = sizeof item;
        if (!SetupDiEnumDeviceInterfaces(devices.value, nullptr, &GUID_DEVINTERFACE_COMPORT, index,
                                         &item)) {
            if (GetLastError() == ERROR_NO_MORE_ITEMS)
                break;
            throw failure("enumerate serial interface");
        }
        DWORD needed = 0;
        SetupDiGetDeviceInterfaceDetailW(devices.value, &item, nullptr, 0, &needed, nullptr);
        if (GetLastError() != ERROR_INSUFFICIENT_BUFFER ||
            needed < sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) || needed > 65536)
            throw failure("size serial interface details");
        std::vector<BYTE> buffer(needed);
        auto* detail = reinterpret_cast<SP_DEVICE_INTERFACE_DETAIL_DATA_W*>(buffer.data());
        detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
        SP_DEVINFO_DATA device{};
        device.cbSize = sizeof device;
        if (!SetupDiGetDeviceInterfaceDetailW(devices.value, &item, detail, needed, nullptr,
                                              &device))
            throw failure("read serial interface details");
        HKEY key = SetupDiOpenDevRegKey(devices.value, &device, DICS_FLAG_GLOBAL, 0, DIREG_DEV,
                                        KEY_QUERY_VALUE);
        if (key == INVALID_HANDLE_VALUE)
            throw failure("read serial port name");
        std::array<wchar_t, 64> name{};
        DWORD bytes = DWORD(sizeof name);
        LSTATUS result =
            RegGetValueW(key, nullptr, L"PortName", RRF_RT_REG_SZ, nullptr, name.data(), &bytes);
        RegCloseKey(key);
        if (result != ERROR_SUCCESS || bytes < sizeof(wchar_t) || bytes > sizeof name ||
            bytes % sizeof(wchar_t) || name[bytes / sizeof(wchar_t) - 1] != L'\0')
            continue;
        for (size_t i = 0; i < pair.size(); ++i) {
            if (!same(name.data(), wide(pair[i].port)))
                continue;
            std::array<wchar_t, 512> instance{};
            if (!SetupDiGetDeviceInstanceIdW(devices.value, &device, instance.data(),
                                             DWORD(instance.size()), nullptr))
                throw failure("read serial device instance");
            std::array<wchar_t, 2048> hardware{};
            DWORD type = 0, size = 0;
            if (!SetupDiGetDeviceRegistryPropertyW(devices.value, &device, SPDRP_HARDWAREID, &type,
                                                   reinterpret_cast<BYTE*>(hardware.data()),
                                                   DWORD(sizeof hardware), &size) ||
                type != REG_MULTI_SZ || size < 2 * sizeof(wchar_t) || size > sizeof hardware ||
                size % sizeof(wchar_t) || hardware[size / sizeof(wchar_t) - 1] != L'\0' ||
                hardware[size / sizeof(wchar_t) - 2] != L'\0')
                throw failure("read serial hardware identity");
            if (!same(instance.data(), wide(pair[i].instance)) ||
                !same(hardware.data(), wide(pair[i].hardware)) ||
                property(devices.value, device, DEVPKEY_Device_DriverProvider) !=
                    wide(pair[i].provider) ||
                property(devices.value, device, DEVPKEY_Device_DriverVersion) !=
                    wide(pair[i].version))
                throw std::runtime_error(
                    "recorded COM name no longer matches its approved virtual device");
            pair[i].interface_path = detail->DevicePath;
            ++found[i];
        }
    }
    if (found[0] != 1 || found[1] != 1)
        throw std::runtime_error("recorded virtual pair is missing or ambiguous");
}
struct Operation {
    OVERLAPPED overlap{};
    std::vector<char> data;
    DWORD amount = 0;
    bool active = false, ready = false;
    Operation() {
        overlap.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        if (!overlap.hEvent)
            throw failure("create serial completion event");
    }
    ~Operation() {
        CloseHandle(overlap.hEvent);
    }
    void reset() {
        auto event = overlap.hEvent;
        overlap = {};
        overlap.hEvent = event;
        if (!ResetEvent(event))
            throw failure("reset serial completion event");
        amount = 0;
        ready = false;
    }
    void settle(HANDLE port) {
        if (!active)
            return;
        if (!GetOverlappedResult(port, &overlap, &amount, FALSE)) {
            if (GetLastError() == ERROR_IO_INCOMPLETE)
                return;
            throw failure("complete serial operation");
        }
        active = false;
        ready = true;
        if (amount > data.size())
            throw std::runtime_error("invalid serial completion length");
    }
};
} // namespace
struct WindowsSerial::Impl {
    HANDLE port = INVALID_HANDLE_VALUE;
    Operation incoming, outgoing;
    std::string peer_name;
    bool input_allowed = false;
    ~Impl() {
        if (port == INVALID_HANDLE_VALUE)
            return;
        CancelIoEx(port, nullptr);
        for (auto* operation : {&incoming, &outgoing}) {
            if (!operation->active)
                continue;
            // Never free an OVERLAPPED or its buffer while a driver owns it.
            // A broken driver that cannot cancel ends this process without
            // unwinding those buffers; normal cancellation completes below.
            if (WaitForSingleObject(operation->overlap.hEvent, 5000) != WAIT_OBJECT_0) {
                TerminateProcess(GetCurrentProcess(), 2);
                std::_Exit(2);
            }
            DWORD ignored = 0;
            if (!GetOverlappedResult(port, &operation->overlap, &ignored, FALSE) &&
                GetLastError() != ERROR_OPERATION_ABORTED) {
                TerminateProcess(GetCurrentProcess(), 2);
                std::_Exit(2);
            }
            operation->active = false;
        }
        CloseHandle(port);
    }
    void post_read() {
        if (!input_allowed || incoming.active || incoming.ready)
            return;
        incoming.reset();
        incoming.data.resize(1024);
        if (ReadFile(port, incoming.data.data(), DWORD(incoming.data.size()), &incoming.amount,
                     &incoming.overlap))
            incoming.ready = true;
        else if (GetLastError() == ERROR_IO_PENDING)
            incoming.active = true;
        else
            throw failure("start serial read");
    }
    unsigned events(bool have_output) {
        incoming.settle(port);
        outgoing.settle(port);
        return (input_allowed && incoming.ready ? readable : 0) |
               (have_output && (outgoing.ready || !outgoing.active) ? writable : 0);
    }
};
WindowsSerial::WindowsSerial(const Json& record, const std::string& selected)
    : impl(std::make_unique<Impl>()) {
    if (!canonical_port(selected))
        throw std::runtime_error("select an explicit canonical COM name");
    auto pair = parse_pair(record);
    resolve(pair);
    size_t index = selected == pair[0].port ? 0 : selected == pair[1].port ? 1 : 2;
    if (index == 2)
        throw std::runtime_error("selected COM endpoint is not in the provisioned pair");
    // Open the verified device interface, never an independently reassigned
    // DOS COM alias. Standard SetupAPI supplies this opaque path.
    impl->port = CreateFileW(pair[index].interface_path.c_str(), GENERIC_READ | GENERIC_WRITE, 0,
                             nullptr, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, nullptr);
    if (impl->port == INVALID_HANDLE_VALUE)
        throw failure("open approved virtual serial endpoint");
    auto after = parse_pair(record);
    resolve(after);
    for (size_t i = 0; i < pair.size(); ++i)
        if (!same(pair[i].interface_path, after[i].interface_path))
            throw std::runtime_error("virtual endpoint changed while opening");
    impl->peer_name = pair[1 - index].port;
    DCB dcb{};
    dcb.DCBlength = sizeof dcb;
    if (!GetCommState(impl->port, &dcb))
        throw failure("read serial settings");
    dcb.BaudRate = CBR_57600;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    dcb.fBinary = TRUE;
    dcb.fParity = FALSE;
    dcb.fOutxCtsFlow = FALSE;
    dcb.fOutxDsrFlow = FALSE;
    dcb.fDtrControl = DTR_CONTROL_ENABLE;
    dcb.fDsrSensitivity = FALSE;
    dcb.fTXContinueOnXoff = TRUE;
    dcb.fOutX = FALSE;
    dcb.fInX = FALSE;
    dcb.fErrorChar = FALSE;
    dcb.fNull = FALSE;
    dcb.fRtsControl = RTS_CONTROL_ENABLE;
    dcb.fAbortOnError = FALSE;
    if (!SetCommState(impl->port, &dcb))
        throw failure("configure serial endpoint");
    COMMTIMEOUTS timeouts{};
    timeouts.ReadIntervalTimeout = MAXDWORD;
    timeouts.ReadTotalTimeoutMultiplier = MAXDWORD;
    timeouts.ReadTotalTimeoutConstant = 100;
    if (!SetCommTimeouts(impl->port, &timeouts))
        throw failure("configure serial wait");
}
WindowsSerial::~WindowsSerial() = default;
unsigned WindowsSerial::wait(bool accept_input, bool have_output, unsigned milliseconds) {
    if (milliseconds > 1000)
        throw std::runtime_error("serial wait exceeds loop budget");
    impl->input_allowed = accept_input;
    impl->post_read();
    auto ready = impl->events(have_output);
    if (ready)
        return ready;
    std::array<HANDLE, 2> handles{};
    DWORD count = 0;
    if (accept_input && impl->incoming.active)
        handles[count++] = impl->incoming.overlap.hEvent;
    if (impl->outgoing.active)
        handles[count++] = impl->outgoing.overlap.hEvent;
    if (count) {
        DWORD result = WaitForMultipleObjects(count, handles.data(), FALSE, milliseconds);
        if (result == WAIT_FAILED)
            throw failure("wait for serial completion");
    } else
        Sleep(milliseconds);
    return impl->events(have_output);
}
size_t WindowsSerial::read(char* bytes, size_t capacity) {
    auto& operation = impl->incoming;
    if (!impl->input_allowed || !operation.ready)
        return 0;
    if (operation.amount > operation.data.size() || operation.amount > capacity)
        throw std::runtime_error("serial read capacity differs");
    std::memcpy(bytes, operation.data.data(), operation.amount);
    size_t result = operation.amount;
    operation.ready = false;
    return result;
}
size_t WindowsSerial::write(const char* bytes, size_t length) {
    auto& operation = impl->outgoing;
    operation.settle(impl->port);
    if (operation.ready) {
        if (length < operation.data.size() ||
            !std::equal(operation.data.begin(), operation.data.end(), bytes))
            throw std::runtime_error("pending serial write buffer changed before completion");
        size_t result = operation.amount;
        operation.ready = false;
        operation.data.clear();
        return result;
    }
    if (operation.active || !length)
        return 0;
    operation.reset();
    operation.data.assign(bytes, bytes + std::min<size_t>(length, 65536));
    if (WriteFile(impl->port, operation.data.data(), DWORD(operation.data.size()),
                  &operation.amount, &operation.overlap)) {
        if (operation.amount > operation.data.size())
            throw std::runtime_error("invalid serial write completion length");
        size_t result = operation.amount;
        operation.data.clear();
        return result;
    }
    if (GetLastError() != ERROR_IO_PENDING)
        throw failure("start serial write");
    operation.active = true;
    return 0;
}
bool WindowsSerial::drained() const noexcept {
    return !impl->outgoing.active && !impl->outgoing.ready;
}
const std::string& WindowsSerial::peer() const noexcept {
    return impl->peer_name;
}
} // namespace rmx
