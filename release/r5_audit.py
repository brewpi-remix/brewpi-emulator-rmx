# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Inventory exact R4 artifacts and assemble separate attributed R5 companions.

No original source/binary archive is changed. External legal texts and GNU
source packages retain their own terms and never enter original source trees.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile
from artifacts import ROOT, STEM, archive, canonical, sha, source_record, unpack, preflight
from local import verify_freeze


def require(condition,message):
    if not condition:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text())


def members(text):
    beginning=text.split('As-needed library included',1)[0].split('Merging program properties',1)[0]
    result=[]
    for library,member in re.findall(r'^([^\s]+\.a)\(([^)]+)\)',beginning,re.M):
        if (library=='librmx_lcd.a' and member=='lcd.cpp.o') or (library=='librmx_protocol.a' and member in ['json.cpp.o','engine.cpp.o','controller.cpp.o','controls.cpp.o','dynamics.cpp.o','storage.cpp.o']):kind='original-MIT'
        elif library=='/usr/lib/gcc/aarch64-linux-gnu/12/libgcc.a' and member in ['ldadd_4_4.o','lse-init.o']:kind='GCC-runtime-exception-3.1'
        else:raise ValueError('unclassified static archive member: '+library+'('+member+')')
        result.append(dict(archive=library,member=member,classification=kind))
    require(bool(result),'missing archive selection evidence')
    return result


def owners(text,headers):
    result={}
    for line in text.splitlines():
        owner,name=line.split(': ',1)
        require(name in headers and name not in result,'unexpected or duplicate header provider')
        package=owner.split(':')[0]
        require(package in ['libc6-dev','libgcc-12-dev','libstdc++-12-dev','linux-libc-dev'],'unclassified external header provider')
        result[name]=owner
    require(set(result)==set(headers),'missing external header provider')
    return result


def glibc_source(directory):
    dsc=directory/'glibc_2.36-9+deb12u14.dsc';text=dsc.read_text()
    require('\nSource: glibc\n' in text and '\nVersion: 2.36-9+deb12u14\n' in text,'wrong glibc source package')
    block=text.split('Checksums-Sha256:\n',1)[1].split('\nFiles:',1)[0]
    files={}
    for line in block.strip().splitlines():
        digest,size,name=line.split()
        require(Path(name).name==name,'unsafe source package name')
        path=directory/name;require(path.is_file() and not path.is_symlink() and path.stat().st_size==int(size) and sha(path)==digest,'source package checksum mismatch')
        require(name not in files,'duplicate distributor source')
        files[name]=dict(sha256=digest,bytes=int(size))
    require(set(files)=={'glibc_2.36.orig.tar.xz','glibc_2.36-9+deb12u14.debian.tar.xz'},'incomplete distributor source')
    files[dsc.name]=dict(sha256=sha(dsc),bytes=dsc.stat().st_size)
    notices={}
    paths=['csu/abi-note.c','csu/init.c']+[f'sysdeps/{arch}/{name}.S' for arch in ['aarch64','x86_64'] for name in ['start','crti','crtn']]
    with tarfile.open(directory/'glibc_2.36.orig.tar.xz','r:xz') as source:
        for name in paths:
            original=source.extractfile('glibc-2.36/'+name).read().decode()
            patched=(directory/'patched'/name).read_text()
            old=re.search(r'/\*.*?\*/',original,re.S).group(0)
            current=re.search(r'/\*.*?\*/',patched,re.S).group(0)
            require(old==current and 'Lesser General Public License' in current,'startup license changed or missing: '+name)
            if name not in ['csu/init.c','sysdeps/aarch64/start.S']:require('unlimited' in current and 'permission to link the compiled version' in ' '.join(current.split()),'startup linking permission missing')
            notices['glibc-startup/'+name.replace('/','-')+'.txt']=(current+'\n').encode()
    return files,notices


def binary_components(directory,manifest):
    data=read(directory/'audit.json')
    require(data.get('status')=='passed' and data['architecture']==manifest['architecture'] and data['source_snapshot_sha256']==manifest['source_snapshot_sha256'] and data['executable_sha256']==manifest['files']['bin/brewpi-emulator-rmx'],'wrong exact-byte binary audit')
    require(data.get('diagnostic_link_flags_only') is True,'unreviewed compilation method')
    require(data['inspector_sha256']==sha(ROOT/'release/audit_binary.py'),'unreviewed inspector identity')
    runtime=data['runtime_libraries']
    require(len(runtime)==5 and {Path(p).name for p in runtime}==({'libstdc++.so.6','libm.so.6','libgcc_s.so.1','libc.so.6'}|{'ld-linux-aarch64.so.1' if manifest['architecture']=='arm64' else 'ld-linux-x86-64.so.2'}),'incomplete runtime closure')
    require(all(v['provider'].split(':')[0] in ['libc6','libstdc++6','libgcc-s1'] and re.fullmatch('[a-f0-9]{64}',v['sha256']) and v['version'] for v in runtime.values()),'unknown runtime provider')
    static=members((directory/'link.map').read_text());providers=owners((directory/'header-owners.txt').read_text(),data['external_headers'])
    required={'Scrt1.o','crti.o','crtn.o','crtbeginS.o','crtendS.o','libgcc.a','libgcc_s.so','libstdc++.so','libc.so'}
    require(set(data['compiler_objects'])==required,'incomplete startup/compiler object inventory')
    notices=directory/'external-notices'
    expected={p+'-copyright.txt' for p in ['libc6','libc6-dev','libstdc++6','libstdc++-12-dev','libgcc-s1','libgcc-12-dev','gcc-12-base','linux-libc-dev']}|{'GPL-2.txt','GPL-3.txt','LGPL-2.1.txt'}
    require(set(data['external_notices'])==expected and {p.name for p in notices.iterdir()}==expected,'incomplete legal text inventory')
    for name,digest in data['external_notices'].items():require(sha(notices/name)==digest,'external notice changed')
    require('GCC RUNTIME LIBRARY EXCEPTION' in (notices/'libgcc-12-dev-copyright.txt').read_text(),'GCC exception missing')
    versions=dict(line.split('\t',1) for line in (directory/'packages.tsv').read_text().splitlines())
    for provider in set(providers.values()):require(provider in versions,'missing actual provider version')
    inputs={name:dict(value,provider=(directory/(name+'.owner.txt')).read_text().split(': ',1)[0]) for name,value in data['compiler_objects'].items()}
    for value in inputs.values():
        require(value['provider'] in versions,'missing link input provider version')
        value['provider_version']=versions[value['provider']]
    installed={name:dict(sha256=digest,mode=manifest['file_modes'][name],classification='original MIT implementation plus separately licensed compiler/system target-code contributions' if name.startswith('bin/') else 'original MIT project helper/document or generated unit') for name,digest in manifest['files'].items()}
    return dict(executable_sha256=data['executable_sha256'],installed_files=installed,static_archive_members=static,runtime_libraries=runtime,startup_and_link_inputs=inputs,external_headers={name:dict(sha256=digest,provider=providers[name],provider_version=versions[providers[name]]) for name,digest in data['external_headers'].items()},notice_hashes=data['external_notices'],link_map_sha256=sha(directory/'link.map'),elf_evidence_sha256=sha(directory/'elf.txt'),runtime_evidence_sha256=sha(directory/'runtime.txt'),provider_versions={p:versions[p] for p in sorted(set(providers.values()))})


def build(candidate,evidence,output):
    preflight();candidate=Path(candidate);evidence=Path(evidence);output=Path(output)
    require(not output.exists(),'refusing to replace R5 output');verify_freeze(candidate)
    source_archive=candidate/(STEM+'-source.tar.gz')
    with tempfile.TemporaryDirectory() as temporary:
        source=unpack(source_archive,Path(temporary)/'source',STEM+'-source');record=source_record(source)
        for name in record['files']:
            if Path(name).suffix in ['.cpp','.hpp','.py','.sh','.cmake','.yml'] or name=='CMakeLists.txt':
                require('SPDX-License-Identifier: MIT' in (source/name).read_text(), 'missing original source notice: '+name)
        license_bytes=(source/'LICENSE.md').read_bytes()
        source_metadata_sha=sha(source/'SOURCE.json')
    components={};notice_entries={'LICENSE-original-project.md':(license_bytes,0o644)}
    for arch in ['arm64','amd64']:
        manifest=read(candidate/(arch+'-payload-manifest.json'));directory=evidence/(arch+'-review2')
        components[arch]=binary_components(directory,manifest)
        require(components[arch]['provider_versions']['libc6-dev:'+arch]=='2.36-9+deb12u14','corresponding glibc source version mismatch')
        build_manifest=read(candidate/(arch+'-build-manifest.json'))
        require(read(directory/'audit.json')['source_archive_sha256']==sha(source_archive),'inspected source archive mismatch')
        components[arch]['build']={key:build_manifest[key] for key in ['compiler','linker','flags','image_id','prefix','source_date_epoch','package_inventory_sha256','package_archives_sha256']}
        components[arch]['required_external_libraries']=build_manifest['needed']
        components[arch]['elf_interpreter']=build_manifest['interpreter']
        components[arch]['versioned_symbols']=build_manifest['versioned_symbols']
        components[arch]['inspection_execution']='native arm64 Linux guest' if arch=='arm64' else 'emulated amd64 Linux guest on ARM64; native qualification retained separately'
        for path in (directory/'external-notices').iterdir():notice_entries['external/'+arch+'/'+path.name]=(path.read_bytes(),0o644)
    source_files,startup=glibc_source(evidence/'glibc-source')
    for name,data in startup.items():notice_entries['external/'+name]=(data,0o644)
    syscall=(evidence/'Linux-syscall-note.txt').read_bytes()
    require(b'SPDX-Exception-Identifier: Linux-syscall-note' in syscall and b'derived work' in syscall,'missing Linux syscall exception')
    notice_entries['external/Linux-syscall-note.txt']=(syscall,0o644)
    original_source={name:dict(entry,classification='original project source/data or standard project metadata; MIT') for name,entry in record['files'].items()}
    inventory=dict(schema=1,version='0.0.1-rc.1',source_commit=record['base_commit'],source_snapshot_sha256=record['source_snapshot_sha256'],original_project_license='MIT',original_source_files=original_source,generated_source_metadata=dict(path='SOURCE.json',sha256=source_metadata_sha,classification='original generated identity metadata'),binaries=components,glibc_corresponding_source=source_files,
        distribution_condition='Each source/binary archive requires both R5 NOTICES and glibc-source companions; original source plus GNU corresponding source permit library modification/relinking. No restriction on reverse engineering for debugging modifications.',
        glibc_startup='LGPL-2.1-or-later; linking permissions retained where present; AArch64 start.S and csu/init.c covered by complete corresponding-source delivery.',
        gcc_runtime='GPL-3.0-or-later WITH GCC-exception-3.1; ordinary GCC 12 compilation of independent MIT modules, no non-GPL GCC intermediate-representation optimization.',
        external_requirements='Compatible loader, libc/libm/libstdc++/libgcc supplied by the OS; Python for readiness and optional Python/Tcl/Tk/font for GUI remain external. No system library binary, firmware/host/panel/Fuscus code or font is bundled.')
    notice_entries['COMPONENTS.json']=(canonical(inventory),0o644)
    index=(ROOT/'release/r5-notice-index.md').read_bytes();require(b'glibc-source' in index and b'MIT' in index,'missing distribution instructions')
    notice_entries['NOTICE-INDEX.md']=(index,0o644)
    source_entries={name:((evidence/'glibc-source'/name).read_bytes(),0o644) for name in source_files}
    source_entries['README.md']=((ROOT/'release/r5-glibc-source-readme.md').read_bytes(),0o644)
    output.mkdir(parents=True)
    epoch=record['source_date_epoch']
    for name,entries in [('NOTICES',notice_entries),('glibc-source',source_entries)]:
        for label in ['first','second']:
            path=output/(label+'-'+STEM+'-'+name+'.tar.gz');archive(path,STEM+'-'+name,entries,epoch)
        require((output/('first-'+STEM+'-'+name+'.tar.gz')).read_bytes()==(output/('second-'+STEM+'-'+name+'.tar.gz')).read_bytes(),'nonreproducible R5 companion')
        (output/('first-'+STEM+'-'+name+'.tar.gz')).rename(output/(STEM+'-'+name+'.tar.gz'));(output/('second-'+STEM+'-'+name+'.tar.gz')).unlink()
    for path in candidate.glob('*.tar.gz'):shutil.copyfile(path,output/path.name)
    supplement_members={name:{path:dict(sha256=hashlib.sha256(data).hexdigest(),mode=mode,classification=('external source/metadata under original distributor terms' if name=='glibc-source' and path!='README.md' else 'external legal text under its own terms' if path.startswith('external/') else 'original R5 notice/index/metadata under MIT')) for path,(data,mode) in entries.items()} for name,entries in [('NOTICES',notice_entries),('glibc-source',source_entries)]}
    report=dict(schema=1,status='R5-artifact-audit-prepared',version='0.0.1-rc.1',qualified_source_commit=record['base_commit'],qualified_source_snapshot=record['source_snapshot_sha256'],artifacts={p.name:sha(p) for p in sorted(output.iterdir())},inventory=inventory,supplement_members=supplement_members,r6_complete=False,release_published=False)
    (output/'R5-AUDIT.json').write_bytes(canonical(report))
    (output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(output.iterdir())))
    return report


def verify(candidate,evidence,output):
    """Recreate from independent saved inputs, then validate complete archive members."""
    output=Path(output)
    expected={p.name for p in Path(candidate).glob('*.tar.gz')}|{STEM+'-'+kind+'.tar.gz' for kind in ['NOTICES','glibc-source']}|{'R5-AUDIT.json','SHA256SUMS'}
    require({p.name for p in output.iterdir()}==expected,'missing or unexpected R5 distribution member')
    require(all(p.is_file() and not p.is_symlink() for p in output.iterdir()),'nonregular R5 distribution member')
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);rebuilt=root/'rebuilt'
        report=build(candidate,evidence,rebuilt)
        for name in expected:require((output/name).read_bytes()==(rebuilt/name).read_bytes(),'R5 audit/distribution mismatch: '+name)
        for kind,inventory in report['supplement_members'].items():
            unpack(output/(STEM+'-'+kind+'.tar.gz'),root/kind,STEM+'-'+kind,inventory)
    return dict(status='passed',version=report['version'],qualified_source_commit=report['qualified_source_commit'],artifacts=report['artifacts'],r6_complete=False,release_published=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('candidate',type=Path);parser.add_argument('evidence',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args();result=(verify if args.verify else build)(args.candidate,args.evidence,args.output)
    print(json.dumps(dict(status=result['status'],artifacts=result['artifacts']),indent=2))
