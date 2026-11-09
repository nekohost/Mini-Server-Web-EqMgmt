"""Check both mail directions in the production browser with the ordinary test account."""
import base64
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import uuid

from verify_production_entry import BASE, LOGIN, ROOT, LiveBrowser, read_db, record


def state(owner, message):
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        rows=db.execute("""SELECT j.* FROM jobs j JOIN messages m ON m.job=j.id
                           WHERE j.owner=? AND m.role='user' AND m.content=?""",(owner,message)).fetchall()
    assert len(rows)<=1,'duplicate test job'
    return dict(rows[0]) if rows else None


def reload_chat(browser,cid):
    browser.navigate('/assistant')
    button='#ai-conversations button[data-conversation-id="'+cid+'"]'
    browser.wait_for("document.querySelector("+json.dumps(button)+")",'test chat listed')
    browser.script("const b=document.querySelector(arguments[0]);if(b.getAttribute('aria-current')!=='true')b.click()",button)
    browser.wait_for("document.querySelector('#equipment-ai')?.dataset.entry==='ready'",'chat restored')


def answers(browser):
    return browser.js("return Array.from(document.querySelectorAll('#ai-messages article[data-role=assistant] .ai-answer'),n=>n.textContent)")


def get_display(browser,answer):
    end=time.monotonic()+60
    while time.monotonic()<end:
        for text in answers(browser):
            if text and text.splitlines()[1:]==answer.splitlines()[1:]:
                return text
        time.sleep(.12)
    raise AssertionError('stored assistant content was not displayed')


def exercise(browser,owner,model_id,out,expected_cid,case):
    direction,level,rev,source=case
    language='한국어' if direction=='en-ko' else '영어'
    message=f'다음 이메일을 {language}로 번역해 주세요.\n\n'+source
    jid=state(owner,message)
    if jid is None:
        if expected_cid:
            reload_chat(browser,expected_cid)
        else:
            browser.navigate('/assistant')
            browser.wait_for("['draft','ready'].includes(document.querySelector('#equipment-ai')?.dataset.entry)",'assistant ready')
            browser.activate('#ai-new',False)
            browser.wait_for("document.querySelector('#equipment-ai')?.dataset.entry==='draft'",'new unsaved chat')
        browser.wait_for("Array.from(document.querySelectorAll('#ai-model option')).some(x=>x.value==="+json.dumps(model_id)+"&&!x.disabled)",'verified model available')
        browser.script("const s=document.querySelector('#ai-model'); if(s.value!==arguments[0]){s.value=arguments[0];s.dispatchEvent(new Event('change',{bubbles:true}))}",model_id)
        browser.wait_for("!document.querySelector('#ai-send').disabled",'send ready')
        browser.script("const b=document.querySelector('#ai-input');b.value=arguments[0];b.dispatchEvent(new Event('input',{bubbles:true}))",message)
        browser.activate('#ai-send',False)
        limit=time.monotonic()+45
        while jid is None and time.monotonic()<limit:
            time.sleep(.24)
            jid=state(owner,message)
        if not jid:
            raise RuntimeError('test message was not durably admitted; inspect before resubmission')
    cid=jid['conversation']
    assert expected_cid is None or cid==expected_cid
    while jid['state'] in ('queued','running','draining'):
        time.sleep(1)
        jid=state(owner,message)
    raw_route=json.loads(jid['route_snapshot'])
    assert raw_route['model']=='qwen3.8-flash-next-iq3_xxs' and raw_route['adapter']=='strata'
    assert raw_route['mail_translation']==direction and raw_route['mail_prompt_revision']==rev
    assert raw_route['reasoning_effort']==jid['level']==level
    assert json.loads(jid['context'])==[{'role':'user','content':source}]
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        msg=db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'",(jid['id'],)).fetchall()
        steps=db.execute('SELECT step,content FROM message_steps WHERE job=? ORDER BY step',(jid['id'],)).fetchall()
        n=db.execute('SELECT COUNT(*) FROM proposals WHERE job=?',(jid['id'],)).fetchone()[0]
    assert len(msg)==len(steps)==1 and steps[0][0]==0 and n==0
    safe={k:raw_route[k] for k in ('provider_name','revision','adapter','model','reasoning_effort','mail_translation','mail_prompt_revision')}
    evidence=dict(direction=direction,job=jid['id'],conversation=cid,owner_login=LOGIN,state=jid['state'],error=jid['error'],
                  source=source,raw=steps[0][1],stored=msg[0][0],settings=safe,steps=jid['steps'],proposals=n,
                  context_contains_only_this_mail=True, elapsed_s=round(jid['updated']-jid['created'],2))
    record(out/(direction+'.json'),evidence)
    if jid['state']!='done':
        raise RuntimeError('first actual mail stopped: '+str(jid['error_code']))
    if not browser.js("return location.pathname==='/assistant'"):
        reload_chat(browser,cid)
    shown=get_display(browser,msg[0][0])
    reload_chat(browser,cid)
    after=get_display(browser,msg[0][0])
    assert shown==after
    evidence.update(display=shown,restored_same=True)
    record(out/(direction+'.json'),evidence)
    nodes=browser.call('POST',browser.sid+'/elements',{'using':'css selector','value':'#ai-messages article[data-role=assistant] .ai-answer'})
    for node in nodes:
        key=next(iter(node.values()))
        text=browser.call('GET',browser.sid+'/element/'+key+'/property/textContent')
        if text==shown:
            shot=browser.call('GET',browser.sid+'/element/'+key+'/screenshot')
            (out/(direction+'.png')).write_bytes(base64.b64decode(shot))
            break
    print(direction,jid['state'],evidence['elapsed_s'],flush=True)
    return cid


def main():
    if socket.gethostname()!='nkhst-pentium':raise RuntimeError('production fixture host mismatch')
    out=Path(sys.argv[1]).resolve()
    if out.parent.parent!=ROOT/'instance/releases' or out.name!='live-mail' or not out.parent.name.startswith('20261105-ai-ux-mail-'):
        raise ValueError('production evidence path mismatch')
    os.umask(0o077)
    out.mkdir(mode=0o700,exist_ok=True)
    if (out/'verified.json').exists():raise RuntimeError('already verified')
    with read_db(ROOT/'equipment.db') as db:
        user=db.execute("SELECT UserId,Role,IsDeleted,IsDeactivated FROM users WHERE LoginId=?",(LOGIN,)).fetchone()
        assert user and user[1]=='user' and all((v or 'N')=='N' for v in user[2:])
        owner=user[0]
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        model=db.execute("SELECT m.id FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider WHERE m.upstream=? AND p.name=? AND p.enabled=1 AND p.retired=0 AND m.published=1 AND m.present=1",('qwen3.8-flash-next-iq3_xxs','260Strata')).fetchall()
        assert len(model)==1
    mark=out.parent.name[-6:]
    cases=[('en-ko','xhigh','mail-20261109-r2','Subject: Inspection form '+mark+'\n\nDear Lee,\n\nFacilities may sign off by email. Only Security must sign the original paper form. Neither approval has been received. Keep the pass in the cabinet until both are recorded.\n\nRegards,\nRobin'),
           ('ko-en','low','mail-20261110-contact-r4','제목: 반납 안내 '+mark+'\n\n민지님, 안녕하세요.\n\n담당자는 그대로이고 담당자의 연락처 중 내선 번호만 변경되었습니다. 안내문에서 내선 번호만 수정해 주세요. 담당자 이름과 접수 날짜는 바꾸지 마세요.\n\n감사합니다.\n유진 드림')]
    password=sys.stdin.readline().rstrip('\r\n')
    assert password
    with tempfile.TemporaryDirectory(prefix='eq-release-mail-') as profile:
        browser=LiveBrowser(profile,1380,960)
        try:
            browser.navigate('/login')
            browser.wait_for("document.querySelector('#loginForm') && typeof window.getCSRFToken==='function'",'normal login')
            browser.script("document.getElementById('LoginId').value=arguments[0];document.getElementById('Password').value=arguments[1];document.getElementById('loginForm').requestSubmit()",LOGIN,password)
            del password
            browser.wait_for("location.origin==='https://nekohost.org' && location.pathname!=='/login' && document.readyState!=='loading'",'ordinary user login')
            cid=None
            for case in cases:
                cid=exercise(browser,owner,model[0][0],out,cid,case)
            record(out/'verified.json',dict(status='pass',site=BASE,account=LOGIN,conversation=cid,directions=['en-ko','ko-en'],
                                          chromium=browser.cdp('Browser.getVersion',{})['product'],reopened=True))
        finally:
            browser.close()


if __name__=='__main__':
    main()
