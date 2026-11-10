"""Replay the exact measured Qwen streams through the revised application, preserving first outcomes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

trial = Path(sys.argv[1]).resolve()
root = trial/'verified/candidate'
sys.path[:0] = [str(root/'tests'), str(root)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(root)
from test_equipment_ai import AssistantTests
from utils.ai_assistant.worker import PROTOCOL
from blind_review import blind, write_new

cases = [case for file in ('holdout.json', 'contrast.json') for case in json.loads((trial/file).read_bytes())]
data = json.loads((trial/'confirmation/measurements.json').read_bytes())
if (trial/'prospective/measurements.json').is_file():
    cases.extend(json.loads((trial/'prospective-cases.json').read_bytes()))
    data.update(json.loads((trial/'prospective/measurements.json').read_bytes()))
replays = []
shared_controls = len(sys.argv) > 2 and sys.argv[2] == 'shared-controls'
if shared_controls:
    cases = [case for case in cases if data[case['id']]['control']['instruction_sha256']
             == data[case['id']]['selected']['instruction_sha256']]
out = trial/('shared-control-replay' if shared_controls else 'verified-confirmation')
out.mkdir(exist_ok=True)
for case in cases:
    key = case['id']
    row = data[key]['control' if shared_controls else 'selected']
    f = AssistantTests(methodName='runTest')
    f.setUp()
    try:
        f.login(2)
        source = case['original']
        target = {'ko-en':'영어', 'en-ko':'한국어'}[case['direction']]
        receipt = f.client.post('/api/ai/conversations/first-turn', json={
            'content':'다음 이메일을 '+target+'로 번역해 주세요.\n\n'+source,
            'level':'medium','reasoning_version':2,'client_key':uuid.uuid4().hex}, headers=f.headers)
        assert receipt.status_code == 202, key
        job = f.client.post('/internal/ai/claim',json={'worker':uuid.uuid4().hex,'protocol':PROTOCOL},headers=f.worker_headers).get_json()['job']
        assert job['tools'] == [] and not job['web_search_required']
        assert job['route']['model'] == row['model'] and job['reasoning_effort'] == row['effort']
        assert job['messages'][1:] == [{'role':'user','content':source}]
        assert hashlib.sha256(job['messages'][0]['content'].encode()).hexdigest() == row['instruction_sha256']
        assert job['id'] == receipt.get_json()['job_id'] and row['termination']['done'] is True
        finish = f.client.post('/internal/ai/jobs/'+job['id']+'/finish',json={
            'lease':job['lease'],'outcome':'complete','termination':row['termination'],'content':row['raw'],'calls':[]},headers=f.worker_headers)
        assert finish.status_code == 200, key
        with f.store.db() as db:
            jid = (job['id'],)
            state, error = db.execute('SELECT state,error FROM jobs WHERE id=?',jid).fetchone()
            message = db.execute("SELECT content FROM messages WHERE role='assistant' AND job=?",jid).fetchone()
            raw = db.execute('SELECT content FROM message_steps WHERE job=?',jid).fetchone()[0]
        assert raw == row['raw']
        stored = message[0] if message else ''
        if key == 'T5' and not shared_controls:
            assert row['state'] == 'failed' and state == 'done' and 'stock.csv' in stored
        else:
            assert state == row['state'] and (stored or '') == (row['stored'] or ''), key
        replays.append({'case':key,'original_state':row['state'],'original_error':row['error'],'final_state':state,'final_error':error,
                        'identical_wire_and_raw':True, 'display_changed':(stored or '')!=(row['stored'] or '')})
        row.update(state=state,stored=stored,error=error)
    finally:
        f.tearDown()
        f.doCleanups()
write_new(out/'replays.json',replays)
if shared_controls:
    print('verified',len(replays),'unchanged-instruction control streams, identical saved answers')
else:
    write_new(out/'measurements.json',data)
    print('verified',len(replays),'recorded streams',blind(cases,data,out))
