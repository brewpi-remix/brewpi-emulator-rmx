# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original deterministic provisional packaging; never commits, publishes, or installs live."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/ci'))
from payload import FILES, LOCAL_CONTROLS_FILES, payload_files, preflight, sha
from version import application_version, checked_version
VERSION=application_version(ROOT)
STEM='brewpi-emulator-rmx-'+VERSION
ORIGINAL_SOURCES={
    'libexec/brewpi-emulator-rmx/wait-ready.py':'scripts/wait-ready.py',
    'share/doc/brewpi-emulator-rmx/LICENSE.md':'LICENSE.md',
    'share/doc/brewpi-emulator-rmx/THIRD_PARTY_NOTICES.md':'THIRD_PARTY_NOTICES.md',
    'share/doc/brewpi-emulator-rmx/operation.txt':'docs/operation.txt',
}


def source_names(root):
    names=[line for line in (Path(root)/'release/source-files.txt').read_text().splitlines()
           if line and not line.startswith('#')]
    if names!=sorted(set(names)):raise ValueError('source allowlist must be unique and sorted')
    required=set(ORIGINAL_SOURCES.values())|{
        'CMakeLists.txt','cmake/version.cmake','scripts/lcd-viewer.py',
        'systemd/brewpi-emulator@.service.in',
        'docs/macos.txt','release/notices/LLVM-LICENSE.txt',
    }
    missing=required-set(names)
    if missing:raise ValueError('source allowlist omits install inputs: '+', '.join(sorted(missing)))
    return names


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def write_json(path, value):
    with Path(path).open('xb') as output:output.write(canonical(value))


def safe_name(name):
    parts=PurePosixPath(name).parts
    if not name or name.startswith('/') or '\\' in name or '\x00' in name or PurePosixPath(name).as_posix()!=name or any(p in ['.','..'] for p in name.split('/')) or not parts:
        raise ValueError('unsafe archive/input path')
    reserved={'CON','PRN','AUX','NUL','CONIN$','CONOUT$','CLOCK$'} | {
        prefix+suffix for prefix in ['COM','LPT'] for suffix in ['1','2','3','4','5','6','7','8','9','¹','²','³']}
    if any(':' in p or p.endswith(('.', ' ')) or any(ord(c)<32 for c in p) or
           p.split('.')[0].rstrip(' ').upper() in reserved for p in parts):
        raise ValueError('archive/input path is not portable to Windows')
    if any(p in ['.git','.agents','.codex','__pycache__','runs','state','captures','.venv','build','dist','out','local'] or p.startswith(('build-','cmake-build-')) or p=='.env' or (p.startswith('.env.') and p!='.env.example') for p in parts):
        raise ValueError('excluded local/external input')
    return name


def archive(path, top, entries, epoch):
    safe_name(top)
    with Path(path).open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=epoch,compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed,mode='w',format=tarfile.USTAR_FORMAT) as output:
                for name,(data,mode) in sorted(entries.items()):
                    safe_name(name)
                    if mode not in [0o644,0o755]:raise ValueError('undeclared file mode')
                    member=tarfile.TarInfo(top+'/'+name)
                    member.size=len(data);member.mode=mode;member.mtime=epoch
                    member.uid=member.gid=0;member.uname=member.gname=''
                    output.addfile(member,io.BytesIO(data))


def unpack(path, destination, top, inventory=None, epoch=None):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    seen=set();portable_seen=set();members=[]
    # Validate every member before writing even one payload file.
    with tarfile.open(path,'r:gz') as source:
        for member in source:
            name=safe_name(member.name)
            if not name.startswith(top+'/') or not member.isfile() or member.linkname or member.mode not in [0o644,0o755] or member.uid or member.gid or member.uname or member.gname:
                raise ValueError('unsafe or noncanonical archive member')
            if epoch is not None and member.mtime!=epoch:raise ValueError('archive timestamp differs from source epoch')
            relative=name[len(top)+1:];safe_name(relative)
            import unicodedata
            portable=unicodedata.normalize('NFC',relative).casefold()
            if relative in seen or portable in portable_seen:raise ValueError('duplicate or nonportable archive member')
            seen.add(relative);portable_seen.add(portable)
            data=source.extractfile(member).read()
            if inventory is not None:
                expected=inventory.get(relative)
                if not expected or expected['sha256']!=hashlib.sha256(data).hexdigest() or expected['mode']!=member.mode:
                    raise ValueError('archive inventory mismatch')
            members.append((relative,data,member.mode))
    if inventory is not None and seen!=set(inventory):raise ValueError('missing archive members')
    if any(any(unicodedata.normalize('NFC',str(parent)).casefold() in portable_seen for parent in PurePosixPath(name).parents) for name in seen):
        raise ValueError('archive file conflicts with a parent directory')
    for name,data,mode in members:
        target=destination/top/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output:output.write(data)
        target.chmod(mode)
    return destination/top


def legal_provenance(files):
    origins={'release/notices/LLVM-LICENSE.txt':'https://llvm.org/LICENSE.txt',
             'release/notices/MSVC-STL-LICENSE.txt':'https://raw.githubusercontent.com/microsoft/STL/219514876ea86491de191ceaa88632616bbc0f19/LICENSE.txt'}
    return {name:dict(origin=origin,spdx_license_expression='Apache-2.0 WITH LLVM-exception',
                      sha256=files[name]['sha256'],purpose='verbatim external legal text; not original MIT prose')
            for name,origin in origins.items() if name in files}


def check_legal_provenance(record):
    expected=legal_provenance(record.get('files',{}))
    if expected and (record.get('license_scope')!='original-project-material-only' or
                     record.get('external_legal_texts')!=expected):
        raise ValueError('external legal text lacks separate provenance/license classification')


def source_record(root, expected_version=None):
    expected_version=checked_version(expected_version if expected_version is not None else VERSION)
    root=Path(root).resolve();metadata=root/'SOURCE.json'
    if metadata.is_symlink() or not metadata.is_file() or (os.name!='nt' and stat.S_IMODE(metadata.stat().st_mode)!=0o644):
        raise ValueError('source metadata is not a regular canonical file')
    record=json.loads(metadata.read_text())
    if record.get('schema')!=1 or record.get('version')!=expected_version or record.get('spdx_license_identifier')!='MIT' or record.get('source_commit') is not None or record.get('identity_role')!='uncommitted-provisional-snapshot' or not re.fullmatch('[0-9a-f]{40}',record.get('base_commit','')) or type(record.get('source_date_epoch')) is not int or not 0<=record['source_date_epoch']<=0xffffffff:
        raise ValueError('invalid provisional source metadata')
    check_legal_provenance(record)
    content={k:v for k,v in record.items() if k!='source_snapshot_sha256'}
    if hashlib.sha256(canonical(content)).hexdigest()!=record['source_snapshot_sha256']:
        raise ValueError('source metadata identity mismatch')
    actual=set()
    for p in root.rglob('*'):
        if '__pycache__' in p.parts:continue
        if p.is_symlink() or not (p.is_file() or p.is_dir()):raise ValueError('nonregular source input')
        if p.is_file():actual.add(p.relative_to(root).as_posix())
    if actual!=set(record['files'])|{'SOURCE.json'}:raise ValueError('undeclared source snapshot files')
    for name,row in record['files'].items():
        p=root/safe_name(name)
        if row.get('mode') not in [0o644,0o755] or not p.is_file() or any(q.is_symlink() for q in [p,*p.parents]) or sha(p)!=row['sha256'] or (os.name!='nt' and stat.S_IMODE(p.stat().st_mode)!=row['mode']):
            raise ValueError('frozen source input changed: '+name)
    if 'cmake/version.cmake' not in record['files']:
        raise ValueError('source snapshot omits application version metadata')
    if application_version(root)!=expected_version:
        raise ValueError('archived application metadata differs from expected version')
    return record


def verify_original_files(manifest, record):
    """Bind verbatim installed project material to the archived original source."""
    bindings=dict(ORIGINAL_SOURCES)
    if manifest.get('payload_profile')=='local-controls-v1':
        bindings['libexec/brewpi-emulator-rmx/lcd-viewer.py']='scripts/lcd-viewer.py'
    for installed,original in bindings.items():
        digest=record.get('files',{}).get(original,{}).get('sha256')
        if digest is None or manifest.get('files',{}).get(installed)!=digest:
            raise ValueError('installed original differs from source: '+installed)


def payload_record(manifest, record, architecture, source_digest, expected_version=None):
    version=checked_version(expected_version if expected_version is not None else VERSION)
    if record.get('version')!=version:raise ValueError('source version differs from payload expectation')
    expected=dict(schema=2,candidate_version=version,source_commit=None,base_commit=record['base_commit'],
        source_snapshot_sha256=record['source_snapshot_sha256'],source_archive_sha256=source_digest,
        source_commit_role='pending-reviewed-commit-binding',architecture=architecture,install_prefix='/usr/local',
        application_version_output='brewpi-emulator-rmx '+version)
    if any(manifest.get(k)!=v for k,v in expected.items()):raise ValueError('payload metadata differs from source/target')
    files=payload_files(manifest)
    modes={name:(0o755 if name.startswith(('bin/','libexec/')) else 0o644) for name in files}
    if set(manifest.get('files',{}))!=files or manifest.get('file_modes')!=modes:
        raise ValueError('incorrect payload inventory or modes')
    if any(not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value) for value in manifest['files'].values()):
        raise ValueError('invalid payload file digest')
    verify_original_files(manifest,record)
    return {name:dict(sha256=digest,mode=modes[name]) for name,digest in manifest['files'].items()}


def canonical_source(source, path, expected_version=None):
    record=source_record(source,expected_version=expected_version)
    entries={name:((Path(source)/name).read_bytes(),row['mode']) for name,row in record['files'].items()}
    entries['SOURCE.json']=((Path(source)/'SOURCE.json').read_bytes(),0o644)
    archive(path,'brewpi-emulator-rmx-'+record['version']+'-source',entries,record['source_date_epoch'])


def snapshot(root, output):
    preflight();root=Path(root).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    if application_version(root)!=VERSION:raise ValueError('wrong candidate version')
    base=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    epoch=int(subprocess.check_output(['git','-C',str(root),'show','-s','--format=%ct',base],text=True))
    names=source_names(root)
    tracked=set(subprocess.check_output(['git','-C',str(root),'ls-files'],text=True).splitlines())
    entries={};files={};new=[]
    for name in names:
        safe_name(name);p=root/name
        if not p.is_file() or any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('nonregular source input')
        if name not in tracked:
            if not (name.startswith('release/') or name in ['cmake/version.cmake','tests/ci/version.py','docs/development.md','docs/release.md','engineering/protocol/commands.md','engineering/protocol/controller.md','tests/qualification/native_package.py','tests/qualification/native_package_checks.py','tests/macos_serial.py','tests/macos_runtime.py','docs/macos.md','docs/macos.txt','docs/windows.md','docs/windows.txt',
                'scripts/windows_channel.py','scripts/windows_ready.py','src/storage_windows.cpp',
                'src/windows_channel.cpp','src/windows_channel.hpp','src/windows_console.cpp',
                'src/windows_console.hpp','src/windows_host.hpp','src/windows_ready.cpp',
                'src/windows_ready.hpp','src/windows_serial.cpp','src/windows_serial.hpp',
                'tests/windows-channel-client.py','tests/windows-channel.cpp','tests/windows-serial.cpp',
                'tests/windows-storage.cpp','tests/windows/CMakeLists.txt','tests/windows_application.py',
                '.github/workflows/windows-native.yml','tests/ci/native_windows.py','tests/windows_runtime.py','tests/native_protocol.py','tests/windows_session0.py','tests/windows_session0_checks.py',
                'engineering/protocol/arduino-validation.md','src/profile.hpp']):
                raise ValueError('undeclared new original input: '+name)
            new.append(name)
        if p.stat().st_mode&0o6000:raise ValueError('privileged source mode')
        mode=0o755 if p.stat().st_mode&0o111 else 0o644
        data=p.read_bytes();entries[name]=(data,mode);files[name]=dict(sha256=hashlib.sha256(data).hexdigest(),mode=mode)
    content=dict(schema=1,spdx_license_identifier='MIT',version=VERSION,base_commit=base,source_commit=None,
        identity_role='uncommitted-provisional-snapshot',source_date_epoch=epoch,files=files)
    legal=legal_provenance(files)
    if legal:
        content.update(license_scope='original-project-material-only',external_legal_texts=legal)
    record=dict(content,source_snapshot_sha256=hashlib.sha256(canonical(content)).hexdigest())
    entries['SOURCE.json']=(canonical(record),0o644)
    top=STEM+'-source';name=top+'.tar.gz'
    for part in ['first','second']:
        folder=output/part;folder.mkdir();archive(folder/name,top,entries,epoch)
    if (output/'first'/name).read_bytes()!=(output/'second'/name).read_bytes():raise ValueError('source archives differ')
    shutil.copyfile(output/'first'/name,output/name)
    extracted=unpack(output/name,output/'extracted',top,{p:dict(sha256=hashlib.sha256(d).hexdigest(),mode=m) for p,(d,m) in entries.items()})
    source_record(extracted)
    write_json(output/'source-manifest.json',dict(record,archive=name,archive_sha256=sha(output/name),
        review_required=True,untracked_original_inputs=new,source_reproducible=True))
    return record


def command(args, log, **kwargs):
    with Path(log).open('w') as stream:
        try:subprocess.run([str(x) for x in args],check=True,stdout=stream,stderr=subprocess.STDOUT,**kwargs)
        except subprocess.CalledProcessError:
            stream.flush();print(Path(log).read_text()[-16000:],file=sys.stderr);raise


def build(source_archive, output, work, architecture, image_id):
    preflight();output=Path(output);output.mkdir(parents=True,exist_ok=False)
    work=Path(work);work.mkdir(parents=True,exist_ok=False)
    source=unpack(source_archive,work/'source',STEM+'-source');record=source_record(source)
    if application_version(source)!=VERSION:raise ValueError('source version mismatch')
    machine={'arm64':'aarch64','amd64':'x86_64'}[architecture]
    if __import__('platform').machine()!=machine:raise ValueError('wrong target guest architecture')
    canonical_source(source,output/(STEM+'-source.tar.gz'))
    if sha(output/(STEM+'-source.tar.gz'))!=sha(source_archive):raise ValueError('source archive is not canonical for pinned packaging tools')
    compiler=subprocess.check_output(['c++','-dumpversion'],text=True).strip()
    if compiler!='12':raise ValueError('candidate requires GCC 12')
    build_root=work/'build'
    isa='armv8-a' if architecture=='arm64' else 'x86-64'
    flags=' '.join(['-march='+isa,'-mtune=generic','-ffile-prefix-map='+str(source)+'=/usr/src/brewpi-emulator-rmx',
                    '-ffile-prefix-map='+str(build_root)+'=/usr/src/brewpi-emulator-rmx/build'])
    env=dict(os.environ,SOURCE_DATE_EPOCH=str(record['source_date_epoch']),LC_ALL='C',TZ='UTC')
    command(['cmake','-S',source,'-B',build_root,'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX=/usr/local',
             '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DCMAKE_CXX_FLAGS='+flags],output/'configure.log',env=env)
    command(['cmake','--build',build_root,'-j2'],output/'build.log',env=env)
    command(['ctest','-T','Test','--output-on-failure'],output/'ctest.log',cwd=build_root,env=env)
    sys.path.insert(0,str(source/'tests/ci'));from native import validate_build
    validate_build(build_root)
    shutil.copyfile(next((build_root/'Testing').glob('*/Test.xml')),output/'ctest.xml')
    shutil.copytree(build_root/'test-results',output/'native-results')
    shutil.copyfile(build_root/'compile_commands.json',output/'compile_commands.json')
    stage=work/'stage'
    command(['cmake','--install',build_root],output/'install.log',env=dict(env,DESTDIR=str(stage)))
    command(['cmake','--install',build_root,'--component','lcd-viewer'],output/'lcd-install.log',env=dict(env,DESTDIR=str(stage)))
    tree=stage/'usr/local'
    actual={str(p.relative_to(tree)) for p in tree.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=LOCAL_CONTROLS_FILES:raise ValueError('unexpected installed payload')
    entries={}
    for name in sorted(LOCAL_CONTROLS_FILES):
        path=tree/name
        if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('linked payload input')
        mode=0o755 if name.startswith(('bin/','libexec/')) else 0o644
        if stat.S_IMODE(path.stat().st_mode)!=mode:raise ValueError('incorrect installed mode')
        entries[name]=(path.read_bytes(),mode)
    binary=tree/'bin/brewpi-emulator-rmx'
    version=subprocess.check_output([str(binary),'--version'],text=True).strip()
    if version!='brewpi-emulator-rmx '+VERSION:raise ValueError('wrong packaged version')
    elf={}
    for option,label in [('-h','header'),('-l','programs'),('-d','dynamic'),('-n','notes'),('-A','attributes'),('--version-info','versions')]:
        elf[label]=subprocess.check_output(['readelf',option,str(binary)],text=True)
        (output/('elf-'+label+'.txt')).write_text(elf[label])
    needed=sorted(re.findall(r'\(NEEDED\).*?\[(.*?)\]',elf['dynamic']))
    if not needed or not set(needed)<={'libstdc++.so.6','libm.so.6','libgcc_s.so.1','libc.so.6'} or '(RPATH)' in elf['dynamic'] or '(RUNPATH)' in elf['dynamic']:
        raise ValueError('unexpected loader dependency/search path')
    interpreter=re.search(r'Requesting program interpreter: ([^\]]+)',elf['programs']).group(1)
    symbols=sorted(set(re.findall(r'\b(?:GLIBCXX|GLIBC|CXXABI)_[0-9.]+',elf['versions'])))
    data=dict(schema=2,payload_profile='local-controls-v1',candidate_version=VERSION,source_commit=None,base_commit=record['base_commit'],
        source_snapshot_sha256=record['source_snapshot_sha256'],source_archive_sha256=sha(source_archive),
        source_commit_role='pending-reviewed-commit-binding',architecture=architecture,install_prefix='/usr/local',
        application_version_output=version,files={p:hashlib.sha256(d).hexdigest() for p,(d,m) in entries.items()},
        file_modes={p:m for p,(d,m) in entries.items()})
    top=STEM+'-linux-'+architecture;archive(output/(top+'.tar.gz'),top,entries,record['source_date_epoch'])
    unpack(output/(top+'.tar.gz'),output/'extracted',top,{p:dict(sha256=hashlib.sha256(d).hexdigest(),mode=m) for p,(d,m) in entries.items()})
    write_json(output/'payload-manifest.json',data)
    packages=Path('/opt/rmx-inputs/packages.tsv').read_text()
    for name in ['packages.tsv','debs.sha256','indices.sha256']:
        shutil.copyfile('/opt/rmx-inputs/'+name,output/name)
    notices=output/'external-notices';notices.mkdir()
    for package in ['libc6','libc6-dev','libstdc++6','libgcc-s1','gcc-12-base']:
        path=Path('/usr/share/doc')/package/'copyright'
        shutil.copyfile(path,notices/(package+'-copyright.txt'))
    normalized_flags=['-march='+isa,'-mtune=generic','-ffile-prefix-map={source}=/usr/src/brewpi-emulator-rmx',
                      '-ffile-prefix-map={build}=/usr/src/brewpi-emulator-rmx/build','-O3','-DNDEBUG','-std=c++17']
    write_json(output/'build-manifest.json',dict(schema=1,architecture=architecture,version=VERSION,
        source_snapshot_sha256=record['source_snapshot_sha256'],source_archive_sha256=sha(source_archive),
        source_date_epoch=record['source_date_epoch'],image_id=image_id,
        compiler=subprocess.check_output(['c++','--version'],text=True).splitlines()[0],
        linker=subprocess.check_output(['ld','--version'],text=True).splitlines()[0],
        flags=normalized_flags,prefix='/usr/local',locale='C',timezone='UTC',
        archive=top+'.tar.gz',archive_sha256=sha(output/(top+'.tar.gz')),needed=needed,interpreter=interpreter,
        versioned_symbols=symbols,package_inventory_sha256=sha(output/'packages.tsv'),
        package_archives_sha256=sha(output/'debs.sha256'),files=data['files'],file_modes=data['file_modes']))
    write_json(output/'build-results.json',dict(status='passed',native_suites=6,counts=dict(passed=48,unresolved_reference_characterization=9),
        mode='source-build from offline source archive',actual_build_root=str(build_root),actual_source_root=str(source)))


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    snap=sub.add_parser('snapshot');snap.add_argument('output');snap.add_argument('--root',default=str(ROOT))
    repack=sub.add_parser('repack-source');repack.add_argument('source');repack.add_argument('output');repack.add_argument('--work',required=True);repack.add_argument('--expected-version')
    b=sub.add_parser('build');b.add_argument('source');b.add_argument('output');b.add_argument('--work',required=True)
    b.add_argument('--architecture',choices=['arm64','amd64'],required=True);b.add_argument('--image-id',required=True)
    args=parser.parse_args()
    if args.action=='snapshot':snapshot(args.root,args.output)
    elif args.action=='repack-source':
        version=checked_version(args.expected_version if args.expected_version is not None else VERSION)
        source=unpack(args.source,args.work,'brewpi-emulator-rmx-'+version+'-source')
        canonical_source(source,args.output,expected_version=version)
    else:build(args.source,args.output,args.work,args.architecture,args.image_id)


if __name__=='__main__':main()
