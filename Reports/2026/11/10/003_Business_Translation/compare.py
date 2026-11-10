"""Publish synthetic first attempts and verify the exact production candidate against the measured wire."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
from statistics import median
import sys
import uuid

folder = Path(sys.argv[1]).resolve()
delivery = folder/'release'
root = delivery/'candidate'
sys.path[:0] = [str(root/'tests'), str(root)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(root)
from test_equipment_ai import AssistantTests
from utils.ai_assistant import worker

def read_lines(path):
    return [json.loads(s) for s in path.read_text().splitlines()]

def write_json(name, value):
    (delivery/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def h(s):
    return hashlib.sha256(s.encode()).hexdigest()

groups=(folder, folder/'confirmation')
cases=[case for group in groups for case in json.loads((group/'cases.json').read_bytes())]
ids=[v['id'] for v in cases]
assert len(ids)==len(set(ids)) and len(cases)==41
arms={}
periods=[]
engine_ids=set()
health={}
for arm in ('baseline','candidate'):
    rows=[r for group in groups for r in read_lines(group/(arm+'-results.jsonl'))]
    wires=[w for group in groups for w in read_lines(group/(arm+'-wire.jsonl'))]
    samples=[read_lines(group/(arm+'-metrics.jsonl')) for group in groups]
    stats=[s for group_samples in samples for s in group_samples]
    assert [v['case'] for v in rows]==[w['id'] for w in wires]==ids
    observed=[s for s in stats if 'state' in s]
    health[arm]={'failed_metrics_samples':sum('sample_error' in v for v in stats),
                 'model':sorted({s['engine'] for s in observed}),'max_observed_queue':max(s['queued'] for s in observed),
                 'provider_total_delta':sum([s['total'] for s in sample if 'total' in s][-1]
                                            -[s['total'] for s in sample if 'total' in s][0] for sample in samples)}
    data={}
    for case,row,wire in zip(cases,rows,wires):
        step,=row['steps']
        assert row['original']==case['original'] and wire['source_sha256']==h(case['original'])
        assert step['wire_calls']==1 and wire['model']=='qwen3.8-flash-next-iq3_xxs' and not wire['tools']
        assert step['server_request_id'] not in engine_ids
        engine_ids.add(step['server_request_id'])
        periods.append((step['wire_start'],step['wire_end']))
        data[case['id']]={'state':row['state'],'error':row['error'],'raw':step['content'],'stored':row['answer'],
                          'elapsed_s':row['elapsed'],'effort':wire['effort'],'system_sha256':wire['instruction_sha256'],
                          'termination':step['termination'],'model':wire['model'],'step_outcome':step['outcome']}
        if arm=='candidate':
            f=AssistantTests(methodName='runTest')
            f.setUp()
            try:
                f.login(2)
                reply=f.client.post('/api/ai/conversations/first-turn',json={'content':row['submitted'],'level':'medium',
                    'reasoning_version':2,'client_key':uuid.uuid4().hex},headers=f.headers)
                assert reply.status_code==202,case['id']
                claimed=f.client.post('/internal/ai/claim',json={'worker':uuid.uuid4().hex,'protocol':worker.PROTOCOL},headers=f.worker_headers)
                job=claimed.get_json()['job']
                assert job['messages'][1:]==[{'role':'user','content':case['original']}] and job['tools']==[]
                assert h(job['messages'][0]['content'])==wire['instruction_sha256'] and job['reasoning_effort']==wire['effort']
                payload={k:step[k] for k in ('outcome','termination','content','calls')}
                payload['lease']=job['lease']
                res=f.client.post('/internal/ai/jobs/'+job['id']+'/finish',json=payload,headers=f.worker_headers)
                assert res.status_code==200,(case['id'],res.get_json())
                with f.store.db() as db:
                    s,e=db.execute('select state,error from jobs where id=?',(job['id'],)).fetchone()
                    raw=db.execute('select content from message_steps where job=?',(job['id'],)).fetchone()[0]
                    stored=db.execute("select content from messages where role='assistant' and job=?",(job['id'],)).fetchone()[0]
                assert raw==step['content']
                study_display=row['stored_assistant'][-1]
                if (s,e,stored)!=(row['state'],row['error'],study_display):
                    # Only the new subjectless-envelope check was added after the original
                    # candidate run. Keep the first termination and certify exactly what changed.
                    from utils.ai_assistant.translation import unrequested_heading
                    assert case['split']!='locked_confirmation' and s=='done' and not e
                    assert step['termination']=={'done':True,'finish_reason':'stop'}
                    assert unrequested_heading(case['original'],raw)!=raw
                    data[case['id']].update(measured_state=row['state'],measured_error=row['error'],
                            measured_display=row['answer'],state=s,error=e,stored=stored)
            finally:
                f.tearDown()
                f.doCleanups()
    arms[arm]=data
periods.sort()
gaps=[n[0]-p[1] for p,n in zip(periods,periods[1:])]
assert min(gaps)>=0
mapping={}
blind=[]
order=list(range(len(cases)))
rng=random.Random(2026111003)
rng.shuffle(order)
flips=[i%2==0 for i in range(len(cases))]
rng.shuffle(flips)
for idx in order:
    c=cases[idx]
    k=c['id']
    armnames=['candidate','baseline'] if flips[idx] else ['baseline','candidate']
    mapping[k]=armnames
    blind.append({'id':k,'source':c['original'],'target':{'en-ko':'한국어','ko-en':'영어'}[c['direction']],
                  **{letter:arms[a][k]['stored'] or '[저장된 번역문 없음]' for letter,a in zip(('L','R'),armnames)}})
write_json('blind-mail.json',blind)
write_json('mapping.json',mapping)
old=json.loads((folder/'baseline-66.json').read_bytes())
new=json.loads((delivery/'candidate-66.json').read_bytes())
assert len(old)==len(new)==66 and all((a['case'],a['state'],a['stored'],a['raw'])==(b['case'],b['state'],b['stored'],b['raw']) for a,b in zip(old,new))
write_json('measurements.json',{'cases':cases,'arms':arms,'models':health,'wire_count':len(engine_ids),
    'overlaps':0,'minimum_between_requests_s':round(min(gaps),3),'exact_shipped_replays':len(cases),
    'historical_replays':dict(Counter(v['state'] for v in new)),
    'adjusted_envelope_cases':[k for k,v in arms['candidate'].items() if 'measured_state' in v],
    'time_medians_seconds':{arm:{lang:round(median(v['elapsed_s'] for k,v in rows.items() if k in
        {c['id'] for c in cases if c['direction']==lang}),2) for lang in ('en-ko','ko-en')} for arm,rows in arms.items()}})
print(len(cases),'pairs;',len(engine_ids),'wire calls;',len(new),'previous replies')
