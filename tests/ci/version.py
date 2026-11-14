# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Read original application metadata without Git or a new runtime dependency."""
from pathlib import Path
import re


def application_version(root):
    text=(Path(root)/'cmake/version.cmake').read_text()
    values={}
    for key in ['MAJOR','MINOR','PATCH']:
        match=re.search(r'^set\(RMX_VERSION_'+key+r' ([0-9]+)\)$',text,re.M)
        if not match:raise ValueError('missing numeric application version')
        values[key]=match.group(1)
    match=re.search(r'^set\(RMX_VERSION_PRERELEASE "([a-z0-9.-]+)"\)$',text,re.M)
    if not match:raise ValueError('missing prerelease version')
    return '.'.join(values[key] for key in ['MAJOR','MINOR','PATCH'])+'-'+match.group(1)


def version_output(root):
    return 'brewpi-emulator-rmx '+application_version(root)
