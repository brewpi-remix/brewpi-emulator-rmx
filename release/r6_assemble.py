# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Assemble a review handoff from reconciled records; never publish or rebuild."""
import argparse
import json
from pathlib import Path
import shutil
import stat
import time
from artifacts import canonical, preflight, sha, source_record
from r6_handoff import regular, require

STEM='brewpi-emulator-rmx-0.0.1-rc.1'


def verify(output):
    preflight();output=Path(output).absolute()
    record=json.loads(regular(output,'HANDOFF.json').read_text());files=record['files']
    require(record['status']=='R6-ready-for-owner-review' and record['owner_review_pending'] is True and record['version']=='0.0.1-rc.1','wrong handoff disposition')
    require(record['candidate_commit']=='f717d36364778ad48cd28bb5ae5a221c29c5db49' and record['review_source_commit'] is None and record['review_baseline']=='cad8a2a71922efa99b3431ca75c12096249a3a0e' and all(record[k] is False for k in ['committed','pushed','tagged','published']),'unsupported source/publication claim')
    paths=list(output.rglob('*'));require(all(not p.is_symlink() and (p.is_file() or p.is_dir()) and not (p.stat().st_mode&0o6000) for p in paths),'nonregular or privileged handoff member')
    require({str(p.relative_to(output)) for p in paths if p.is_file()}==set(files)|{'HANDOFF.json','SHA256SUMS'},'missing or unexpected handoff file')
    for name,row in files.items():
        path=regular(output,name)
        require(sha(path)==row['sha256'] and stat.S_IMODE(path.stat().st_mode)==row['mode'],'handoff file mismatch: '+name)
    source=source_record(output/'review')
    require(source['source_commit'] is None and source['base_commit']==record['review_baseline'] and source['source_snapshot_sha256']==record['review_snapshot'],'review inputs misidentified as candidate source')
    audit=json.loads((output/'packages/R5-AUDIT.json').read_text())
    accepted=json.loads((output/'manifests/r5-acceptance.json').read_text())
    names={STEM+'-'+kind+'.tar.gz' for kind in ['source','linux-amd64','linux-arm64','NOTICES','glibc-source']}
    require(set(audit['artifacts'])==names and accepted['status']=='R5-accepted' and accepted['artifacts']==audit['artifacts'],'missing required licensing/source/binary companion')
    require({p.name for p in (output/'packages').iterdir()}==names|{'R5-AUDIT.json','SHA256SUMS'},'unexpected package closure')
    package_sums=''.join(sha(output/'packages'/name)+'  '+name+'\n' for name in sorted(names|{'R5-AUDIT.json'}))
    require((output/'packages/SHA256SUMS').read_text()==package_sums,'R5 package checksum inventory mismatch')
    require(audit['qualified_source_commit']==record['candidate_commit'] and audit['qualified_source_snapshot']==record['candidate_snapshot'] and len(audit['artifacts'])==5,'wrong R5 candidate closure')
    for name,digest in audit['artifacts'].items():require(sha(regular(output/'packages',name))==digest,'changed qualified archive')
    expected=''.join(sha(output/name)+'  '+name+'\n' for name in sorted(set(files)|{'HANDOFF.json'}))
    require((output/'SHA256SUMS').read_text()==expected,'handoff checksum inventory mismatch')
    return dict(status='passed',files=len(files)+2,version=record['version'],candidate_commit=record['candidate_commit'],review_snapshot=record['review_snapshot'],handoff_sha256=sha(output/'HANDOFF.json'),checksums_sha256=sha(output/'SHA256SUMS'),owner_review_pending=True)


def _build(review,store,index,output,owned):
    preflight();review=Path(review);store=Path(store);output=Path(output).absolute();data=store/'retained'
    require(not output.exists() and not any(p.is_symlink() for p in [output,*output.parents]),'handoff destination already exists or has a symlink parent')
    source=source_record(review);context=json.loads(Path(index).read_text())
    require(source['source_commit'] is None and source['base_commit']=='cad8a2a71922efa99b3431ca75c12096249a3a0e','wrong uncommitted R6 input baseline')
    require(context['status']=='R6-evidence-reconciled-for-owner-review' and context['version']=='0.0.1-rc.1' and context['owner_review_pending'] is True,'unreconciled R6 evidence index')
    candidate=data/'dist/r4-final-review'/STEM;packages=data/'dist/r5-review2'/STEM
    accepted=json.loads((data/'dist/r5-review2/R5-ACCEPTANCE.json').read_text());association=json.loads((data/'dist/r4-final-review/acceptance-0.0.1-rc.1/source-association.json').read_text())
    require(accepted['status']=='R5-accepted' and context['candidate_commit']==accepted['qualified_source_commit']==association['source_commit'],'R4/R5/context source mismatch')
    require(json.loads((store/'retention.json').read_text())['status']=='passed' and json.loads((store/'backup-verification.json').read_text())['status']=='passed','incomplete evidence retention/backup')
    require(json.loads((store/'inventory.json').read_text())['selection']==json.loads((review/'release/r6-inputs.json').read_text()),'retention selection differs from reviewed required inputs')
    output.mkdir(parents=True,mode=0o700);owned['output']=output;origins={}
    def copy(path,name,role):
        require(path.is_file() and not path.is_symlink(),'missing or nonregular handoff input')
        destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,destination);origins[name]=role
    for path in packages.iterdir():copy(path,'packages/'+path.name,'unchanged qualified R5 distribution; external components retain their terms')
    manifest_names=['source-manifest.json','environment-lock.json','reproducibility.json']
    for arch in ['arm64','amd64']:
        manifest_names += [arch+'-'+n for n in ['payload-manifest.json','build-manifest.json','packages.tsv','debs.sha256','indices.sha256','runtime-packages.tsv','runtime-debs.sha256']]
    for name in manifest_names:copy(candidate/name,'manifests/'+name,'original R4 input/build/runtime manifest')
    for path in (data/'dist/r4-final-review/acceptance-0.0.1-rc.1').iterdir():copy(path,'manifests/r4-acceptance/'+path.name,'original historical R4 acceptance packet; R5/R6 fields retain their creation-time status')
    copy(data/'dist/r4-final-review/acceptance-0.0.1-rc.1/source-association.json','manifests/source-association.json','exact qualified original-source binding')
    copy(data/'dist/r5-review2/R5-ACCEPTANCE.json','manifests/r5-acceptance.json','original R5 acceptance; historical R6 field unchanged')
    for path,name in [(data/'runs/controls-hosted-f717d36/verification.json','candidate-ci.json'),(data/'runs/r5-20261116/hosted/verification.json','tooling-ci.json'),(store/'retention.json','retention.json'),(store/'backup-verification.json','backup-verification.json')]:copy(path,'manifests/'+name,'original verification summary; raw private evidence excluded')
    for name in list(source['files'])+['SOURCE.json']:copy(review/name,'review/'+name,'uncommitted original MIT R6 review inputs; not qualified candidate source')
    for name in ['rc1-guide.md','rc1-release-notes.md']:copy(review/'docs'/name,name,'portable original MIT handoff prose')
    copy(Path(index),'evidence-index.json','new reconciled R6 evidence/context index; original executed identities preserved')
    (output/'REVIEW.md').write_text('# Review handoff for 0.0.1-rc.1\n\nRead the [dossier](review/engineering/development/software-release-rc1-dossier.md), [candidate notes](rc1-release-notes.md), and [guide](rc1-guide.md). Verify SHA256SUMS and packages/SHA256SUMS. All five qualified archives are under packages/. The review/ tree is an uncommitted R6 documentation/helper snapshot on cad8a2a, not the candidate source; use packages/ for the qualified f717d36 source. HANDOFF.json separates those identities and maps the exact manifests/evidence. Private raw evidence is retained outside this handoff in the owner store described by the dossier. Stop for owner review; no commit, push, tag, or publication is approved.\n')
    origins['REVIEW.md']='original MIT review navigation'
    files={name:dict(sha256=sha(output/name),mode=stat.S_IMODE((output/name).stat().st_mode),role=role) for name,role in origins.items()}
    report=dict(schema=1,status='R6-ready-for-owner-review',version='0.0.1-rc.1',candidate_commit=accepted['qualified_source_commit'],candidate_snapshot=accepted['qualified_source_snapshot'],review_baseline=source['base_commit'],review_snapshot=source['source_snapshot_sha256'],review_source_commit=None,owner_review_pending=True,committed=False,pushed=False,tagged=False,published=False,files=files)
    (output/'HANDOFF.json').write_bytes(canonical(report));(output/'SHA256SUMS').write_text(''.join(sha(output/name)+'  '+name+'\n' for name in sorted(set(files)|{'HANDOFF.json'})))
    return verify(output)


def build(review,store,index,output):
    owned={};started=time.time()
    try:return _build(review,store,index,output,owned)
    except BaseException as exc:
        destination=owned.get('output')
        if destination and destination.is_dir() and not destination.is_symlink():
            (destination/'ASSEMBLY-FAILED.json').write_bytes(canonical(dict(status='failed',started_utc=started,finished_utc=time.time(),error=type(exc).__name__+': '+str(exc),owner_review_pending=True,published=False)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['build','verify']);parser.add_argument('output',type=Path);parser.add_argument('--review',type=Path);parser.add_argument('--store',type=Path);parser.add_argument('--index',type=Path)
    args=parser.parse_args()
    if args.action=='build':
        require(args.review and args.store and args.index,'build requires --review, --store, and --index')
        result=build(args.review,args.store,args.index,args.output)
    else:result=verify(args.output)
    print(json.dumps(result,indent=2))
