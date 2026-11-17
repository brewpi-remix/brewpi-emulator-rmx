# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Local Windows message-pipe client for the existing bounded LCD packets."""
import ctypes
from ctypes import wintypes as w
import os
import re

if os.name != 'nt':
    raise OSError('Windows message pipes require native Windows')

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                               w.DWORD, w.DWORD, w.HANDLE]
kernel.CreateFileW.restype = w.HANDLE
kernel.CloseHandle.argtypes = [w.HANDLE]
kernel.CloseHandle.restype = w.BOOL
kernel.SetNamedPipeHandleState.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD),
                                         ctypes.c_void_p, ctypes.c_void_p]
kernel.SetNamedPipeHandleState.restype = w.BOOL
kernel.GetNamedPipeServerProcessId.argtypes = [w.HANDLE, ctypes.POINTER(w.ULONG)]
kernel.GetNamedPipeServerProcessId.restype = w.BOOL
kernel.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD,
                           ctypes.POINTER(w.DWORD), ctypes.c_void_p]
kernel.ReadFile.restype = w.BOOL
kernel.WriteFile.argtypes = kernel.ReadFile.argtypes
kernel.WriteFile.restype = w.BOOL


class PacketPipe:
    def __init__(self, name, expected_parent_pid):
        self.handle = None
        prefix = '\\\\.\\pipe\\brewpi-emulator-'
        if not isinstance(name, str) or not name.startswith(prefix) or not re.fullmatch(
                '[0-9a-f]{32}', name[len(prefix):]):
            raise ValueError('invalid private LCD channel name')
        if type(expected_parent_pid) is not int or not 0 < expected_parent_pid < 2**32:
            raise ValueError('invalid LCD parent identity')
        # Identification-level QoS prevents server impersonation of this client.
        handle = kernel.CreateFileW(name, 0xc0000000, 0, None, 3, 0x110000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle
        try:
            actual = w.ULONG()
            if not kernel.GetNamedPipeServerProcessId(handle, ctypes.byref(actual)):
                raise ctypes.WinError(ctypes.get_last_error())
            if actual.value != expected_parent_pid:
                raise OSError('LCD pipe server is not the expected parent')
            mode = w.DWORD(3)  # PIPE_READMODE_MESSAGE | PIPE_NOWAIT
            if not kernel.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close()
            raise

    def setblocking(self, enabled):
        if enabled:
            raise ValueError('LCD packet pipe is nonblocking')

    def send(self, data):
        if self.handle is None:
            raise OSError('LCD packet pipe is closed')
        if not isinstance(data, bytes) or not 0 < len(data) <= 4096:
            raise ValueError('invalid LCD packet length')
        buffer = ctypes.create_string_buffer(data)
        count = w.DWORD()
        if not kernel.WriteFile(self.handle, buffer, len(data), ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if count.value == 0:
            raise BlockingIOError('LCD packet buffer is full')
        if count.value != len(data):
            raise OSError('LCD packet write was not atomic')
        return count.value

    def recv(self, capacity):
        if self.handle is None:
            raise OSError('LCD packet pipe is closed')
        if type(capacity) is not int or not 0 < capacity <= 4097:
            raise ValueError('invalid LCD receive capacity')
        buffer = ctypes.create_string_buffer(capacity)
        count = w.DWORD()
        if not kernel.ReadFile(self.handle, buffer, capacity, ctypes.byref(count), None):
            code = ctypes.get_last_error()
            if code == 232:  # ERROR_NO_DATA on an empty NOWAIT pipe
                raise BlockingIOError('no LCD message available')
            if code == 109:  # ERROR_BROKEN_PIPE
                return b''
            if code == 234:  # ERROR_MORE_DATA: reject, never parse a partial packet
                raise ValueError('oversized LCD message')
            raise ctypes.WinError(code)
        if not 0 < count.value <= 4096:
            raise ValueError('invalid LCD message length')
        return buffer.raw[:count.value]

    def close(self):
        if self.handle is not None:
            kernel.CloseHandle(self.handle)
            self.handle = None
