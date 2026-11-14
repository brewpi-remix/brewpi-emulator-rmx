# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Provision separate, revision-pinned external clients/source citation inputs."""
import json
from pathlib import Path
import subprocess
import sys
from payload import preflight


def prepare(parent):
    preflight()
    pins=json.loads(Path(__file__).with_name('references.json').read_text())
    for name, revision in pins.items():
        path=Path(parent)/name
        if not path.exists():
            path.mkdir(parents=True)
            subprocess.run(['git','init',str(path)],check=True,stdout=subprocess.DEVNULL)
            org='brewpi-remix'
            subprocess.run(['git','-C',str(path),'fetch','--depth=1',
                            'https://github.com/'+org+'/'+name+'.git',revision],check=True)
            subprocess.run(['git','-C',str(path),'checkout','--detach',revision],check=True)
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if actual!=revision or subprocess.check_output(['git','-C',str(path),'status','--porcelain']):
            raise ValueError('wrong or modified reference: '+name)


if __name__=='__main__':
    prepare(sys.argv[1])
