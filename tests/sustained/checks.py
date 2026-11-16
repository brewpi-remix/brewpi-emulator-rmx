# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Original negative regressions for sustained evidence; no reference fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import socket
import copy
import threading
import time
from measurement import Evidence, canonical, compare_clocks, validate_resources
from wire import Frames
from unittest.mock import patch


class Gates(unittest.TestCase):
    def clock(self,t):return dict(monotonic=t,boottime=t,utc=1000+t)

    def test_clock_gaps_suspend_and_backwards_time_fail(self):
        compare_clocks(self.clock(1),self.clock(1.5))
        for current in [self.clock(7),dict(self.clock(2),boottime=20),dict(self.clock(2),utc=1020),self.clock(0)]:
            with self.subTest(current=current),self.assertRaises(ValueError):compare_clocks(self.clock(1),current)

    def rows(self):
        return [dict(self.clock(t),pid=17,start_ticks=100,elapsed=t,rss_kib=2048,fds=8,threads=1) for t in [0,.5,1]]

    def usage(self):return dict(emulator_pid=17,wait4_collected=True,exit_code=0,interrupted=0,maxrss_kib=4096)

    def test_pilot_never_counts_as_qualification(self):
        self.assertFalse(validate_resources(self.rows(),self.usage(),'normal',1,False)['qualification'])
        with self.assertRaises(ValueError):validate_resources(self.rows(),self.usage(),'normal',1)

    def test_same_pid_sampling_gap_and_peak_proof_required(self):
        for field,value in [('pid',18),('start_ticks',101),('monotonic',3),('rss_kib',float('nan'))]:
            rows=self.rows();rows[-1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_resources(rows,self.usage(),'normal',1,False)
        for clock in ['monotonic','boottime','utc']:
            rows=self.rows();rows[0][clock]=float('nan')
            with self.subTest(clock=clock),self.assertRaises(ValueError):validate_resources(rows,self.usage(),'normal',1,False)
        for field,value in [('emulator_pid',19),('wait4_collected',False),('exit_code',1),('interrupted',15),('maxrss_kib',131073),('maxrss_kib',0)]:
            with self.subTest(field=field),self.assertRaises(ValueError):validate_resources(self.rows(),dict(self.usage(),**{field:value}),'normal',1,False)
        report=validate_resources(self.rows(),dict(self.usage(),maxrss_kib=2000),'normal',1,False)
        self.assertEqual(report['sampled_maxrss_kib'],2048)
        rows=self.rows();rows[-1]['rss_kib']=131073
        with self.assertRaises(ValueError):validate_resources(rows,self.usage(),'normal',1,False)

    def test_simulated_time_cannot_replace_observation_time(self):
        rows=self.rows();rows[-1]['elapsed']=60
        with self.assertRaises(ValueError):validate_resources(rows,self.usage(),'accelerated',60,False)
        for duration in [0,float('inf'),float('nan')]:
            with self.assertRaises(ValueError):validate_resources(self.rows(),self.usage(),'normal',duration,False)

    def test_steady_windows_and_growth_are_mandatory(self):
        rows=[dict(self.clock(t),pid=17,start_ticks=100,elapsed=t,rss_kib=2048 if t<80000 else 12000,fds=8,threads=1) for t in range(86401)]
        with self.assertRaisesRegex(ValueError,'growth'):validate_resources(rows,dict(self.usage(),maxrss_kib=12000),'normal',86400)
        for row in rows:row['rss_kib']=2048
        self.assertTrue(validate_resources(rows,self.usage(),'normal',86400)['qualification'])
        with self.assertRaises(ValueError):validate_resources(rows[:-2],self.usage(),'normal',86400)

    def test_rotation_preserves_all_validated_digest_accounting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'wire';evidence=Evidence(root,128,2)
            records=[dict(sequence=i,value='original fixture') for i in range(20)]
            for row in records:evidence.append(row)
            result=evidence.close();ledger=[json.loads(line) for line in (root/'segments.jsonl').read_text().splitlines()]
            self.assertEqual(result['records'],len(records));self.assertEqual(result['sha256'],hashlib.sha256(b''.join(canonical(row) for row in records)).hexdigest())
            self.assertEqual(sum(row['records'] for row in ledger),len(records));self.assertLessEqual(len(list(root.glob('[0-9]*.jsonl'))),2)
            with self.assertRaises(ValueError):evidence.append({})


class Protocol(unittest.TestCase):
    def test_every_split_preserves_non_json_diagnostics_and_all_bytes(self):
        wire=b'D:{"logType":"I","logID":12,"V":["key","unescaped"quote"]}\r\n'
        for cut in range(len(wire)+1):
            stream=Frames();rows=stream.feed(wire[:cut])+stream.feed(wire[cut:])
            self.assertEqual(rows,[wire[:-2]]);self.assertEqual(stream.summary(True)['bytes'],len(wire))
            self.assertEqual(stream.summary()['sha256'],hashlib.sha256(wire).hexdigest())

    def test_bad_or_incomplete_frames_fail(self):
        for wire in [b'bad\r\n',b'Q:{}\r\n',b'N:{}\r\n',b'D:{}\r\n',b'S:{incomplete}\r\n',b'x'*(1024*1024+1)]:
            with self.subTest(wire=wire),self.assertRaises(ValueError):Frames().feed(wire)
        stream=Frames();stream.feed(b'N:')
        with self.assertRaises(ValueError):stream.summary(True)


class HostSocket(unittest.TestCase):
    def test_complete_reply_does_not_require_peer_eof(self):
        from host import Host
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            listener.bind(str(root/'BEERSOCKET'));listener.listen(1)
            release=threading.Event();errors=[]
            def server():
                try:
                    conn,_=listener.accept()
                    with conn:
                        self.assertEqual(conn.recv(4096),b'getControlSettings')
                        conn.sendall(b'{"mode":');conn.sendall(b'"b"}')
                        release.wait(2)
                except BaseException as exc:errors.append(exc)
            worker=threading.Thread(target=server);worker.start()
            client=Host.__new__(Host);client.script=root
            try:self.assertEqual(client.get('getControlSettings'),{'mode':'b'})
            finally:release.set();worker.join(3);listener.close()
            self.assertFalse(worker.is_alive());self.assertFalse(errors)


class FailureAccounting(unittest.TestCase):
    def test_observation_heartbeat_and_post_exit_validation_have_distinct_deadlines(self):
        from supervise import check_worker_progress
        current=(100000,100000,200000)
        for phase in ['normal','accelerated','latency','backpressure']:
            with self.subTest(phase=phase),self.assertRaises(RuntimeError):
                check_worker_progress(dict(phase=phase,monotonic=99994,utc=199994),current,6)
        # Full-day sample reconciliation can exceed five seconds after clean exit.
        for phase in ['setup','validation']:
            check_worker_progress(dict(phase=phase),current,10)
            with self.subTest(phase=phase),self.assertRaises(RuntimeError):
                check_worker_progress(dict(phase=phase),current,1801)
        for bad in [dict(phase='unknown'),dict(phase='normal',monotonic=float('nan'),utc=200000),dict(phase='normal',monotonic=100006,utc=200000)]:
            with self.subTest(heartbeat=bad),self.assertRaises(RuntimeError):check_worker_progress(bad,current,0)

    def test_evidence_io_failure_is_not_counted_as_a_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence=Evidence(Path(temporary)/'capture',128,2)
            evidence.append(dict(valid=True))
            with patch.object(evidence,'stream') as stream:
                stream.write.side_effect=OSError('injected evidence storage failure')
                with self.assertRaises(OSError):evidence.append(dict(valid=True,second=True))
            self.assertEqual(evidence.close()['records'],1)

    def test_missing_failed_short_and_wrong_architecture_reports_fail(self):
        from validate import summary
        for result in [dict(status='failed'),dict(status='passed',qualification=True,r3_complete=True,architecture='amd64',workloads=[]),
                       dict(status='passed',qualification=False,r3_complete=False,architecture='arm64',workloads=[])]:
            with self.subTest(result=result),self.assertRaises(ValueError):summary(result,True,'arm64')


    def test_complete_summary_rejects_missing_coverage_and_failed_gates(self):
        from validate import summary,FAULTS
        cases=[]
        for start,advance in [(65534000,1000),(65535000,1000),(65535500,1500),(65536000,2000),(4294966000,2000),(4294967000,1000),(4294967295,1),(4294967295,100)]:
            ms=(start+(advance//100)*100)%(2**32)
            cases.append(dict(start_millis=start,advance_millis=advance,expected_millis=ms,expected_seconds=(ms//1000)%65536,status='passed'))
        cycles=[dict(cycle=i,status='passed',full_snapshot_equal=True,quiescent_fds=8,quiescent_threads=1) for i in range(100)]
        values=dict(clock=dict(status='passed',constructed_history=True,cases=cases),faults=dict(status='passed',checks=[dict(name=n,status='passed') for n in FAULTS]),lifecycle=dict(status='passed',cycles=cycles))
        for kind,speed,duration in [('normal',1,86400),('accelerated',60,21600)]:
            values[kind]=dict(status='passed',qualification=True,requested_speed=speed,achieved_speed=speed,observed_wall_seconds=duration,pid=17,
                lifetime=dict(emulator_pid=17,wait4_collected=True,exit_code=0,interrupted=0),resource=dict(same_pid=17),
                latency=dict(samples=30,median_seconds=.005,max_seconds=.01,partial_token_seconds=1),states=[3,4],profile_observations=['active','disabled'],host=dict(unchanged=True),
                backpressure=[dict(status='passed',ordered_replies=2000,pause_seconds=.5) for _ in range(6)],controller_second_wraps=19)
        def result(v):return dict(status='passed',qualification=True,r3_complete=True,architecture='arm64',workloads=[dict(kind=k,result=r) for k,r in v.items()])
        self.assertEqual(set(summary(result(values),True,'arm64')),set(values))
        distribution=copy.deepcopy(values);distribution['normal']['latency']['seconds']=[.005]*29+[.01]
        summary(result(distribution),True,'arm64')
        for bad in [float('nan'),float('inf'),None,-1]:
            changed=copy.deepcopy(values);changed['normal']['observed_wall_seconds']=bad
            with self.subTest(duration=bad),self.assertRaises(ValueError):summary(result(changed),True,'arm64')
        for field,bad in [('max_seconds',float('nan')),('median_seconds',None),('samples',0),('seconds',[.01])]:
            changed=copy.deepcopy(values);changed['normal']['latency'][field]=bad
            with self.subTest(timing=field),self.assertRaises(ValueError):summary(result(changed),True,'arm64')
        partial=result({k:v for k,v in values.items() if k!='normal'});partial.update(scope='accelerated-only',r3_complete=False)
        self.assertEqual(set(summary(partial,True,'arm64','accelerated-only')),set(values)-{'normal'})
        with self.assertRaises(ValueError):summary(partial,True,'arm64')
        partial['r3_complete']=True
        with self.assertRaises(ValueError):summary(partial,True,'arm64','accelerated-only')
        for kind,key,value in [('clock','cases',cases[:7]+cases[:1]),('faults','checks',[]),('lifecycle','cycles',cycles[:99]),
            ('normal','observed_wall_seconds',86399),('accelerated','backpressure',[]),('accelerated','backpressure',[dict(status='failed')]),
            ('normal','states',[3]),('normal','profile_observations',['active']),('accelerated','controller_second_wraps',1)]:
            changed=copy.deepcopy(values);changed[kind][key]=value
            with self.subTest(kind=kind,key=key),self.assertRaises(ValueError):summary(result(changed),True,'arm64')


if __name__=='__main__':unittest.main()
