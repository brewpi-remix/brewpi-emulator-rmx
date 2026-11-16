# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Inspect an exact-byte reproduction using extra linker diagnostics only.

Runs in the existing disposable pinned build image. External object/license
captures remain separate from original source and shipping payloads.
"""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
from artifacts import STEM, sha, source_record, unpack


def command(arguments, output, **kwargs):
    result=subprocess.run(list(map(str,arguments)),capture_output=True,text=True,check=True,**kwargs)
    output.write_text(result.stdout+result.stderr)
    return result.stdout


def audit(source_archive, output, architecture, expected):
    output=Path(output);work=Path('/build/r5');work.mkdir();output.mkdir(exist_ok=True)
    source=unpack(source_archive,work/'source',STEM+'-source');record=source_record(source);build=work/'build'
    isa='armv8-a' if architecture=='arm64' else 'x86-64'
    flags=' '.join(['-march='+isa,'-mtune=generic','-ffile-prefix-map='+str(source)+'=/usr/src/brewpi-emulator-rmx','-ffile-prefix-map='+str(build)+'=/usr/src/brewpi-emulator-rmx/build'])
    env=dict(os.environ,SOURCE_DATE_EPOCH=str(record['source_date_epoch']),LC_ALL='C',TZ='UTC')
    command(['cmake','-S',source,'-B',build,'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr/local','-DBUILD_TESTING=OFF','-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_EXE_LINKER_FLAGS=-Wl,-Map=/output/link.map,--cref,--trace'],output/'configure.log',env=env)
    command(['cmake','--build',build,'--target','brewpi-emulator-rmx','-j2'],output/'build.log',env=env)
    binary=build/'brewpi-emulator-rmx'
    if sha(binary)!=expected:raise ValueError('diagnostic reproduction differs from qualified executable')
    shutil.copyfile(build/'CMakeFiles/brewpi-emulator-rmx.dir/link.txt',output/'link-command.txt')
    for label,args in [('elf',['readelf','-h','-l','-d','-n','--version-info',binary]),('symbols',['nm','-C',binary]),('undefined',['nm','-D','-C','--undefined-only',binary]),('runtime',['ldd',binary])]:
        command(args,output/(label+'.txt'))
    runtime={}
    for name in sorted(set(re.findall(r'(/[^\s()]+)',(output/'runtime.txt').read_text()))):
        path=Path(name);resolved=path.resolve()
        owner=None
        for possible in [path,resolved]:
            result=subprocess.run(['dpkg-query','-S',str(possible)],capture_output=True,text=True)
            if result.returncode==0:
                owner=result.stdout.split(': ',1)[0];break
        if owner is None:raise ValueError('unclassified runtime library: '+name)
        version=subprocess.check_output(['dpkg-query','-W','-f=${Version}',owner],text=True)
        runtime[name]=dict(resolved=str(resolved),sha256=sha(resolved),provider=owner,version=version)
    objects={}
    for name in ['Scrt1.o','crti.o','crtbeginS.o','crtendS.o','crtn.o','libgcc.a','libgcc_s.so','libstdc++.so','libc.so']:
        path=Path(subprocess.check_output(['c++','-print-file-name='+name],text=True).strip()).resolve()
        objects[name]=dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size)
        command(['dpkg-query','-S',str(path)],output/(name+'.owner.txt'))
    notices=output/'external-notices';notices.mkdir()
    for name in ['LGPL-2.1','GPL-2','GPL-3']:
        shutil.copyfile('/usr/share/common-licenses/'+name,notices/(name+'.txt'))
    for package in ['libc6','libc6-dev','libstdc++6','libstdc++-12-dev','libgcc-s1','libgcc-12-dev','gcc-12-base','linux-libc-dev']:
        shutil.copyfile('/usr/share/doc/'+package+'/copyright',notices/(package+'-copyright.txt'))
    command(['dpkg-query','-W'],output/'packages.tsv')
    dependencies=[]
    for path in build.rglob('*.o.d'):
        for token in path.read_text().replace('\\\n',' ').split():
            if token.startswith('/usr/') and Path(token).is_file():dependencies.append(token)
    headers={name:sha(name) for name in sorted(set(dependencies))}
    command(['dpkg-query','-S',*headers],output/'header-owners.txt')
    (output/'audit.json').write_text(json.dumps(dict(status='passed',architecture=architecture,executable_sha256=expected,source_snapshot_sha256=record['source_snapshot_sha256'],diagnostic_link_flags_only=True,inspector_sha256=sha(__file__),source_archive_sha256=sha(source_archive),runtime_libraries=runtime,compiler_objects=objects,external_headers=headers,external_notices={p.name:sha(p) for p in sorted(notices.iterdir())}),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output');parser.add_argument('architecture',choices=['amd64','arm64']);parser.add_argument('expected')
    args=parser.parse_args();audit(args.source,args.output,args.architecture,args.expected)
