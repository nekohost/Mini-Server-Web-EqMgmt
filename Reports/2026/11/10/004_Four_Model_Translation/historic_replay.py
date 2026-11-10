"""Replay the first saved completion when the final application builds the same request. Queue changed historic requests for live validation."""
from hashlib import sha256
import json, os
from pathlib import Path
import sys, uuid

root, folder=map(lambda a:Path(a).resolve(),sys.argv[1:3])
sys.path[:0]=[str(root/'tests'),str(root)]
os.environ['EQ_TEST_PROJECT_ROOT']=str(root)
from test_equipment_ai import AssistantTests
from utils.ai_assistant.worker import PROTOCOL

def sha(v):return sha256(v.encode()).hexdigest()

def check(case,previous):
    fixture=AssistantTests(methodName='runTest');fixture.setUp()
    try:
        fixture.login(2)
        original=case['original']; target={'ko-en':'영어','en-ko':'한국어'}[case['direction']]
        receipt=fixture.client.post('/api/ai/conversations/first-turn',json={'content':'다음 이메일을 '+target+'로 번역해 주세요.\n\n'+original,
            'level':'medium','reasoning_version':2,'client_key':uuid.uuid4().hex},headers=fixture.headers)
        assert receipt.status_code==202,case['id']
        job=fixture.client.post('/internal/ai/claim',json={'worker':uuid.uuid4().hex,'protocol':PROTOCOL},headers=fixture.worker_headers).get_json()['job']
        assert job['tools']==[] and not job['web_search_required'] and job['messages'][1:]==[{'role':'user','content':original}]
        assert job['route']['model']==previous['model'] and job['reasoning_effort']==previous['effort']
        digest=sha(job['messages'][0]['content'])
        if digest!=previous['prompt_sha256']:return {'same':False,'instruction_sha256':digest}
        assert previous['state']=='done' and previous['termination']=={'done':True,'finish_reason':'stop'}
        packet={'lease':job['lease'],'outcome':'complete','termination':previous['termination'],'content':previous['raw'],'calls':[]}
        response=fixture.client.post('/internal/ai/jobs/'+job['id']+'/finish',json=packet,headers=fixture.worker_headers)
        assert response.status_code==200,case['id']
        with fixture.store.db() as db:
            saved=db.execute('select state from jobs where id=?',(job['id'],)).fetchone()
            msg=db.execute("select content from messages where role='assistant' and job=?",(job['id'],)).fetchone()
        assert saved[0]=='done' and msg[0]==previous['stored'],case['id']
        return {'same':True,'instruction_sha256':digest,'previous_raw_sha256':sha(previous['raw']),'stored_sha256':sha(msg[0])}
    finally:fixture.tearDown();fixture.doCleanups()

prior=json.loads((folder/'historic-source.json').read_bytes())
replays={}
pending=[]
for case in prior['cases']:
    key=case['id'];old=prior['arms']['release'][key]
    replays[key]=check(case,old)
    if not replays[key]['same']:pending.append(case)
assert len(replays)==20
(folder/'replays.json').write_text(json.dumps(replays,indent=2))
(folder/'cases.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2))
print('identical applied replays',20-len(pending),'live required',len(pending))
