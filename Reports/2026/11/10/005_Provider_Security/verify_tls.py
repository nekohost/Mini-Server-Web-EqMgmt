"""Check the same R7 identity previously enrolled in production, using an isolated administrator fixture."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import ssl
import sys
import time
import uuid

from cryptography.fernet import Fernet
from dotenv import dotenv_values

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
TRIAL = Path(sys.argv[1]).resolve()
SOURCE = (TRIAL/'source') if sys.argv[2]=='staging' else ROOT
sys.path[:0] = [str(SOURCE/'tests'),str(SOURCE)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(SOURCE)
from test_equipment_ai import AssistantTests
from utils.ai_assistant.providers import PROTOCOL, LEGACY_GROUP
from utils.ai_assistant.worker import Worker

URL = 'https://192.168.0.14:8443'
FINGERPRINT = 'e3ffd864d9e80538139956a6d15e02c51ae62b61d1b0d9e042b5c4958adfbde9'
pem = (ROOT/'instance/releases/260strata-tls-4wqgb1p0/r7-public-ca.pem').read_text()
assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()==FINGERPRINT
dbpath = ROOT/'instance/ai/assistant.sqlite3'
with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
    previous = db.execute("SELECT r.base_url,r.credential FROM ai_provider_revisions r JOIN ai_providers p ON p.id=r.provider WHERE p.name='260Strata' AND r.revision=5").fetchone()
assert previous==(URL,'env:USER_AI_STRATA_KEY')
config = dotenv_values(Path.home()/'.config/eqmgmt/assistant-worker.env')
assert config['USER_AI_STRATA_URL']=='http://192.168.0.14:8080'
case=AssistantTests()
case.setUp()
try:
    case.login(1)
    case.app.config['USER_AI_PROVIDER_ENCRYPTION_KEY']=Fernet.generate_key().decode()
    def post(path, body, expected):
        response=case.client.post(path,json=body,headers=case.headers)
        if response.status_code!=expected:
            raise AssertionError((path,response.status_code,response.get_json().get('message')))
        return response.get_json()
    def internal(path,body):
        response=case.app.test_client().post(path,json=body,headers=case.worker_headers)
        assert response.status_code==200, (path,response.status_code)
        return response.get_json()
    pid=post('/api/admin/ai/providers', dict(name='R7 TLS verification',adapter='strata',base_url=URL,
             resource_group=LEGACY_GROUP,enabled=True,manual=False,revision=0,trust_mode='private',
             ca_pem=pem,api_key=config['USER_AI_STRATA_KEY']),201)['id']
    result=post(f'/api/admin/ai/providers/{pid}/discover',{'candidate_revision':1},200)
    candidate=next(x['candidate'] for x in result['providers'] if x['id']==pid)
    assert candidate['fingerprint']==FINGERPRINT and candidate['addresses']==['192.168.0.14']
    mid=next(x['id'] for x in candidate['models'] if x['upstream']=='qwen3.8-flash-next-iq3_xxs')
    sys.path.insert(0,str(ROOT/'tools'))
    from deploy_ai_ux_release import active_jobs
    if active_jobs():raise RuntimeError('production model busy; retry after normal completion')
    jid=post(f'/api/admin/ai/models/{mid}/probe',dict(client_key=uuid.uuid4().hex,provider_id=pid,
             candidate_revision=1,context_tokens=65536,tools=False,reasoning=False),202)['job_id']
    job=internal('/internal/ai/claim',{'worker':'isolated-tls','protocol':PROTOCOL})['job']
    assert job['id']==jid and job['route']['base_url']==URL
    worker=Worker('http://localhost',case.app.config['USER_AI_WORKER_TOKEN'],'http://127.0.0.1', '', 'fixture')
    worker.post=internal
    started=time.monotonic()
    worker.run_job(job)
    registry=case.app.extensions['equipment_assistant']['registry']
    with case.store.db() as db:
        row=db.execute('SELECT state,error_code FROM jobs WHERE id=?',(jid,)).fetchone()
        assert row['state']=='done', (row['state'],row['error_code'])
    assert next(p for p in registry.admin_list()['providers'] if p['id']==pid)['revision']==1
    out=dict(source=sys.argv[2],fixture_database=True,actual_upstream=True,public_ca_uploaded=True,
             fingerprint=FINGERPRINT,discovery=True,proof='done',seconds=round(time.monotonic()-started,2),
             production_provider_modified=False)
    (TRIAL/(sys.argv[2]+'-tls.json')).write_text(json.dumps(out,indent=2))
    print(json.dumps(out))
finally:
    case.doCleanups()
