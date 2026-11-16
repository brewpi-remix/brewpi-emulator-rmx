# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Render the installed text guide from current operator/scenario documentation."""
import argparse
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def render(root):
    root=Path(root).resolve()
    sections=[]
    for name in ['docs/operation.md','config/README.md']:
        path=root/name

        def link(match):
            label,destination=match.groups()
            if destination.startswith('https://'):
                return label+' ('+destination+')'
            target=(path.parent/destination.split('#',1)[0]).resolve()
            relative=target.relative_to(root).as_posix()
            if relative in ['LICENSE.md','THIRD_PARTY_NOTICES.md']:
                return label+' ('+relative+')'
            if relative=='config/README.md':
                return label+' (Scenario configuration below)'
            return label+' (source archive: '+relative+')'

        text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,path.read_text())
        text=re.sub(r'^#+ ','',text,flags=re.M)
        text=re.sub(r'^```[^\n]*\n','',text,flags=re.M)
        sections.append(text.rstrip())
    header=('BrewPi Emulator Remix\nCopyright 2026 Lee Bussy\nSPDX-License-Identifier: MIT\n\n'
            'Downloads: https://github.com/brewpi-remix/brewpi-emulator-rmx/releases\n\n')
    return header+'\n\n'.join(sections)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='fail if the installed guide is stale')
    args=parser.parse_args()
    target=ROOT/'docs/operation.txt';expected=render(ROOT)
    if args.check:
        if not target.is_file() or target.read_text()!=expected:
            raise SystemExit('Installed guide is stale; run python3 release/runbook.py')
    else:target.write_text(expected)


if __name__=='__main__':main()
