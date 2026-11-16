# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Read original application metadata without Git or a new runtime dependency."""
from pathlib import Path
import re


def checked_version(value):
    if not isinstance(value,str):raise ValueError('invalid application version')
    match=re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?',value)
    if not match:raise ValueError('invalid application version')
    suffix=match.group(4)
    if suffix and any(part.isdigit() and len(part)>1 and part.startswith('0') for part in suffix.split('.')):
        raise ValueError('invalid numeric prerelease identifier')
    return value


def application_version(root):
    text=(Path(root)/'cmake/version.cmake').read_text()
    values={}
    for line in text.splitlines():
        line=line.strip()
        if not line:continue
        if line.startswith('#'):
            if re.match(r'#\[=*\[',line):raise ValueError('multiline comments are not application metadata')
            continue
        match=re.fullmatch(r'set\(RMX_VERSION_(MAJOR|MINOR|PATCH) ([0-9]+)\)',line)
        if match:key,value=match.groups()
        else:
            match=re.fullmatch(r'set\(RMX_VERSION_(PRERELEASE) "([0-9A-Za-z.-]*)"\)',line)
            if not match:raise ValueError('noncanonical application version declaration')
            key,value=match.groups()
        if key in values:raise ValueError('duplicate application version declaration')
        values[key]=value
    if set(values)!={'MAJOR','MINOR','PATCH','PRERELEASE'}:raise ValueError('missing application version declaration')
    suffix=values['PRERELEASE']
    return checked_version('.'.join(values[key] for key in ['MAJOR','MINOR','PATCH'])+('-'+suffix if suffix else ''))


def version_output(root):
    return 'brewpi-emulator-rmx '+application_version(root)
