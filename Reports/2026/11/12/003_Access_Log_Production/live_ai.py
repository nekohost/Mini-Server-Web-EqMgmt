"""Verify one ordinary user's real browser turn and its metadata on the deployed service."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import tempfile
import time

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'Reports/2026/11/09/007_AI_Conversation_Entry_Release'))
sys.path.insert(0, str(ROOT/'Reports/2026/11/10/001_AI_Mail_Translation_Release'))
from verify_production_entry import LOGIN, LiveBrowser
from verify_live_mail import reload_chat, state


def read_db(name):
    db = sqlite3.connect((ROOT/name).as_uri()+'?mode=ro', uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def terminal_job(owner, question):
    while True:
        item = state(owner, question)
        if item and item['state'] in ('failed','cancelled','recovery_required','done'):
            return item
        time.sleep(.75)


def verify(release):
    assert socket.gethostname() == 'nkhst-pentium' and LOGIN == 'test04'
    assert release.parent == ROOT/'instance/releases'
    activation = json.loads((release/'activation.json').read_text())
    mark = hashlib.sha256(release.name.encode()).hexdigest()[:7]
    left, right = 20 + int(mark[:2],16)%27, 7 + int(mark[2:4],16)%14
    answer = str(left+right)
    question = f'운영 점검 {mark}. {left}와 {right}를 더한 값만 숫자로 답해 주세요.'
    with closing(read_db('equipment.db')) as db:
        user = db.execute('SELECT UserId,Role,IsDeleted,IsDeactivated,SessionToken FROM users WHERE LoginId=?',(LOGIN,)).fetchone()
        assert user and user['Role']=='user' and user['IsDeleted']=='N' and user['IsDeactivated']=='N'
        assert not user['SessionToken'], 'dedicated test user already has an active session'
        owner = user['UserId']
        begin = db.execute('SELECT MAX(LogId) FROM access_logs').fetchone()[0]
    evidence_start = release/'live-start.json'
    if evidence_start.exists():
        begin = json.loads(evidence_start.read_text())['log_bound']
    else:
        with evidence_start.open('x') as recorded:
            json.dump({'log_bound':begin},recorded)
    password = sys.stdin.readline().rstrip('\r\n')
    if not password:
        raise RuntimeError('Missing ordinary test account credential')
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='access-release-chrome-') as chrome_profile:
        b = LiveBrowser(chrome_profile,1280,800)
        signed_in = False
        try:
            b.navigate('/login')
            b.wait_for("location.origin==='https://nekohost.org' && document.getElementById('loginForm')"
                       " && typeof window.getCSRFToken==='function'",'HTTPS login')
            b.script("document.querySelector('#LoginId').value=arguments[0];"
                     "document.querySelector('#Password').value=arguments[1];document.querySelector('#loginForm').requestSubmit()",
                     LOGIN,password)
            del password
            b.wait_for("location.origin==='https://nekohost.org' && location.pathname!=='/login'",'ordinary portal')
            signed_in = True
            existing = state(owner,question)
            b.navigate('/assistant')
            b.wait_for("['ready','draft'].includes(document.querySelector('#equipment-ai')?.dataset.entry)",'assistant opened')
            if not existing:
                b.activate('#ai-new',False)
                b.wait_for("document.querySelector('#equipment-ai').dataset.entry==='draft'",'new draft')
                b.wait_for("Array.from(document.querySelectorAll('#ai-model option')).some(o=>o.value&&!o.disabled)",
                           'verified model available')
                b.script("const s=document.querySelector('#ai-model');if(!s.selectedOptions[0]?.value || "
                         "s.selectedOptions[0].disabled){const a=Array.from(s.options).filter(o=>o.value&&!o.disabled);"
                         "if(a.length===1){s.value=a[0].value;s.dispatchEvent(new Event('change',{bubbles:true}))}}")
                b.script("const x=document.getElementById('ai-input'); x.value=arguments[0];"
                         "x.dispatchEvent(new Event('input',{bubbles:true}));",question)
                b.wait_for("!document.querySelector('#ai-send').disabled",'send enabled')
                posted = time.monotonic()
                b.activate('#ai-send',False)
                for _ in range(180):
                    if state(owner,question):
                        break
                    time.sleep(.25)
                else:
                    raise RuntimeError('first turn was not accepted')
            else:
                posted = time.monotonic()
                reload_chat(b,existing['conversation'])
            job = terminal_job(owner,question)
            assert job['state']=='done', ('terminal job',job['state'],job.get('error_code'))
            elapsed = round(time.monotonic()-posted,2)
            with closing(read_db('instance/ai/assistant.sqlite3')) as db:
                stored = db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'",(job['id'],)).fetchall()
                assert len(stored)==1
                raw = stored[0]['content'].strip()
                assert re.findall(r'\d+',raw)==[answer], 'unexpected answer to synthetic arithmetic'
                singleton = db.execute("SELECT COUNT(*) FROM messages WHERE role='user' AND content=? AND job=?",
                                       (question,job['id'])).fetchone()[0]
                assert singleton==1
            selector = '#ai-messages article[data-role=assistant] .ai-answer'
            check = ("Array.from(document.querySelectorAll("+json.dumps(selector)+"), n=>n.textContent.trim())"
                     ".some(t=>JSON.stringify(t.match(/\\d+/g))==="+json.dumps(json.dumps([answer],separators=(',',':')))+")")
            b.wait_for(check,'answer on screen')
            reload_chat(b,job['conversation'])
            b.wait_for(check,'answer after reopening')
            browser_version = b.cdp('Browser.getVersion',{})['product']
            with closing(read_db('equipment.db')) as db:
                scopes = (begin,'/api/ai/conversations/first-turn','/api/ai/jobs/'+job['id'],
                          '/api/ai/conversations/'+job['conversation']+'/messages','/assistant')
                for _ in range(45):
                    rows=db.execute("SELECT RequestPath,StatusCode,RequestPayload,ResponsePayload FROM access_logs "
                                    "WHERE LogId>? AND RequestPath IN (?,?,?,?)",scopes).fetchall()
                    actions=[(r['RequestPath'],r['StatusCode']) for r in rows]
                    if all(pair in actions for pair in [(scopes[1],202),(scopes[2],200),(scopes[3],200),(scopes[4],200)]):
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError('real browser access receipts incomplete')
                assert all(r['RequestPayload'] is None and r['ResponsePayload'] is None for r in rows)
                internal = db.execute("SELECT COUNT(*) FROM access_logs WHERE LogId>? AND "
                                      "(RequestPath='/internal/ai/claim' OR RequestPath GLOB ?) AND StatusCode BETWEEN 200 AND 299",
                                      (begin,'/internal/ai/jobs/'+job['id']+'/*')).fetchone()[0]
                assert internal==0, 'unexpected normal worker access records'
            report={'status':'pass','production_commit':activation['commit'],'https_origin':'https://nekohost.org',
                    'account':LOGIN,'browser':browser_version,'arithmetic':f'{left} + {right} = {answer}',
                    'real_job':'done','user_messages_for_turn':singleton,'assistant_messages_for_turn':len(stored),
                    'onscreen':True,'onscreen_after_reopen':True,'user_http_metadata_rows':len(rows),
                    'first_turn_status':202,'poll_and_reopen_status':200,'ai_body_copies':0,'normal_worker_rows':internal,
                    'provider_model':json.loads(job['route_snapshot'])['model'],
                    'send_to_terminal_seconds':elapsed, 'existing_test_turn_reused':bool(existing)}
        finally:
            try:
                if signed_in:
                    # The owned test session ends through the same CSRF-protected logout as the normal browser.
                    logout = b.call('POST', b.sid+'/execute/async', {'script':
                        "const done=arguments[arguments.length-1]; (async()=>{const c=document.querySelector('#equipment-ai')?.dataset.csrf"
                        "||window.getCSRFToken?.();let r=await fetch('/logout',{method:'POST',"
                        "credentials:'same-origin',headers:{'X-CSRFToken':c}});done(r.ok)})().catch(()=>done(false));",'args':[]})
                    assert logout is True
            finally:
                b.close()
    with closing(read_db('equipment.db')) as db:
        assert not db.execute('SELECT SessionToken FROM users WHERE UserId=?',(owner,)).fetchone()[0]
    report.update(test_session_logged_out=True,total_seconds=round(time.monotonic()-t0,2))
    (release/'live-ai.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    os.umask(0o077)
    verify(Path(sys.argv[1]).resolve())
