"""Exercise two previously unused, synthetic work emails through the authenticated production UI."""
import base64
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
sys.path.extend([str(ROOT), str(ROOT/'Reports/2026/11/09/007_AI_Conversation_Entry_Release'),
                 str(ROOT/'Reports/2026/11/10/001_AI_Mail_Translation_Release')])
from verify_production_entry import BASE, LOGIN, LiveBrowser, read_db, record
from verify_live_mail import reload_chat, state

MODEL = 'qwen3.8-flash-next-iq3_xxs'
PROBES = (
    ('en-ko', 'xhigh', 'Could you translate this message into natural Korean?',
     'Hello Riley,\n\nThe spare sensor is on loan from the distributor. We still own the test stand. Please ask for a collection window; we have not agreed to cover the freight.\n\nRegards,\nLuca'),
    ('ko-en', 'low', '아래 메일을 자연스러운 업무용 영어로 옮겨 주세요.',
     '제목: 납품 서류 대조\n\n안녕하세요.\n\n창고에서 받은 납품 명세서에는 여섯 상자가 적혀 있습니다. 실제로 도착한 수량은 아직 대조 중입니다. 차이가 확인되면 명세서 사본만 보내 주세요.\n\n감사합니다.\n한서린 드림'),
)


def visible_answer(browser, stored):
    # Only the mail presenter's optional bold/Markdown subject markers may disappear.
    first, sep, rest = stored.partition('\n')
    plain = re.sub(r'^#{1,4}\s+|[*]', '', first) + sep + rest if re.match(r'^(?:#{1,4}\s*)?[*]*(Subject|제목)[*]*\s*[:：]', first, re.I) else stored
    selector = '#ai-messages article[data-role=assistant] .ai-answer'
    browser.wait_for('Array.from(document.querySelectorAll('+json.dumps(selector)+')).some(n=>'
                     +json.dumps([stored,plain],ensure_ascii=False)+'.includes(n.textContent))','exact completed mail')
    for elem in browser.call('POST',browser.sid+'/elements',{'using':'css selector','value':selector}):
        node = browser.sid+'/element/'+next(iter(elem.values()))
        text = browser.call('GET',node+'/property/textContent')
        if text in (stored,plain):
            return text, node
    raise AssertionError('completed mail element absent')


def verify(browser, owner, model, release, previous, probe):
    direction, effort, instruction, source = probe
    message = instruction+'\n\n'+source
    existing = state(owner,message)
    if existing:
        reload_chat(browser,existing['conversation'])
    else:
        if previous:
            reload_chat(browser,previous)
        else:
            browser.navigate('/assistant')
            browser.wait_for("['ready','draft'].includes(document.querySelector('#equipment-ai')?.dataset.entry)",'assistant ready')
            browser.activate('#ai-new',False)
            browser.wait_for("document.querySelector('#equipment-ai')?.dataset.entry==='draft'",'new unsaved chat')
        browser.wait_for("Array.from(document.querySelectorAll('#ai-model option')).some(x=>x.value==="+json.dumps(model)+"&&!x.disabled)",'verified model')
        browser.script("const s=document.querySelector('#ai-model');if(s.value!==arguments[0]){s.value=arguments[0];s.dispatchEvent(new Event('change',{bubbles:true}))}",model)
        browser.script("const t=document.querySelector('#ai-input');t.value=arguments[0];t.dispatchEvent(new Event('input',{bubbles:true}))",message)
        browser.wait_for("!document.querySelector('#ai-send').disabled",'send ready')
        browser.activate('#ai-send',False)
        for _ in range(180):
            existing=state(owner,message)
            if existing:
                break
            time.sleep(.25)
        if not existing:
            raise RuntimeError('no durable admission; inspect before resubmitting')
    assert previous is None or existing['conversation']==previous
    while existing['state'] in ('queued','running','draining'):
        time.sleep(1)
        existing=state(owner,message)
    route=json.loads(existing['route_snapshot'])
    assert json.loads(existing['context'])==[{'role':'user','content':source}]
    assert route['provider_name']=='260Strata' and route['model']==MODEL and route['adapter']=='strata'
    assert route['mail_translation']==direction and route['reasoning_effort']==effort==existing['level']
    expected=json.loads((release/'expected-live.json').read_bytes())[direction]
    assert all(route.get(k)==v for k,v in expected.items()), (direction,expected.keys())
    out=release/'live-mail'
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        job=(existing['id'],)
        steps=db.execute('SELECT content FROM message_steps WHERE job=? ORDER BY step',job).fetchall()
        display=db.execute("SELECT content FROM messages WHERE role='assistant' AND job=?",job).fetchall()
        proposals=db.execute('SELECT count(*) FROM proposals WHERE job=?',job).fetchone()[0]
    assert len(steps)==len(display)==1 and proposals==0
    result={'direction':direction,'instruction':instruction,'source':source,'model':MODEL,'provider':route['provider_name'],
            'reasoning_effort':effort,'writing_revision':route.get('mail_writing_revision'),
            'correspondence_revision':route.get('mail_correspondence_revision'),'fidelity_revision':route.get('mail_fidelity_revision'),'state':existing['state'],'error':existing['error'],
            'seconds':round(existing['updated']-existing['created'],2),'model_steps':len(steps),'proposals':proposals,
            'raw':steps[0][0],'stored':display[0][0],'scope_only_current_mail':True}
    record(out/(direction+'.json'),result)
    assert existing['state']=='done',result['error']
    first,_=visible_answer(browser,result['stored'])
    reload_chat(browser,existing['conversation'])
    after,node=visible_answer(browser,result['stored'])
    assert first==after
    image=browser.call('GET',node+'/screenshot')
    (out/(direction+'.png')).write_bytes(base64.b64decode(image))
    result.update(display=after,restored_same=True)
    record(out/(direction+'.json'),result)
    print(direction,result['seconds'],'done',flush=True)
    return existing['conversation']


def main():
    release=Path(sys.argv[1]).resolve()
    if socket.gethostname()!='nkhst-pentium' or release.parent!=ROOT/'instance/releases' or not release.name.startswith('20261105-ai-ux-mail-fidelity-'):
        raise RuntimeError('unexpected release destination')
    os.umask(0o077)
    out=release/'live-mail'
    out.mkdir(exist_ok=True,mode=0o700)
    assert not (out/'verified.json').exists()
    with read_db(ROOT/'equipment.db') as db:
        owner=db.execute("SELECT UserId,Role,IsDeleted,IsDeactivated FROM users WHERE LoginId=?",(LOGIN,)).fetchone()
        assert owner and owner[1]=='user' and all((v or 'N')=='N' for v in owner[2:])
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        models=db.execute("SELECT m.id FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider WHERE m.upstream=? AND p.name='260Strata' AND p.enabled=1 AND p.retired=0 AND m.published=1 AND m.present=1",(MODEL,)).fetchall()
        assert len(models)==1
    password=sys.stdin.readline().rstrip('\r\n')
    assert password
    with tempfile.TemporaryDirectory(prefix='equipment-mail-four-browser-') as profile:
        browser=LiveBrowser(profile,1380,960)
        try:
            browser.navigate('/login')
            browser.wait_for("document.querySelector('#loginForm') && typeof window.getCSRFToken==='function'",'login')
            browser.script("document.querySelector('#LoginId').value=arguments[0];document.querySelector('#Password').value=arguments[1];document.querySelector('#loginForm').requestSubmit()",LOGIN,password)
            del password
            browser.wait_for("location.origin==='https://nekohost.org' && location.pathname!=='/login' && document.readyState!=='loading'",'ordinary login')
            conversation=None
            for probe in PROBES:
                conversation=verify(browser,owner[0],models[0][0],release,conversation,probe)
            record(out/'verified.json',{'status':'pass','role':'user','account':LOGIN,'origin':BASE,'same_conversation':True,
                    'restored_both':True,'chromium':browser.cdp('Browser.getVersion',{})['product']})
        finally:
            browser.close()


if __name__=='__main__':
    main()
