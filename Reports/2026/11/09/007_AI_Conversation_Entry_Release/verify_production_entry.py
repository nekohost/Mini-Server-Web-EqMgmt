"""Opt-in production verification using a dedicated ordinary account, public HTTPS and read-only SQLite counts.

Run on the equipment host with the release proof directory and pass the test account's password on stdin.
The two marked, terminal test conversations are moved to the account's trash using the authenticated API.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import tempfile
import time
import uuid

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
BASE = 'https://nekohost.org'
LOGIN = 'test04'
sys.path.insert(0, str(ROOT/'tests'))
from capture_ai_conversation_entry import Browser


class LiveBrowser(Browser):
    """Use the release-tested WebDriver harness with normal HTTPS resolution and certificate checks."""
    def call(self, method, path, data=None):
        if method == 'POST' and path == '/session':
            args = data['capabilities']['alwaysMatch']['goog:chromeOptions']['args']
            args[:] = [a for a in args if not a.startswith('--host-resolver-rules=')]
        return super().call(method, path, data)

    def script(self, script, *args):
        return self.call('POST', self.sid+'/execute/sync', {'script':script, 'args':list(args)})

    def navigate(self, path):
        self.call('POST', self.sid+'/url', {'url':BASE+path})

    def wait_for(self, condition, label):
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            if self.js('return Boolean('+condition+')'):
                return
            time.sleep(.055)
        raise RuntimeError('Browser condition did not resolve: '+label)

    def activate(self, selector, touch):
        selector_json = json.dumps(selector)
        node = self.call('POST', self.sid+'/element', {'using':'css selector', 'value':selector})
        if not touch:
            self.call('POST', self.sid+'/element/'+next(iter(node.values()))+'/click', {})
            return
        point = self.js("const x=document.querySelector("+selector_json+"); x.scrollIntoView({block:'nearest'}); const r=x.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}")
        self.cdp('Input.dispatchTouchEvent', {'type':'touchStart', 'touchPoints':[point]})
        self.cdp('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})


MONITOR = """
if(location.pathname==='/assistant'){
 const p=window.entryQA={frames:0,welcome:0,freshTitle:0,empty:0,loading:0,errors:0,observe:true,posts:[],receipts:[],uiPosts:0,stage:'',released:{},hold:sessionStorage.qahold==='yes',mode:'',metrics() {return {frames:this.frames,welcome:this.welcome,new_title:this.freshTitle,false_empty:this.empty,loading:this.loading,errors:this.errors,overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),width:innerWidth,height:innerHeight};}};
 const shown=window.qashown=x=>!!(x&&!x.hidden&&x.getClientRects().length&&getComputedStyle(x).visibility!=='hidden');
 const by=window.qaby=id=>document.getElementById(id);
 addEventListener('error',e=>{if(e.message)p.errors++});
 function frame(){
   const root=by('equipment-ai');
   if(root&&by('ai-welcome')&&p.observe){
     p.frames++; if(root.dataset.entry==='loading')p.loading++;
     if(shown(by('ai-welcome')))p.welcome++;
     if(shown(by('ai-title'))&&/새로운 대화|새 대화/.test(by('ai-title').textContent))p.freshTitle++;
     if(shown(by('ai-list-empty')))p.empty++;
   }
   requestAnimationFrame(frame);
 }
 requestAnimationFrame(frame);
 const fetchReal=window.fetch.bind(window);
 window.fetch=async function(input,options={}){
   const u=new URL(typeof input==='string'?input:input.url,location.href);
   const method=(options.method||(input&&input.method)||'GET').toUpperCase();
   if(u.origin!==location.origin)return fetchReal(input,options);
   if(method==='POST'&&u.pathname.startsWith('/api/ai/'))p.posts.push(u.pathname);
   if(method==='POST'&&u.pathname==='/api/ai/conversations/first-turn'&&p.mode){
     p.uiPosts++;
     const first=p.uiPosts===1;
     const attempts=first?2:1;
     const replies=await Promise.all(Array.from({length:attempts},()=>fetchReal(input,options)));
     for(const response of replies){
       const ack=await response.clone().json();
       p.receipts.push({status:response.status,conversation:ack.conversation_id,job:ack.job_id});
     }
     if(first&&p.mode==='lose')throw new TypeError('Test browser suppressed the acknowledged reply');
     return replies[0];
   }
   const response=await fetchReal(input,options);
   let stage='';
   if(method==='GET'&&u.pathname==='/api/ai/conversations'&&u.searchParams.get('resume')==='1')stage='list';
   if(method==='GET'&&u.pathname.endsWith('/messages'))stage='body';
   if(p.hold&&stage&&!p.released[stage]){
     p.stage=stage;
     await new Promise(resolve=>{p.release=()=>{p.released[stage]=true;resolve()};});
   }
   return response;
 };
}
"""


def read_db(path):
    """Open a production database without permission to mutate or create it."""
    db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=12)
    db.row_factory = sqlite3.Row
    return db


def counts(owner):
    """Measure the test account's conversation, user-message, response and job rows in one snapshot."""
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        db.execute('BEGIN')
        return [db.execute(sql,(owner,)).fetchone()[0] for sql in (
            'SELECT COUNT(*) FROM conversations WHERE owner=?',
            "SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id=m.conversation WHERE c.owner=? AND m.role='user'",
            "SELECT COUNT(*) FROM messages m JOIN conversations c ON c.id=m.conversation WHERE c.owner=? AND m.role='assistant'",
            'SELECT COUNT(*) FROM jobs WHERE owner=?')]


def inspect_turn(owner, cid, jid, question):
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        db.execute('BEGIN')
        job=db.execute('SELECT state,error_code FROM jobs WHERE id=? AND conversation=? AND owner=?',(jid,cid,owner)).fetchone()
        assert job and db.execute('SELECT COUNT(*) FROM conversations WHERE owner=? AND id=? AND title=? AND is_deleted=0',(owner,cid,question)).fetchone()[0]==1
        rows=db.execute('SELECT role,content FROM messages WHERE conversation=? AND job=?',(cid,jid)).fetchall()
        assert [r['content'] for r in rows if r['role']=='user']==[question] and sum(r['role']=='assistant' for r in rows)==1
        return job['state'],job['error_code'],sum(len(r['content'] or '') for r in rows if r['role']=='assistant')


def record(path, data):
    tmp=path.with_suffix('.pending')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def capture(b,folder,label,question=None):
    """Observe the normal restoration and separately hold actual list/body responses in this browser only."""
    b.js("sessionStorage.qahold='"+('yes' if label=='held' else 'no')+"'")
    b.navigate('/assistant')
    if label=='held':
        for step in ('list','body'):
            b.wait_for("window.entryQA?.stage==='"+step+"' && entryQA.loading>=2",step+' response arrived')
            assert b.js("return !qashown(qaby('ai-welcome')) && !qashown(qaby('ai-title'))")
            b.snap(folder,'01-list-pending' if step=='list' else '02-body-pending')
            b.js("entryQA.release()")
    b.wait_for("window.entryQA && qaby('equipment-ai')?.dataset.entry==='ready' && qaby('ai-messages').children.length>0 && !qaby('ai-send').disabled",'existing conversation ready')
    b.wait_for('entryQA.frames>=3','browser painted')
    stats=b.js('entryQA.observe=false;return entryQA.metrics()')
    assert all(stats[k]==0 for k in ('welcome','new_title','false_empty','overflow')),stats
    if label=='held':
        assert b.script("return qaby('ai-title').textContent===arguments[0]",question)
        b.snap(folder,'03-restored')
    return stats


def new_draft(b,touch):
    if touch and b.js("return qaby('ai-menu-toggle').getAttribute('aria-expanded')!=='true'"):
        b.activate('#ai-menu-toggle',True)
    b.activate('#ai-new',touch)
    b.wait_for("qaby('equipment-ai').dataset.entry==='draft' && qashown(qaby('ai-welcome')) && !qaby('ai-send').disabled",'unsaved draft')


def run_device(b, out, owner, name, width, height, marker):
    """Send one distinct UI submission on this device; clone its authentic HTTP request to test server idempotency."""
    folder=out/name
    folder.mkdir(mode=0o700,exist_ok=True)
    mobile=width<600
    question=f'운영 화면 점검 {marker} {"모바일" if mobile else "PC"}. 확인이라고만 답해 주세요.'
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        assert not db.execute('SELECT 1 FROM conversations WHERE owner=? AND title=?',(owner,question)).fetchone(), 'Test question exists; inspect previous run before retrying'
    b.cdp('Emulation.setDeviceMetricsOverride',dict(width=width,height=height,deviceScaleFactor=1,mobile=mobile))
    b.cdp('Emulation.setTouchEmulationEnabled',dict(enabled=mobile,**({'maxTouchPoints':5} if mobile else {})))
    baseline=counts(owner)
    natural=capture(b,folder,'natural')
    assert counts(owner)==baseline and (natural['width'],natural['height'])==(width,height)
    new_draft(b,mobile);new_draft(b,mobile)
    b.snap(folder,'04-unsaved')
    b.js("const box=qaby('ai-input');box.value='작성 중인 초안';box.dispatchEvent(new Event('input'));box.value='   ';qaby('ai-form').requestSubmit()")
    assert b.js('return entryQA.posts.length')==0 and counts(owner)==baseline
    capture(b,folder,'natural')
    new_draft(b,mobile)
    b.js("const s=qaby('ai-level');if(s.querySelector('option[value=off]:not(:disabled)')){s.value='off';s.dispatchEvent(new Event('change'))}")
    assert b.js('return entryQA.posts.length')==0 and counts(owner)==baseline
    b.script("entryQA.mode=arguments[0];const box=qaby('ai-input');box.value=arguments[1];box.dispatchEvent(new Event('input',{bubbles:true}));", 'lose' if mobile else 'duplicate', question)
    b.activate('#ai-send',mobile)
    b.js("qaby('ai-form').requestSubmit();qaby('ai-send').click()")
    if mobile:
        b.wait_for("qashown(qaby('ai-first-uncertain')) && !qaby('ai-first-retry').disabled", 'lost receipt shown')
        b.js("qaby('ai-input').value='다음 질문 초안';qaby('ai-input').dispatchEvent(new Event('input',{bubbles:true}))")
        b.activate('#ai-first-retry',True)
    b.wait_for("entryQA.receipts.length>="+str(3 if mobile else 2)+" && qaby('equipment-ai').dataset.entry==='ready'",'first acceptance')
    returned=b.js('return entryQA.receipts')
    assert len(returned)==(3 if mobile else 2) and all(r['status']==202 for r in returned), 'HTTP receipt count or status'
    ack=returned[0]
    assert re.fullmatch(r'[a-f0-9]{32}',ack['conversation']) and re.fullmatch(r'[a-f0-9]{32}',ack['job']) and all(r==ack for r in returned), 'Duplicate receipts differ'
    assert b.js('return entryQA.uiPosts')==(2 if mobile else 1)
    if mobile:
        assert b.js("return qaby('ai-input').value==='다음 질문 초안'")
    cid,jid=ack['conversation'],ack['job']
    assert b.script("return qaby('ai-title').textContent===arguments[0]",question)
    delta=[a-z for a,z in zip(counts(owner),baseline)]
    assert delta==[1,1,1,1],delta
    b.snap(folder,'05-first-accepted')
    state,code,answer_len=inspect_turn(owner,cid,jid,question)
    print(name,'one chat, one turn and one job; worker state',state,flush=True)
    while state in ('queued','running','draining'):
        time.sleep(2)
        state,code,answer_len=inspect_turn(owner,cid,jid,question)
    assert state=='done' and answer_len>0, ('test turn end state',state,code)
    held=capture(b,folder,'held',question)
    data=dict(viewport=[width,height],touch_emulation=mobile,natural=natural,held=held,before_first_delta=[0,0,0,0],
              saved_delta=delta,rapid_submit_actions=3,ui_first_post_before_retry=1,http_202_receipts=len(returned),
              same_conversation_and_job=True,lost_first_reply_recovered=mobile,next_draft_preserved=mobile,
              worker_state=state,nonempty_model_reply=True)
    record(folder/'result.json',data)
    return data, cid, question


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    out=args.directory.resolve()
    assert socket.gethostname()=='nkhst-pentium' and out.parent.parent==(ROOT/'instance/releases') and out.name=='live-browser'
    assert out.parent.name.startswith('20261105-ai-ux-entry-')
    os.umask(0o077)
    out.mkdir(mode=0o700,exist_ok=True)
    with read_db(ROOT/'equipment.db') as db:
        row=db.execute("SELECT UserId,Role,IsDeleted,IsDeactivated FROM users WHERE LoginId=?",(LOGIN,)).fetchone()
        assert row and row['Role']=='user' and (row['IsDeleted'] or 'N')=='N' and (row['IsDeactivated'] or 'N')=='N'
        owner=row['UserId']
    password=sys.stdin.readline().rstrip('\r\n')
    assert password
    with tempfile.TemporaryDirectory(prefix='eq-public-entry-') as profile:
        b=LiveBrowser(profile,1440,900)
        try:
            b.navigate('/login')
            b.wait_for("document.getElementById('loginForm') && typeof window.getCSRFToken==='function'",'production login ready')
            b.script("document.getElementById('LoginId').value=arguments[0];document.getElementById('Password').value=arguments[1];document.getElementById('loginForm').requestSubmit()",LOGIN,password)
            del password
            b.wait_for("location.origin==='https://nekohost.org' && location.pathname!=='/login' && document.readyState!=='loading'",'authenticated test account')
            b.cdp('Page.addScriptToEvaluateOnNewDocument',{'source':MONITOR})
            items=[]; produced=[]
            for name,w,h in [('desktop',1440,900),('mobile',384,860)]:
                result,cid,q=run_device(b,out,owner,name,w,h,out.parent.name[-6:])
                items.append(result);produced.append((cid,q))
            # Only this run's own terminal rows are eligible for reversible cleanup.
            for cid,q in produced:
                with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
                    row=db.execute('SELECT lifecycle_revision FROM conversations WHERE id=? AND owner=? AND title=? AND is_deleted=0',(cid,owner,q)).fetchone()
                    assert row
                reply=b.call('POST',b.sid+'/execute/async',{'script':"""const [cid,rev,key,done]=arguments;
                fetch('/api/ai/conversations/'+cid+'/trash',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':document.getElementById('equipment-ai').dataset.csrf},
                body:JSON.stringify({lifecycle_revision:rev,operation_id:key})}).then(async r=>done([r.status,(await r.json()).success])).catch(()=>done([0,false]));""",
                    'args':[cid,row['lifecycle_revision'],uuid.uuid4().hex]})
                assert reply==[200,True],('test cleanup',reply)
                with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
                    assert db.execute('SELECT is_deleted FROM conversations WHERE id=? AND owner=?',(cid,owner)).fetchone()[0]==1
            record(out/'verification.json',dict(status='pass',origin=BASE,test_user=LOGIN,devices=items,
                   verified_trash_count=len(produced),permanent_deletions=0,chromium=b.cdp('Browser.getVersion',{})['product']))
        finally:
            b.close()


if __name__=='__main__':
    main()
