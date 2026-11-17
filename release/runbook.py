# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Render the installed text guide from current operator/scenario documentation."""
import argparse
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def render(root, platform='linux'):
    root=Path(root).resolve()
    sections=[]
    if platform not in ['linux','macos','windows']:
        raise ValueError('unsupported operating guide platform')
    names=['docs/operation.md','config/README.md']
    if platform in ['macos','windows']:
        names.insert(0,'docs/'+platform+'.md')
    for name in names:
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

        markdown=path.read_text()
        if platform in ['macos','windows'] and name=='docs/operation.md':
            portable={'Command-line options','Optional local LCD','Local rotary and door controls',
                      'Scenarios and simulation time','Stop, restart, and checkpoints','Troubleshooting'}
            if platform=='windows':
                portable={'Local rotary and door controls','Scenarios and simulation time'}
            chunks=re.split(r'(?=^## )',markdown,flags=re.M)
            markdown='\n'.join(chunk.rstrip() for chunk in chunks
                               if chunk.splitlines()[0].removeprefix('## ') in portable)
        text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,markdown)
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
    for filename,platform in [('operation.txt','linux'),('macos.txt','macos'),('windows.txt','windows')]:
        target=ROOT/'docs'/filename;expected=render(ROOT,platform)
        if args.check:
            if not target.is_file() or target.read_text()!=expected:
                raise SystemExit('Installed guide is stale; run python3 release/runbook.py')
        else:target.write_text(expected)


if __name__=='__main__':main()
