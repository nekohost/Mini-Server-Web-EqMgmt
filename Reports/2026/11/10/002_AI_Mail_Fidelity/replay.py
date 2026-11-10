"""Compare stored results of the same 66 historical completions through both source trees."""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

folder = Path(sys.argv[1])
arm = sys.argv[2]
root = folder / arm
sys.path[:0] = [str(root/'tests'), str(root)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(root)
from test_equipment_ai import AssistantTests
from utils.ai_assistant import worker

suite = sys.argv[3] if len(sys.argv) == 4 else 'archive66'
expected = {'archive66':66, 'delivery12':12}[suite]
rows = json.loads((folder/(suite+'.json')).read_bytes())
assert len(rows) == len({r['case'] for r in rows}) == expected
evidence = []
for row in rows:
    f = AssistantTests(methodName='runTest')
    f.setUp()
    try:
        f.login(2)
        target = '한국어' if row['direction']=='en-ko' else '영어'
        question = f"다음 이메일을 {target}로 번역해 주세요.\n\n"+row['source']
        resp = f.client.post('/api/ai/conversations/first-turn',json={'content':question,'level':'medium','reasoning_version':2,'client_key':uuid.uuid4().hex},headers=f.headers)
        assert resp.status_code == 202
        claimed = f.client.post('/internal/ai/claim',json={'worker':uuid.uuid4().hex,'protocol':worker.PROTOCOL},headers=f.worker_headers)
        job = claimed.get_json()['job']
        assert job['id']==resp.get_json()['job_id'] and job['tools']==[] and job['messages'][1]['content']==row['source']
        assert job['reasoning_effort']==row['effort'] and job['route']['mail_translation']==row['direction']
        prompt_hash = hashlib.sha256(job['messages'][0]['content'].encode('utf8')).hexdigest()
        if suite == 'delivery12':
            assert prompt_hash == row['prompt_sha256'], row['case']
        finish = f.client.post('/internal/ai/jobs/'+job['id']+'/finish',json={**row['measured_finish'],'lease':job['lease']},headers=f.worker_headers)
        assert finish.status_code==200
        with f.store.db() as db:
            raw = db.execute('SELECT content FROM message_steps WHERE job=?',(job['id'],)).fetchone()[0]
            saved = db.execute("SELECT content FROM messages WHERE role='assistant' AND job=?",(job['id'],)).fetchone()[0]
            state,reason = db.execute('SELECT state,error FROM jobs WHERE id=?',(job['id'],)).fetchone()
        assert raw==row['measured_finish']['content']
        if suite == 'delivery12':
            assert (state,saved)==(row['expected_state'],row['expected_display']),row['case']
        evidence.append({'case':row['case'],'state':state,'reason':reason,'source':row['source'],'raw':raw,'stored':saved,
                         'policy':job['route'].get('mail_fidelity_revision'),'prompt_sha256':prompt_hash})
    finally:
        f.tearDown()
        f.doCleanups()
(folder/(arm+'-'+str(expected)+'.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(arm,len(evidence))
