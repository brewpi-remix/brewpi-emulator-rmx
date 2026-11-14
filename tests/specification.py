# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Reproduce original specification, documentation, and pinned-source checks.

Requires this Git checkout and the prepared sibling reference repositories.
References are read with git show; no reference code is imported or executed.
"""
import json,re,subprocess,collections
from pathlib import Path
root=Path(__file__).resolve().parents[1]; base=root/'engineering/protocol/test-vectors'
def pairs(xs):
 d={}
 for k,v in xs:
  assert k not in d,k
  d[k]=v
 return d
art={p.name:json.loads(p.read_text(),object_pairs_hook=pairs) for p in base.glob('*.json')}
d=art['defaults-v1.json']; p=art['protocol-v1.json']; m=art['diagnostics-v1.json']
for a in art.values():
 assert a['schema_version']==1 and a['spdx_license_identifier']=='MIT'
 assert a['execution_status']=='not_executed_against_emulator_or_reference'
 assert a['reference_firmware_revision']=='8f1fa1213cbbfc1f987fada5168d01925e1a2ee8'
def pointer(s):
 f,ptr=s.split('#');v=art[f]
 for k in ptr.split('/')[1:]:v=v[int(k)] if isinstance(v,list) else v[k.replace('~1','/').replace('~0','~')]
 return v
def walk(v):
 if isinstance(v,dict):
  for k,x in v.items():
   if k=='payload_ref':pointer(x)
   if k.endswith('_hex') and isinstance(x,str):bytes.fromhex(x)
   if k=='chunks_hex':
    for h in x:bytes.fromhex(h)
   walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
for a in art.values():walk(a)
records={(r['log_type'],r['log_id']):r for r in m['records']}
assert len(records)==43
assert collections.Counter(k[0] for k in records)=={'E':14,'W':6,'I':23}
def diag(x):
 r=records[x['logType'],x['logID']];assert len(x['V'])==len(r['argument_types'])
 for v,t in zip(x['V'],r['argument_types']):assert type(v) is ({'string':str,'integer':int}[t]),(v,t)
for r in records.values():diag(r['expected_record'])
ids=set();replies=diags=0;actions=collections.Counter()
for c in p['cases']:
 assert c['id'] not in ids;ids.add(c['id']);assert c['initial_preset'] in d['presets']
 for f in c['findings']:assert f in {f'F{i:02}' for i in range(1,22)}
 if c['classification']=='requires_reference_trace':assert c['expected_exact_output'] is None and c['counts_as_pass'] is False;continue
 assert c['classification']=='source_defined'
 for i,s in enumerate(c['steps']):
  actions[s['action']]+=1;e=s.get('expected',{}); rr=e.get('replies',[]);dd=e.get('diagnostics',[]);replies+=len(rr);diags+=len(dd)
  for r in rr:assert sum(k in r for k in ['payload_equals','payload_contains','payload_ref'])==1
  for x in dd:diag(x)
  labels=[r['prefix'] for r in rr]+[f"D:{x['logType']}{x['logID']}" for x in dd]
  if 'output_order' in e:assert collections.Counter(e['output_order'])==collections.Counter(labels),(c['id'],e)
  if s['action']=='serial_write':
   raw=b''.join(bytes.fromhex(h) for h in s['chunks_hex'])
   if raw==b'R':assert c['steps'][i+1]['action']=='await_controller_restart',c['id']
  if 'raw_hex' in e:
   raw=bytes.fromhex(e['raw_hex']);assert raw.endswith(b'\r\n')
   frames=raw[:-2].split(b'\r\n');rr=rr or [{'prefix':line.split(b':',1)[0].decode()} for line in frames]
   for line,r in zip(frames,rr):
    pref,pay=line.split(b':',1);assert pref.decode()==r['prefix'];actual=json.loads(pay.decode('cp437'))
    if 'payload_ref'in r:assert actual==pointer(r['payload_ref'])
    if 'payload_equals'in r:assert actual==r['payload_equals']
    if pref==b'N':assert actual==d['identity']
    if pref==b'S':assert actual==d['settings_c']
    if pref==b'L':assert all(len(row)==20 for row in actual) and all(actual[i][18]=='░' for i in [1,2])
for name,pr in d['presets'].items():
 chain=set();q=pr
 while 'extends' in q:
  n=q['extends'];assert n not in chain;chain.add(n);q=d['presets'][n]
for row in d['inventory']:
 if 'a' not in row:continue
 crc=0
 for b in bytes.fromhex(row['a']):
  crc^=b
  for _ in range(8):crc=(crc>>1)^(0x8c if crc&1 else 0)
 assert crc==0
roms=[x['a'] for x in d['inventory'] if 'a'in x]
assert roms==sorted(roms,key=lambda h:tuple((b>>i)&1 for b in bytes.fromhex(h) for i in range(8)))
# Validate documentation targets and pinned source paths without executing references.
files=[root/x for x in subprocess.check_output(['git','-C',str(root),'ls-files','--cached','--others','--exclude-standard'],text=True).splitlines()]
local=anchors=source=0;cache={}
for f in files:
 b=f.read_bytes();assert b.endswith(b'\n') and b'\r' not in b,f
 assert all(line.rstrip()==line for line in b.splitlines()),f
 if f.suffix!='.md':continue
 txt=b.decode()
 for url in re.findall(r'\]\(([^)]+)\)',txt):
  if url.startswith('https://github.com/brewpi-remix/') and '/blob/' in url:
   mat=re.fullmatch(r'https://github.com/brewpi-remix/([^/]+)/blob/([a-f0-9]{40})/([^#]+)(?:#L(\d+)(?:-L\d+)?)?',url);assert mat,url
   repo,rev,path,line=mat.groups();key=(repo,rev,path)
   if key not in cache:cache[key]=subprocess.check_output(['git','-C',str(root.parent/repo),'show',f'{rev}:{path}'],text=True)
   if line:assert int(line)<=len(cache[key].splitlines()),url
   source+=1
  elif not re.match(r'\w+://',url):
   target,_,anchor=url.partition('#');dest=(f.parent/target).resolve() if target else f;assert dest.exists(),(f,url);local+=1
   if anchor:
    headings=[];seen=collections.Counter()
    for h in re.findall(r'^#+ (.+)$',dest.read_text(),re.M):
     h=re.sub(r'[^\w\- ]','',h.lower()).replace(' ','-');n=seen[h];seen[h]+=1;headings.append(h+(f'-{n}'if n else ''))
    assert anchor in headings,(f,url);anchors+=1
print(json.dumps({'files':len(files),'local_links':local,'anchor_links':anchors,'pinned_sources':source,'cases':len(ids),'classifications':dict(collections.Counter(c['classification'] for c in p['cases'])),'reply_expectations':replies,'diagnostic_expectations':diags,'metadata_signatures':len(records),'actions':dict(actions)},indent=2))
