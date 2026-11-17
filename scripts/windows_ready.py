# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Verify private Windows readiness without opening a COM endpoint."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import secrets
import time


def read_private(path):
    # Validate the same open file's owner, ACL, type, and bounded contents.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    security = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                   w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetFileType.argtypes = [w.HANDLE]
    kernel.GetFileType.restype = w.DWORD
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD,
                               ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    security.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    security.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            w.DWORD, ctypes.POINTER(w.DWORD)]
    security.GetSecurityInfo.argtypes = [w.HANDLE, ctypes.c_int, w.DWORD,
                                         ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                         ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
                                         ctypes.POINTER(ctypes.c_void_p)]
    security.GetSecurityInfo.restype = w.DWORD
    security.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    security.GetAce.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    class ACL(ctypes.Structure):
        _fields_ = [('revision', w.BYTE), ('reserved', w.BYTE), ('size', w.WORD),
                    ('count', w.WORD), ('reserved2', w.WORD)]
    handle = kernel.CreateFileW(str(Path(path).absolute()), 0x80020000, 7, None, 3,
                                0x00200000, None)  # read + READ_CONTROL, no reparse traversal
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    token, descriptor = w.HANDLE(), ctypes.c_void_p()
    try:
        # FileAttributeTagInfo: reject directories and any reparse leaf.
        kernel.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, w.DWORD]
        info = (w.DWORD * 2)()
        if (kernel.GetFileType(handle) != 1 or
                not kernel.GetFileInformationByHandleEx(handle, 9, info, ctypes.sizeof(info)) or
                info[0] & (0x10 | 0x400)):
            raise OSError('readiness record is not a regular file')
        if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise ctypes.WinError(ctypes.get_last_error())
        size = w.DWORD()
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        user = ctypes.create_string_buffer(size.value)
        if not security.GetTokenInformation(token, 1, user, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        current_sid = ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p))[0]
        owner, acl = ctypes.c_void_p(), ctypes.c_void_p()
        code = security.GetSecurityInfo(handle, 1, 5, ctypes.byref(owner), None,
                                         ctypes.byref(acl), None, ctypes.byref(descriptor))
        if code:
            raise ctypes.WinError(code)
        if not owner or not acl or not security.EqualSid(owner, current_sid):
            raise OSError('readiness owner differs from this account')
        count = ctypes.cast(acl, ctypes.POINTER(ACL)).contents.count
        if not count:
            raise OSError('readiness record has no private access entries')
        for i in range(count):
            ace = ctypes.c_void_p()
            if not security.GetAce(acl, i, ctypes.byref(ace)):
                raise ctypes.WinError(ctypes.get_last_error())
            header = (w.BYTE * 4).from_address(ace.value)
            if header[0] != 0 or header[1] & 0x18 or not security.EqualSid(ace.value + 8, current_sid):
                raise OSError('readiness record is not private to this account')
        data = ctypes.create_string_buffer(4097)
        amount = w.DWORD()
        if not kernel.ReadFile(handle, data, len(data), ctypes.byref(amount), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if amount.value > 4096:
            raise ValueError('oversized readiness record')
        return json.loads(data.raw[:amount.value].decode('utf-8'))
    finally:
        if descriptor:
            kernel.LocalFree(descriptor)
        if token:
            kernel.CloseHandle(token)
        kernel.CloseHandle(handle)


def wait_ready(serial, pid, timeout, state):
    if os.name != 'nt' or pid <= 0 or not 0 < timeout <= 300 or not state:
        raise ValueError('Windows requires positive PID, timeout in (0,300], and --state')
    import importlib.util
    import sys
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(
        'rmx_windows_channel', Path(__file__).with_name('windows_channel.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    deadline = time.monotonic() + timeout
    last = 'endpoint not published'
    while time.monotonic() < deadline:
        channel = None
        try:
            record = read_private(str(state) + '.ready')
            if (record.get('format') != 'brewpi-emulator-ready-v1' or
                    record.get('serial') != serial or record.get('pid') != pid):
                raise ValueError('readiness publication does not match this process and endpoint')
            channel = module.PacketPipe(record['pipe'], pid)
            nonce = secrets.token_hex(16)
            channel.send(json.dumps({'nonce': nonce}).encode())
            while time.monotonic() < deadline:
                try:
                    response = json.loads(channel.recv(4097))
                    if response != {'format': 'brewpi-emulator-ready-v1', 'nonce': nonce,
                                    'generation': record['generation'], 'serial': serial}:
                        raise ValueError('readiness challenge response differs')
                    return
                except BlockingIOError:
                    time.sleep(.02)
            raise TimeoutError('readiness response timed out')
        except (OSError, ValueError, KeyError) as exc:
            last = str(exc)
        finally:
            if channel:
                channel.close()
        time.sleep(.02)
    raise TimeoutError('serial readiness timed out: ' + last)
