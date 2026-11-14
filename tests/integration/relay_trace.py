# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Read only completed relay records/frames, scoped to an emulator session."""
import json


def records(path):
    if not path.exists():
        return []
    data = path.read_bytes()
    # A writer may be in the middle of its final line. Malformed completed
    # lines must still fail; do not hide corruption by dropping arbitrary rows.
    return [json.loads(line) for line in data.split(b'\n')[:-1]]


def wire(path, direction, session=None):
    return b''.join(bytes.fromhex(row['hex']) for row in records(path)
                    if row['direction']==direction and
                    (session is None or row['session']==session))


def frames(path, prefix, session=None):
    result=[]
    for line in wire(path,'controller',session).split(b'\r\n')[:-1]:
        if line.startswith(prefix.encode()+b':'):
            result.append(json.loads(line[2:].decode('cp437')))
    return result
