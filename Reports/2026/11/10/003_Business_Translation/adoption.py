"""Verify the shipping packet and first measured raw completion for every case before scoring it."""
from hashlib import sha256
import json
import os
from pathlib import Path
import random
from statistics import median
import sys
import uuid

root = Path(sys.argv[1]).resolve()
adoption = root / 'adoption'
project = adoption / 'candidate'
sys.path[:0] = [str(project/'tests'), str(project)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(project)
from test_equipment_ai import AssistantTests
from utils.ai_assistant import worker


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write(name, data):
    (adoption/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def sha(text):
    return sha256(text.encode()).hexdigest()


trial = json.loads((root/'release/measurements.json').read_bytes())
originals = trial['cases']
followup = json.loads((adoption/'cases.json').read_bytes())
assert len(followup) == 6 and followup[0]['id'] == 'U02'
cases = originals + [row for row in followup if row['id'] != 'U02']
assert len(cases) == len({row['id'] for row in cases}) == 46
table = {}
ledger = []
for group in [root, root/'confirmation', adoption]:
    for arm in ['baseline','candidate']:
        measured = lines(group/(arm+'-results.jsonl'))
        wires = lines(group/(arm+'-wire.jsonl'))
        assert len(measured) == len(wires)
        for row,wire in zip(measured,wires):
            k = row['case']
            step, = row['steps']
            assert wire['id'] == k and wire['source_sha256'] == sha(row['original'])
            assert step['wire_calls'] == 1 and wire['tools'] == 0 and wire['model'] == 'qwen3.8-flash-next-iq3_xxs'
            table[group,arm,k] = row,wire,step
            ledger.append({'case':k,'arm':arm,'group':group.name if group!=root else 'comparison',
                           'start':step['wire_start'],'end':step['wire_end'],
                           'fingerprint':sha(str(step['server_request_id'])),'state':row['state']})
ledger.sort(key=lambda x:x['start'])
assert len(ledger)==94==len({row['fingerprint'] for row in ledger})
assert all(a['end']<=b['start'] for a,b in zip(ledger,ledger[1:]))
write('all-requests.json',ledger)


def measured(group, arm, k):
    row,wire,step=table[group,arm,k]
    return {'origin':(group.name if group!=root else 'comparison')+'/'+arm,'raw':step['content'],'state':row['state'],
            'error':row['error'],'stored':row['answer'],'seconds':row['elapsed'],'model':wire['model'],
            'effort':wire['effort'],'prompt_sha256':wire['instruction_sha256'],'termination':step['termination'],
            'request_fingerprint':sha(str(step['server_request_id']))}


def finish_shipped(group,arm,case):
    k=case['id']
    row,wire,step=table[group,arm,k]
    f=AssistantTests(methodName='runTest')
    f.setUp()
    try:
        f.login(2)
        receipt=f.client.post('/api/ai/conversations/first-turn',json={'content':row['submitted'],'level':'medium',
                              'reasoning_version':2,'client_key':uuid.uuid4().hex},headers=f.headers)
        assert receipt.status_code==202,k
        claimed=f.client.post('/internal/ai/claim',json={'worker':uuid.uuid4().hex,'protocol':worker.PROTOCOL},headers=f.worker_headers)
        job=claimed.get_json()['job']
        assert job['route']['mail_writing_revision']=='business-writing-20261110-v2'
        assert sha(job['messages'][0]['content'])==wire['instruction_sha256'],k
        assert job['messages'][1:]==[{'role':'user','content':case['original']}] and job['tools']==[]
        assert job['reasoning_effort']==wire['effort']=={'en-ko':'xhigh','ko-en':'low'}[case['direction']]
        assert job['route']['model']==wire['model']
        packet={key:step[key] for key in ('outcome','termination','content','calls')}
        done=f.client.post('/internal/ai/jobs/'+job['id']+'/finish',json={**packet,'lease':job['lease']},headers=f.worker_headers)
        assert done.status_code==200,k
        with f.store.db() as db:
            state,error=db.execute('select state,error from jobs where id=?',(job['id'],)).fetchone()
            raw=db.execute('select content from message_steps where job=?',(job['id'],)).fetchone()[0]
            display=db.execute("select content from messages where role='assistant' and job=?",(job['id'],)).fetchone()[0]
        assert raw==step['content']
        item=measured(group,arm,k)
        if (state,error,display)!=(row['state'],row['error'],row['stored_assistant'][-1]):
            item.update(original_state=row['state'],original_error=row['error'],original_display=row['answer'])
        item.update(state=state,error=error,stored=display if state=='done' else '')
        return item
    finally:
        f.tearDown()
        f.doCleanups()


arms={'baseline':{},'release':{}}
needed={'E2','U09','H-K03','U02'}
reuse={}
for c in cases:
    k=c['id']
    group=adoption if k.startswith('D') else (root/'confirmation' if k.startswith('V') else root)
    arms['baseline'][k]=measured(group,'baseline',k)
    sg=adoption if k=='U02' else group
    trial_arm='baseline' if c['direction']=='en-ko' and sg!=adoption else 'candidate'
    # Each source uses the measured wire instructions actually shipped.
    arms['release'][k]=finish_shipped(sg,trial_arm,c)
    result=arms['release'][k]['stored']
    matches=[name for name in ['baseline','candidate'] if k in trial['arms'][name] and trial['arms'][name][k]['stored']==result]
    if not matches or k.startswith('D'):
        needed.add(k)
    else:
        reuse[k]=trial_arm if trial_arm in matches else matches[0]
write('adoption-measurements.json',{'cases':cases,'arms':arms,'exact_packet_and_finish_replays':len(cases),
      'adoption_live_rows':{arm:{c['id']:measured(adoption,arm,c['id']) for c in followup}
                            for arm in ('baseline','candidate')},
      'all_model_calls':len(ledger),'overlapping_calls':0,'reused_review_arms':reuse,
      'time_medians_seconds':{arm:{direction:round(median(data[c['id']]['seconds'] for c in cases if c['direction']==direction),2)
                         for direction in ('en-ko','ko-en')} for arm,data in arms.items()}})
selection=[c for c in cases if c['id'] in needed]
rng=random.Random(2026111004)
rng.shuffle(selection)
sides=[i%2==0 for i in range(len(selection))]
rng.shuffle(sides)
blind=[];mapping={}
for c,flip in zip(selection,sides):
    k=c['id']
    mapping[k]=['release','baseline'] if flip else ['baseline','release']
    blind.append({'id':k,'source':c['original'],'target':{'en-ko':'한국어','ko-en':'영어'}[c['direction']],
                  **{key:arms[arm][k]['stored'] or '[저장된 번역문 없음]' for key,arm in zip(('L','R'),mapping[k])}})
write('adoption-blind.json',blind);write('adoption-mapping.json',mapping)
print('matched',len(cases),'cases;',len(ledger),'calls;',len(needed),'blind followups;',sorted(needed))
