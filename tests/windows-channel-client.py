# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Focused native pipe proof; not GUI or controller acceptance."""
import argparse
import importlib.util
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True

p = argparse.ArgumentParser()
p.add_argument('--release', required=True, type=Path)
p.add_argument('--module', required=True)
p.add_argument('--pipe', required=True)
p.add_argument('--server-pid', required=True, type=int)
a = p.parse_args()
spec = importlib.util.spec_from_file_location('rmx_windows_channel', a.module)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
channel = module.PacketPipe(a.pipe, a.server_pid)
try:
    # The server sends nothing before receiving the first request.
    try:
        channel.recv(4097)
    except BlockingIOError:
        pass
    else:
        raise AssertionError('empty pipe receive did not return immediately')
    for i in range(100):
        payload = i.to_bytes(2, 'little') + bytes(range(256)) * 4
        end = time.monotonic() + 5
        while True:
            try:
                channel.send(payload)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise TimeoutError('native pipe send')
                time.sleep(.001)
        while True:
            try:
                reply = channel.recv(4097)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise TimeoutError('native pipe receive')
                time.sleep(.001)
        assert reply == payload
    channel.send(b'backpressure-ready')
    end = time.monotonic() + 10
    while not a.release.exists():
        if time.monotonic() > end:
            raise TimeoutError('backpressure test barrier')
        time.sleep(.001)
    count = 0
    while True:
        try:
            reply = channel.recv(4097)
        except BlockingIOError:
            if time.monotonic() > end:
                raise TimeoutError('backpressure drain')
            time.sleep(.001)
            continue
        if reply == b'end':
            break
        assert reply == b'z' * 4096
        count += 1
    channel.send(('drained:' + str(count)).encode())
    while True:
        try:
            assert channel.recv(4097) == b'ack-drained'
            break
        except BlockingIOError:
            if time.monotonic() > end:
                raise TimeoutError('backpressure completion acknowledgement')
            time.sleep(.001)
    try:
        channel.send(bytes(4097))
    except ValueError:
        pass
    else:
        raise AssertionError('oversized packet accepted')
finally:
    channel.close()
