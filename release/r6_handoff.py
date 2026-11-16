# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Retain private RC evidence without changing or publishing candidate artifacts.

Inventory metadata is original MIT work. Captured external material keeps its
own terms; this private retention tree is never a public release payload.
"""
import argparse
import fnmatch
import hashlib
import gzip
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import tarfile
from artifacts import canonical, preflight, sha


def require(value,message):
    if not value:raise ValueError(message)


def relative(name):
    path=PurePosixPath(name)
    require(name and path.parts and not path.is_absolute() and str(path)==name and not any(p in ['..','.git'] for p in path.parts),'unsafe retention path: '+name)
    return path


def regular(root,name):
    path=root/str(relative(name))
    require(not any(p.is_symlink() for p in [path,*path.parents]),'symlink in retention input: '+name)
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),'nonregular retention input: '+name)
    return path


def select(root,config):
    root=Path(root).resolve();names=set()
    for name in config['roots']:
        relative(name);path=root/name
        require(path.exists() and not path.is_symlink(),'missing or symlinked retention root: '+name)
        candidates=[path] if path.is_file() else path.rglob('*')
        for file in candidates:
            rel=str(file.relative_to(root))
            if '__pycache__' in file.parts or any(fnmatch.fnmatchcase(rel,p) for p in config['exclude']):continue
            require(not file.is_symlink(),'symlink in selected tree: '+rel)
            if file.is_file():names.add(rel)
            else:require(file.is_dir(),'special retention input: '+rel)
    names.update(config.get('include_files',[]))
    for name in names:regular(root,name)
    for name,digest in config['anchors'].items():
        require(name in names and sha(regular(root,name))==digest,'missing/changed accepted evidence: '+name)
    return sorted(names)


def verify(destination,source=None):
    preflight();destination=Path(destination).absolute()
    require(not any(p.is_symlink() for p in [destination,*destination.parents]),'symlink retention destination')
    record=json.loads(regular(destination,'inventory.json').read_text());data=destination/'retained'
    names=record['files'];require(record.get('schema')==1 and bool(names),'empty or unsupported retention inventory');actual=set()
    for p in data.rglob('*'):
        require(not p.is_symlink() and (p.is_file() or p.is_dir()),'nonregular retained member')
        if p.is_file():actual.add(str(p.relative_to(data)))
    require(set(names)==actual,'missing or unexpected retained file')
    for name,row in names.items():
        path=regular(data,name)
        require(sha(path)==row['sha256'] and path.stat().st_size==row['bytes'] and stat.S_IMODE(path.stat().st_mode)==row['mode'],'retained file mismatch: '+name)
        if source:
            original=regular(Path(source).resolve(),name)
            require(sha(original)==row['sha256'] and stat.S_IMODE(original.stat().st_mode)==row['mode'],'original input changed: '+name)
    config=record['selection']
    for name,digest in config['anchors'].items():require(names.get(name,{}).get('sha256')==digest,'accepted evidence anchor mismatch')
    return dict(status='passed',files=len(names),bytes=sum(row['bytes'] for row in names.values()),inventory_sha256=sha(destination/'inventory.json'))


def retain(root,destination,config):
    preflight();root=Path(root).resolve();destination=Path(destination).absolute()
    require(not destination.exists(),'refusing to replace retention attempt')
    for name in config['roots']:
        require(not destination.is_relative_to(root/str(relative(name))),'retention destination overlaps selected inputs')
    require(not any(p.is_symlink() for p in [destination,*destination.parents]),'symlink retention destination parent')
    destination.mkdir(parents=True,mode=0o700)
    started=time.time()
    try:
        names=select(root,config);require(bool(names),'empty retention selection')
        total=sum((root/name).stat().st_size for name in names)
        require(shutil.disk_usage(destination).free>2*total+256*1024**2,'insufficient free space for retention and readback')
        files={}
        for name in names:
            path=regular(root,name);target=destination/'retained'/name
            before=dict(sha256=sha(path),bytes=path.stat().st_size,mode=stat.S_IMODE(path.stat().st_mode))
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
            require(sha(target)==before['sha256'] and sha(path)==before['sha256'],'input changed while copying: '+name)
            files[name]=before
        (destination/'inventory.json').write_bytes(canonical(dict(schema=1,role='private owner evidence; content retains its original terms',selection=config,files=files)))
        verified=verify(destination,root)
        result=dict(verified,started_utc=started,finished_utc=time.time(),no_publication=True,independent_backup=False)
    except BaseException as exc:
        (destination/'retention.json').write_bytes(canonical(dict(status='failed',started_utc=started,finished_utc=time.time(),error=type(exc).__name__+': '+str(exc),no_publication=True)))
        raise
    (destination/'retention.json').write_bytes(canonical(result));return result


def verify_backup(archive,destination):
    """Read every archived byte and gzip checksum; never extract untrusted paths."""
    destination=Path(destination);verify(destination)
    require(json.loads(regular(destination,'retention.json').read_text()).get('status')=='passed','retention attempt did not pass')
    record=json.loads((destination/'inventory.json').read_text())
    expected={'retained/'+n:row for n,row in record['files'].items()}
    for name in ['inventory.json','retention.json','source-history.bundle']:
        path=regular(destination,name);expected[name]=dict(sha256=sha(path),mode=stat.S_IMODE(path.stat().st_mode),bytes=path.stat().st_size)
    directories={str(parent) for n in expected for parent in PurePosixPath(n).parents if str(parent)!='.'}
    seen=set()
    with tarfile.open(archive,'r:gz') as stream:
        for member in stream:
            name=str(relative(member.name.rstrip('/')))
            require(member.isfile() or member.isdir(),'nonregular backup member')
            if member.isdir():
                require(name in directories,'unexpected backup directory');continue
            require(name in expected and name not in seen,'unexpected/duplicate backup file');seen.add(name)
            row=expected[name];digest=hashlib.sha256()
            with stream.extractfile(member) as file:
                for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
            require(digest.hexdigest()==row['sha256'] and member.mode==row['mode'] and member.size==row['bytes'],'backup byte/mode mismatch: '+name)
    require(seen==set(expected),'missing backup file')
    with gzip.open(archive,'rb') as stream:
        while stream.read(1024*1024):pass
    return dict(status='passed',files=len(seen),archive_sha256=sha(archive),inventory_sha256=sha(destination/'inventory.json'),independent_backup=False)


def backup(destination):
    destination=Path(destination);path=destination/'retained-evidence.tar.gz'
    require(not path.exists(),'refusing to replace backup')
    started=time.time()
    try:
        verify(destination)
        require(json.loads(regular(destination,'retention.json').read_text()).get('status')=='passed','retention attempt did not pass')
        regular(destination,'source-history.bundle')
        with tarfile.open(path,'x:gz',dereference=False) as stream:
            for name in ['retained','inventory.json','retention.json','source-history.bundle']:stream.add(destination/name,arcname=name)
        result=verify_backup(path,destination)
    except BaseException as exc:
        (destination/'backup-verification.json').write_bytes(canonical(dict(status='failed',started_utc=started,finished_utc=time.time(),error=type(exc).__name__+': '+str(exc),no_publication=True)))
        raise
    (destination/'backup-verification.json').write_bytes(canonical(result))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['retain','verify','backup','verify-backup']);parser.add_argument('destination',type=Path);parser.add_argument('--root',type=Path);parser.add_argument('--config',type=Path)
    args=parser.parse_args()
    if args.action=='retain':
        require(args.root and args.config,'retain requires --root and --config')
        report=retain(args.root,args.destination,json.loads(args.config.read_text()))
    elif args.action=='verify':report=verify(args.destination,args.root)
    elif args.action=='backup':report=backup(args.destination)
    else:report=verify_backup(args.destination/'retained-evidence.tar.gz',args.destination)
    print(json.dumps(report,indent=2))
