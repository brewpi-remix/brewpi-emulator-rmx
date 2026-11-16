# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original resource/evidence rules for opt-in Linux sustained qualification."""
import hashlib
import json
import math
from pathlib import Path
import statistics

VERSION='0.0.1-rc.1'
DURATIONS={'normal':86400,'accelerated':21600}
PEAK_KIB=128*1024
GROWTH_KIB=8*1024
WARMUP_SECONDS=1800
WINDOW_SECONDS=3600


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def compare_clocks(previous,current):
    """Reject lost observation, including suspension hidden by monotonic time."""
    deltas={key:current[key]-previous[key] for key in ['monotonic','boottime','utc']}
    if any(not math.isfinite(x) or x<0 or x>5 for x in deltas.values()):
        raise ValueError('interrupted observation or clock discontinuity')
    return deltas


def validate_resources(samples,lifetime,kind,duration,acceptance=True):
    if kind not in DURATIONS:raise ValueError('unknown workload')
    if type(duration) not in [int,float] or not math.isfinite(duration) or duration<=0:raise ValueError('invalid observed duration')
    if not samples or lifetime.get('emulator_pid')!=samples[0]['pid']:
        raise ValueError('missing same-process resource evidence')
    identity=(samples[0]['pid'],samples[0]['start_ticks'])
    previous=None
    origin=samples[0]['monotonic']-samples[0]['elapsed']
    if samples[0]['elapsed']<0 or samples[0]['elapsed']>1:raise ValueError('missing initial resource coverage')
    for row in samples:
        if any(type(row.get(key)) not in [int,float] or not math.isfinite(row[key]) for key in ['monotonic','boottime','utc']):raise ValueError('invalid observation clock')
        if (row['pid'],row['start_ticks'])!=identity:raise ValueError('process changed during continuous observation')
        if any(type(row.get(key)) not in [int,float] or not math.isfinite(row[key]) or row[key]<0 for key in ['elapsed','rss_kib','fds','threads']):
            raise ValueError('invalid resource observation')
        if abs(row['elapsed']-(row['monotonic']-origin))>0.00001:raise ValueError('elapsed observation is not monotonic wall time')
        if previous:
            deltas=compare_clocks(previous,row)
            if deltas['monotonic']>1:raise ValueError('RSS trend sampling gap exceeds one second')
        previous=row
    if lifetime.get('wait4_collected') is not True or lifetime.get('exit_code')!=0 or lifetime.get('interrupted')!=0:
        raise ValueError('missing successful complete-lifetime wait4 accounting')
    peak=lifetime.get('maxrss_kib')
    sampled_peak=max(s['rss_kib'] for s in samples)
    # Linux lifetime and mapping counters use different accounting paths.
    # Retain both and require both to meet the unchanged budget.
    if type(peak) not in [int,float] or not math.isfinite(peak) or peak<=0 or max(peak,sampled_peak)>PEAK_KIB:
        raise ValueError('complete-lifetime or sampled RSS peak exceeds budget')
    if samples[-1]['elapsed']>duration+1 or samples[-1]['elapsed']<duration-1:
        raise ValueError('sample coverage differs from observed duration')
    if acceptance and duration<DURATIONS[kind]:raise ValueError('short pilot cannot qualify a sustained workload')
    first=[s['rss_kib'] for s in samples if WARMUP_SECONDS<=s['elapsed']<WARMUP_SECONDS+WINDOW_SECONDS]
    last=[s['rss_kib'] for s in samples if duration-WINDOW_SECONDS<=s['elapsed']<=duration]
    if acceptance:
        if len(first)<WINDOW_SECONDS or len(last)<WINDOW_SECONDS:raise ValueError('missing complete steady-hour RSS windows')
        if statistics.median(last)>statistics.median(first)+GROWTH_KIB:raise ValueError('steady-hour RSS growth exceeds budget')
    return dict(status='passed',qualification=bool(acceptance),same_pid=identity[0],maxrss_kib=peak,sampled_maxrss_kib=sampled_peak,
                first_steady_median_kib=statistics.median(first) if first else None,
                final_steady_median_kib=statistics.median(last) if last else None)


class Evidence:
    """Rotate only validated records; retain a cumulative digest and segment ledger."""
    def __init__(self,root,limit=1024*1024,keep=8):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        if limit<128 or keep<1:raise ValueError('invalid evidence budget')
        self.limit,self.keep=limit,keep
        self.index=0;self.count=0;self.total_bytes=0;self.digest=hashlib.sha256();self.segment_digest=hashlib.sha256()
        self.segment_count=0;self.segment_size=0;self.closed=False
        self.stream=(self.root/'000000.jsonl').open('xb');self.ledger=(self.root/'segments.jsonl').open('xb')

    def _finish_segment(self):
        self.stream.flush();self.stream.close()
        row=dict(segment=self.index,records=self.segment_count,bytes=self.segment_size,
                 sha256=self.segment_digest.hexdigest(),cumulative_records=self.count,cumulative_sha256=self.digest.hexdigest())
        self.ledger.write(canonical(row));self.ledger.flush()

    def append(self,record):
        if self.closed:raise ValueError('closed evidence stream')
        data=canonical(record)
        if len(data)>self.limit:raise ValueError('record exceeds evidence segment budget')
        if self.segment_size and self.segment_size+len(data)>self.limit:
            self._finish_segment();self.index+=1
            if self.index>=self.keep:(self.root/('%06d.jsonl'%(self.index-self.keep))).unlink()
            self.stream=(self.root/('%06d.jsonl'%self.index)).open('xb')
            self.segment_digest=hashlib.sha256();self.segment_count=0;self.segment_size=0
        self.stream.write(data);self.stream.flush()
        self.digest.update(data);self.segment_digest.update(data)
        self.count+=1;self.total_bytes+=len(data);self.segment_count+=1;self.segment_size+=len(data)

    def close(self):
        if not self.closed:
            self._finish_segment();self.ledger.close();self.closed=True
        return dict(records=self.count,bytes=self.total_bytes,sha256=self.digest.hexdigest(),segments=self.index+1,
                    retained_segments=min(self.keep,self.index+1),validated_before_rotation=True)
