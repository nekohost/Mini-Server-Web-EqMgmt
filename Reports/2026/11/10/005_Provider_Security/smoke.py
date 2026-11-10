"""Verify the public HTTPS entry point, normal-user permissions, HTTP model answer and revoked cookie."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

import requests

root=Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
trial=Path(sys.argv[1]).resolve()
release=json.loads((trial/'release-result.json').read_text())
site='https://nekohost.org'
account='test04'
db=root/'equipment.db'
model='qwen3.8-flash-next-iq3_xxs'
with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
    assert conn.execute("SELECT Role FROM users WHERE LoginId=? AND IsDeleted='N' AND IsDeactivated='N'",(account,)).fetchone()==('user',)
    last_log=conn.execute('SELECT COALESCE(MAX(rowid),0) FROM access_logs').fetchone()[0]
with sqlite3.connect((root/'instance/ai/assistant.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
    rows=conn.execute("""SELECT m.id,r.base_url,p.revision FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider
            JOIN ai_provider_revisions r ON r.provider=p.id AND r.revision=p.revision WHERE p.name='260Strata'
            AND p.enabled=1 AND p.retired=0 AND m.upstream=? AND m.present=1 AND m.published=1""",(model,)).fetchall()
assert len(rows)==1 and rows[0][1:] == ('http://192.168.0.14:8080',6)
session=requests.Session()
session.trust_env=False
session.headers.update(Origin=site)
login=session.get(site+'/login',timeout=12)
login.raise_for_status()
before=re.search(r'<meta name="csrf-token" content="([^"]+)"',login.text)[1]
password=sys.stdin.readline().rstrip('\r\n')
assert password
auth=session.post(site+'/login',json={'LoginId':account,'Password':password},headers={'X-CSRFToken':before},timeout=15)
assert auth.status_code==200 and auth.json().get('success'), ('test login',auth.status_code)
page=session.get(site+'/assistant',timeout=12)
assert page.url==site+'/assistant' and page.ok
csrf=re.search(r'data-csrf="([^"]+)"',page.text)[1]
headers={'X-CSRFToken':csrf}
blocked=session.get(site+'/api/admin/ai/providers',timeout=12)
assert blocked.status_code==403, blocked.status_code
assert session.get(site+f'/api/access_logs/{last_log}/payload',timeout=12).status_code==403
no_token=session.post(site+'/api/admin/ai/providers',json={},timeout=12)
assert no_token.status_code==403
payload={'content':'장비관리 연결 점검입니다. 연결 정상이면 “연결 정상”이라고 한 줄로 답해 주세요.',
         'selection_id':rows[0][0], 'level':'low','reasoning_version':2,
         'client_key':hashlib.sha256(('provider-security-smoke:'+release['commit']).encode()).hexdigest()[:32]}
started=time.monotonic()
send=session.post(site+'/api/ai/conversations/first-turn',json=payload,headers=headers,timeout=12)
assert send.status_code in (200,202), ('submit',send.status_code,send.json().get('message'))
jid=send.json()['job_id']
while True:
    response=session.get(site+'/api/ai/jobs/'+jid,timeout=15)
    response.raise_for_status()
    result=response.json()
    if result['state'] in ('done','failed','cancelled','recovery_required','waiting_confirmation'):break
    time.sleep(1)
assert result['state']=='done' and result['content'].strip(), (result['state'],result.get('error_code'))
elapsed=round(time.monotonic()-started,2)
stale=requests.Session()
stale.trust_env=False
stale.cookies.update(session.cookies)
logout=session.post(site+'/logout',headers=headers,allow_redirects=False,timeout=12)
assert logout.status_code in (200,302,303)
expired=stale.get(site+'/api/ai/capabilities',allow_redirects=False,timeout=12)
assert expired.status_code==401, expired.status_code
rows_audit=[]
for _ in range(15):
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
        rows_audit=conn.execute("SELECT RequestPayload,ResponsePayload FROM access_logs WHERE rowid>? AND RequestPath='/login' AND HttpMethod='POST' AND StatusCode=200",(last_log,)).fetchall()
    if rows_audit:break
    time.sleep(1)
assert rows_audit and all(password not in str(row) for row in rows_audit)
del password
out={'ordinary_user_http_chat':'done','peer_scheme':'http','revision':rows[0][2],'model':model,
     'answer_characters':result['content_length'],'elapsed_seconds':elapsed,'admin_api_status':blocked.status_code,
     'stale_cookie_status':expired.status_code,'ordinary_audit_payload_status':403,'login_audited_without_password':True,
     'https_public_entry':True,'client_certificate_used':False}
(trial/'production-smoke.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
