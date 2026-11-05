"""[MINI-COMMENT: ASSISTANT.BROWSER.FIXTURE]
[EN rev.5]
[Role] Runs the actual candidate DOM/CSS against a deterministic, local-only browser transport.
[Dependencies] Linux Chromium, Flask/Jinja and synthetic responses; no production login/model is used.
[Impact] Tests thinking disclosure, safe rendering, readable business results/CSV and responsive layout without deploying source; model restoration is verified through the compact selector while immutable answer provenance stays independent.
"""
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading

from flask import Flask, jsonify, render_template, request, Response, send_from_directory
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.serving import make_server

SCRIPT=r'''
window.module={exports:{}};
let sent=false, pollCount=0, forceError=false;
const trace=[];
const cid='a'.repeat(32), jid='b'.repeat(32);
let modelId='e'.repeat(32), modelLevel='medium', modelRevision=1, selectionWrites=0;
const models=[{id:'e'.repeat(32),provider:'Strata PC A',label:'Fixture model',available:true,tools:true,levels:['off','low','medium','xhigh'],enabled_levels:['off','low','medium','xhigh'],supported_levels:['off','low','medium','xhigh'],default_level:'medium',reasoning_version:2,known_reasoning:true,level_reasons:{high:'모델 미지원',max:'모델 미지원'}},
  {id:'f'.repeat(32),provider:'PC B',label:'Chat <img src=x>',available:true,tools:false,levels:[]}];
const storage={base_chars:32000000,extension_chars:32000000,total_chars:64000000,used_chars:32000001,reserved_chars:426144,above_base:true};
const receipt={equipment_id:7,message:'장비를 등록했습니다.',internal_marker:'must-not-display',replayed:true};
const proposal={id:'c'.repeat(32),job:jid,operation:'equipment_create',payload:JSON.stringify({name:'시험 장비'}),before_json:'{}',state:'applied',result:JSON.stringify(receipt)};
const nativeFetch=window.fetch.bind(window);
window.fetch=async function(path,options={}) {
  const url=new URL(path,location.origin);
  trace.push({path:url.pathname,search:url.search,method:options.method||'GET'});
  if(!url.pathname.startsWith('/api/ai/')) return nativeFetch(path,options);
  let result={success:true};
  if(url.pathname.endsWith('/capabilities')) Object.assign(result,{storage,model:'Fixture model',reasoning_version:2,levels:[],writes:true,file_tools:true,scopes:['my','public','draft'],tools:['search_equipment','prepare_equipment_create','prepare_catalog_request']});
  else if(url.pathname==='/api/ai/models') Object.assign(result,{models,default_model:models[0].id});
  else if(url.pathname.endsWith('/selection')) {const data=JSON.parse(options.body);modelId=data.selection_id;modelLevel=data.level;modelRevision++;selectionWrites++;Object.assign(result,{revision:modelRevision,selection_id:modelId,level:modelLevel});}
  else if(url.pathname==='/api/ai/conversations') Object.assign(result,url.searchParams.has('cursor')?{conversations:[{id:'d'.repeat(32),title:'더 오래된 대화',updated:1}],next_cursor:null}:{conversations:[{id:cid,title:'화면 확인 대화',updated:2}],next_cursor:'fixture-next'});
  else if(url.pathname.endsWith('/turns')) {sent=true;result.job_id=jid;}
  else if(url.pathname==='/api/ai/csv/preview') Object.assign(result,{count:1,rows:[{Name:'확인 장비',OptionId:3,SerialNumber:'TEST',IsPublic:0}],errors:[],token:'fixture-preview'});
  else if(url.pathname.endsWith('/messages')) Object.assign(result,{storage,conversation:{id:cid,title:'화면 확인 대화',selection_id:url.pathname.includes('d'.repeat(32))?null:modelId,next_level:url.pathname.includes('d'.repeat(32))?'low':modelLevel,selection_revision:modelRevision},next_before:sent&&!url.searchParams.has('before')?101:null,
    messages:url.searchParams.has('before')?[{id:1,role:'user',content:'오래된 질문',reasoning:'',job:null},{id:2,role:'assistant',content:'오래된 답변',reasoning:'',job:null}]:sent?[{id:101,role:'user',content:'내 장비를 확인해 줘',reasoning:'',job:jid},{id:102,role:'assistant',content:'',reasoning:'',job:jid},
      {id:103,role:'assistant',content:'장비관리 서버 확인 완료 ['+'c'.repeat(32)+']: '+JSON.stringify(receipt),reasoning:'',job:null}]:[],
    jobs:sent?[{id:jid,state:forceError&&pollCount?'failed':'queued',steps:0,level:'medium',position:1,error:forceError&&pollCount?'응답 형식 오류로 작업을 중단했습니다.':null,source:{provider_name:'Strata PC A',model_label:'Fixture model',reasoning_effort:'medium',revision:1}}]:[],proposals:[]});
  else if(url.pathname.includes('/jobs/')) {
    pollCount++;
    const answer='**확인했습니다.**\n내 장비를 안전하게 조회했습니다.\n<img src=x onerror="window.__assistantPwned=true">';
    Object.assign(result,{storage,id:jid,message_id:102,source:{provider_name:'Strata PC A',model_label:'Fixture model',reasoning_effort:'medium',revision:1},generation:pollCount>=4?2:1,steps:pollCount>=4?1:0,state:pollCount>=6?'done':pollCount===3?'queued':'running',answer_started:pollCount>=2,
      reasoning:pollCount===1?'필요한 장비 정보를 검토하고 있습니다.':pollCount===2?'\n권한 범위를 확인했습니다.':pollCount===4?'\n\n두 번째 단계의 추론입니다.':'',
      content:pollCount===2||pollCount===5?answer:'',r:pollCount>=4?75:pollCount>=2?50:25,c:pollCount>=5||pollCount===2||pollCount===3?100:0,
      content_length:pollCount>=5||pollCount===2||pollCount===3?100:0,reasoning_length:pollCount>=4?75:pollCount>=2?50:25,proposals:pollCount>=6?[proposal]:[]});
    if(forceError) Object.assign(result,{state:'failed',error:'응답 형식 오류로 작업을 중단했습니다.',error_code:'INVALID_RESPONSE',reasoning:'',content:'',r:0,c:0,content_length:0,reasoning_length:0});
  }
  return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json','X-Assistant-Account':'fixture-account'}});
};
document.addEventListener('DOMContentLoaded',async()=>{
  const checks=[];
  const wait=async(test)=>{for(let i=0;i<1000;i++){if(test())return;await new Promise(r=>setTimeout(r,10));}throw Error('condition timed out');};
  const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
  const report=document.createElement('pre');report.id='browser-test-result';report.style.display='none';document.body.append(report);
  try{
    await wait(()=>document.querySelector('#ai-conversations button'));
    assert([...document.querySelectorAll('#ai-level option')].map(x=>x.value).join(',')==='off,low,medium,high,xhigh,max','six-standard-levels');
    assert(document.querySelector('#ai-level option[value=high]').disabled&&document.querySelector('#ai-level option[value=max]').disabled&&!document.querySelector('#ai-level option[value=low]').disabled,'known-unsupported-levels-visible-disabled');
    assert(getComputedStyle(document.querySelector('.ai-footnote')).fontSize==='12px','readable-footnote-size');
    assert(document.getElementById('ai-model').options.length===2&&document.getElementById('ai-model').textContent.includes('Strata PC A'),'provider-model-picker');
    assert(document.getElementById('ai-level').value==='medium','conversation-reasoning-restored');
    await wait(()=>!document.getElementById('ai-more-conversations').hidden);
    document.getElementById('ai-more-conversations').click();
    await wait(()=>document.getElementById('ai-conversations').textContent.includes('더 오래된 대화'));
    assert(document.getElementById('ai-conversations').querySelectorAll('.ai-conversation').length===2,'older-conversations-reachable');
    assert(document.getElementById('ai-storage-notice').textContent.includes('32,000,000')&&document.getElementById('ai-storage-notice').textContent.includes('64,000,000'),'base-and-extra-budget-visible');
    await wait(()=>!document.getElementById('ai-send').disabled&&!document.getElementById('ai-input').disabled);
    document.getElementById('ai-input').value='내 장비를 확인해 줘';
    document.getElementById('ai-form').requestSubmit();
    await wait(()=>document.querySelector('.ai-thought:not([hidden])'));
    const thought=document.querySelector('.ai-thought:not([hidden])');
    assert(thought.open,'reasoning-opens-live');
    await wait(()=>document.querySelector('.ai-message[data-role=assistant] .ai-answer').textContent.includes('확인했습니다'));
    assert(!thought.open,'answer-auto-collapses-once');
    thought.querySelector('summary').click();assert(thought.open,'user-can-reopen');
    await wait(()=>pollCount>=6);
    await new Promise(r=>setTimeout(r,50));
    assert(thought.open,'poll-keeps-user-expanded');
    assert(thought.querySelector('.ai-thought-text').textContent.includes('두 번째 단계'),'multistep-reasoning-preserved');
    assert(thought.querySelector('.ai-thought-text').textContent.includes('권한 범위'),'reasoning-separate-from-answer');
    assert(!document.querySelector('.ai-answer img')&&!window.__assistantPwned,'model-html-stays-text');
    assert(document.querySelector('.ai-answer strong').textContent==='확인했습니다.','safe-markdown');
    const root=document.getElementById('equipment-ai');
    assert(root.getBoundingClientRect().right<=innerWidth+1,'no-horizontal-overflow');
    if(innerWidth<760){document.getElementById('ai-menu-toggle').click();assert(document.getElementById('ai-sidebar').classList.contains('is-open'),'mobile-conversations');document.getElementById('ai-menu-toggle').click();}
    const merged=module.exports.mergeStream({generation:1,content:'Answer',reasoning:'Thought',r:7,c:6,answerStarted:true},{generation:1,content:' more',reasoning:'',r:7,c:11});
    assert(!merged.closeThought,'no-repeated-auto-collapse');
    const continued=module.exports.mergeStream(merged,{generation:2,content:'Final',reasoning:'\n\nNext thought',r:20,c:5,answer_started:true});
    assert(!continued.closeThought&&continued.reasoning.includes('Thought')&&continued.content==='Final','no-auto-collapse-on-next-generation');
    const safe=document.createElement('div');module.exports.markdown(safe,'[bad](javascript:alert(1))\n<script>evil()</script>\n[내 장비](/my_equipment)');
    assert(!safe.querySelector('script')&&!safe.querySelector('a[href^="javascript:"]')&&safe.querySelector('a[href="/my_equipment"]'),'safe-links');
    const confirmed=document.querySelector('.ai-proposal').textContent;
    assert(confirmed.includes('장비 번호: 7')&&!confirmed.includes('internal_marker')&&!confirmed.includes('must-not-display')&&!confirmed.includes('replayed'),'confirmed-result-user-language');
    const history=[...document.querySelectorAll('.ai-answer')].find(element=>element.textContent.includes('장비관리 서버 확인 완료')).textContent;
    assert(history.includes('장비 번호: 7')&&!history.includes('internal_marker')&&!history.includes('c'.repeat(32)),'receipt-history-user-language');
    document.getElementById('ai-more-messages').click();
    await wait(()=>document.getElementById('ai-messages').textContent.includes('오래된 답변'));
    assert(document.getElementById('ai-messages').firstElementChild.textContent.includes('오래된 질문'),'older-messages-prepended');
    assert(thought.open&&document.contains(thought),'history-loading-preserves-live-details');
    const selected=new DataTransfer();selected.items.add(new File(['synthetic fixture only'],'fixture.csv',{type:'text/csv'}));
    document.getElementById('ai-csv-file').files=selected.files;document.getElementById('ai-csv-form').requestSubmit();
    await wait(()=>!document.getElementById('ai-csv-preview').hidden);
    const csv=document.getElementById('ai-csv-preview').textContent;
    assert(csv.includes('장비 이름: 확인 장비')&&csv.includes('비공개')&&!csv.includes('OptionId')&&!csv.includes('{'),'csv-preview-user-language');
    forceError=true;pollCount=0;
    document.getElementById('ai-input').value='실패 처리 확인';document.getElementById('ai-form').requestSubmit();
    await wait(()=>document.getElementById('ai-progress-text').textContent.includes('응답 형식 오류'));
    assert(document.getElementById('ai-progress-text').textContent.includes('중단')&&document.querySelector('.ai-pulse').hidden&&!document.getElementById('ai-send').disabled,'live-failed-job-stopped-with-reason');
    document.querySelector('#ai-conversations button').click();
    await wait(()=>document.getElementById('ai-progress-text').textContent.includes('응답 형식 오류'));
    assert(document.getElementById('ai-progress-text').textContent.includes('중단'),'failed-reason-persists-on-reopen');
    await wait(()=>document.getElementById('equipment-ai').getAttribute('aria-busy')==='false');
    document.getElementById('ai-model').value=models[1].id;document.getElementById('ai-model').dispatchEvent(new Event('change'));
    await wait(()=>selectionWrites>0&&!document.getElementById('ai-model').disabled);
    assert(document.getElementById('ai-model-status').textContent.includes('대화 전용')&&document.getElementById('ai-level').disabled,'chat-only-supported-controls');
    assert(!document.querySelector('.ai-model-control img'),'model-label-xss-safe');
    document.querySelector('#ai-conversations button').click();
    await wait(()=>document.getElementById('ai-model').selectedOptions[0]?.textContent.includes('PC B')&&document.getElementById('equipment-ai').getAttribute('aria-busy')==='false');
    assert(document.getElementById('ai-model').value===models[1].id&&document.getElementById('ai-level').value==='default','model-choice-restored-on-reopen');
    assert(document.querySelector('.ai-source').textContent.includes('Strata PC A')&&document.getElementById('ai-model').selectedOptions[0]?.textContent.includes('PC B')&&!document.getElementById('ai-model-caption'),'accepted-answer-provenance-survives-model-change');
    assert(document.getElementById('ai-level-help').textContent.includes('모델 기본 동작')&&[...document.querySelectorAll('#ai-level option')].filter(option=>option.value!=='default').every(option=>option.disabled),'unsupported-reasoning-help-correct');
    [...document.querySelectorAll('#ai-conversations button')].find(button=>button.textContent.includes('더 오래된')).click();
    await wait(()=>document.getElementById('equipment-ai').getAttribute('aria-busy')==='false');
    assert(document.getElementById('ai-model').value===models[0].id&&document.getElementById('ai-model-status').textContent.includes('이전 모델 기록이 없습니다'),'legacy-chat-does-not-inherit-other-session-model');
    report.textContent=JSON.stringify({status:'pass',checks,width:innerWidth});
  }catch(error){report.textContent=JSON.stringify({status:'fail',checks,error:error.message,width:innerWidth,diagnostic:{more_hidden:document.getElementById('ai-more-conversations')?.hidden,more_disabled:document.getElementById('ai-more-conversations')?.disabled,nav:document.getElementById('ai-conversations')?.textContent?.slice(0,400),notice:document.getElementById('ai-notice')?.textContent,trace:trace.slice(-8)}});}
  if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
  window.dispatchEvent(new Event('pagehide'));
});
'''

ADMIN_SCRIPT=r'''
let adminRequests=[],fixtureProvider={id:'1'.repeat(32),name:'PC A <img src=x>',revision:1,enabled:1,retired:0,manual:0,sort_order:0,
  base_url:'http://192.168.0.14:8080',adapter:'strata',resource_group:'2'.repeat(32),has_key:1,last_checked:123,models:[
    {id:'3'.repeat(32),label:'Test model',upstream:'qwen3.8-flash-next-iq3_xxs',published:1,present:1,manual:0,sort_order:0,context_tokens:65536,profile:JSON.stringify({chat:true,tools:true,levels:['off','low','medium','xhigh'],enabled_levels:['off','low','medium','xhigh'],supported_levels:['off','low','medium','xhigh'],default_level:'medium',reasoning_version:2,known_reasoning:true,level_reasons:{high:'모델 미지원',max:'모델 미지원'}}),verified_revision:1,profile_revision:1,enabled_levels:['off','low','medium','xhigh'],supported_levels:['off','low','medium','xhigh'],default_level:'medium',known_reasoning:true}]};
const nativeFetch=window.fetch.bind(window);
window.fetch=async(path,options={})=>{
  const url=new URL(path,location.origin);
  if(!url.pathname.startsWith('/api/admin/ai/')&&!url.pathname.startsWith('/api/ai/jobs/'))return nativeFetch(path,options);
  const data=options.body?JSON.parse(options.body):null;adminRequests.push({path:url.pathname,data,headers:options.headers});
  let result={success:true};
  if(url.pathname==='/api/admin/ai/providers'&&options.method!=='POST')Object.assign(result,{providers:[fixtureProvider],groups:[{id:'2'.repeat(32),name:'PC A shared GPU'}],default_model:'3'.repeat(32),encryption_configured:true});
  else if(url.pathname.endsWith('/probe'))Object.assign(result,{job_id:'4'.repeat(32)});
  else if(url.pathname.startsWith('/api/ai/jobs/'))Object.assign(result,{state:'done',steps:2});
  else if(url.pathname.endsWith('/models')){fixtureProvider.models[0].label=data.label;result.id='3'.repeat(32);}
  else if(url.pathname.endsWith('/discover')){}
  else {fixtureProvider={...fixtureProvider,...data,revision:fixtureProvider.revision+1,has_key:1};delete fixtureProvider.api_key;result.id=fixtureProvider.id;}
  return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});
};
document.addEventListener('DOMContentLoaded',async()=>{
  const checks=[],report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
  const wait=async(test)=>{for(let i=0;i<1000;i++){if(test())return;await new Promise(r=>setTimeout(r,10));}throw Error('condition timed out');};
  const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
  try{
    await wait(()=>document.querySelector('#provider-list button'));
    document.querySelector('#provider-list button').click();
    const form=document.getElementById('provider-form');
    assert(document.querySelectorAll('.provider-reasoning-options input').length===6,'admin-six-efforts');
    assert(document.querySelector('[data-reasoning-level=high]').disabled&&document.querySelector('[data-reasoning-level=max]').disabled,'admin-known-ceiling-disabled');
    assert(form.elements.api_key.value===''&&form.elements.api_key.placeholder.includes('키 저장됨'),'key-write-only');
    assert(!document.getElementById('provider-list').querySelector('img'),'provider-label-xss-safe');
    assert(document.getElementById('provider-manual').hidden&&!form.elements.manual.checked,'automatic-inventory-default');
    assert(form.elements.resource_group.selectedOptions[0].textContent.includes('shared GPU'),'shared-group-control');
    form.elements.manual.checked=true;form.elements.api_key.value='synthetic-ui-key-123456789';form.requestSubmit();
    await wait(()=>document.getElementById('provider-notice').textContent.includes('연결을 저장'));
    assert(form.elements.api_key.value===''&&!document.getElementById('provider-manual').hidden,'key-cleared-and-optional-manual-enabled');
    const save=adminRequests.find(item=>item.data&&item.data.api_key);
    assert(save.headers['X-CSRFToken']==='fixture-csrf'&&save.data.revision===1&&save.data.manual===true,'admin-mutation-csrf-revision');
    document.querySelector('.provider-model-card input[type=text]').value='Renamed model';document.querySelector('.provider-model-card').requestSubmit();
    await wait(()=>document.getElementById('provider-notice').textContent.includes('모델 설정을 저장'));
    assert(document.querySelector('.provider-model-card h3').textContent==='Renamed model','model-alias-edit');
    const policySave=adminRequests.find(item=>item.path.endsWith('/models')&&item.data.id);
    assert(policySave.data.reasoning_levels.join(',')==='off,low,medium,xhigh'&&policySave.data.reasoning_default==='medium'&&policySave.data.profile_revision===1,'admin-effort-default-and-revision-saved');
    document.querySelector('.provider-model-card button[type=button]').click();
    await wait(()=>document.getElementById('provider-notice').textContent.includes('기능 시험을 완료'));
    assert(adminRequests.some(item=>item.path.endsWith('/probe'))&&adminRequests.some(item=>item.path.startsWith('/api/ai/jobs/')),'capability-test-queue-and-poll');
    assert(!document.querySelector('input[name=headers]')&&!document.querySelector('textarea[name=body]'),'advanced-customization-deferred');
    window.confirm=()=>true;document.getElementById('provider-retire').click();
    await wait(()=>document.getElementById('provider-notice').textContent.includes('연결을 폐기'));
    assert(document.getElementById('provider-save').disabled&&document.getElementById('provider-retire').hidden,'soft-retire-visible');
    assert(document.getElementById('ai-providers-admin').getBoundingClientRect().right<=innerWidth+1&&document.documentElement.scrollWidth<=innerWidth+1,'admin-responsive-no-overflow');
    report.textContent=JSON.stringify({status:'pass',view:'admin',checks,width:innerWidth});
  }catch(error){report.textContent=JSON.stringify({status:'fail',view:'admin',checks,error:error.message,width:innerWidth});}
  if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
  window.dispatchEvent(new Event('pagehide'));
});
'''


def run_browser(project,assets):
    """[Role] Serves only test assets on loopback and returns bounded results/screenshots from Chromium."""
    app=Flask('assistant_browser',static_folder=None)
    app.secret_key='synthetic-browser-fixture-not-a-production-key'
    app.jinja_loader=ChoiceLoader([DictLoader({k.removeprefix('templates/'):v for k,v in assets.items() if k.startswith('templates/')}),FileSystemLoader(Path(project)/'templates')])

    @app.get('/static/<path:filename>',endpoint='static')
    def static(filename):
        """[Role] Reads candidate assets first and safe existing project static files second."""
        key='static/'+filename
        if key in assets:
            mime='text/css' if filename.endswith('.css') else 'application/javascript'
            return Response(assets[key],content_type=mime)
        return send_from_directory(Path(project)/'static',filename)

    @app.get('/')
    @app.get('/admin-fixture')
    def page():
        """[Role] Renders the actual Jinja UI and injects deterministic browser checks only in this fixture."""
        admin=request.path=='/admin-fixture'
        html=render_template('equipment_ai_providers.html' if admin else 'equipment_ai.html',user={'NickName':'개발 확인','Role':'admin' if admin else 'user'},assistant_csrf='fixture-csrf',csrf_token='fixture-csrf')
        html=html.replace('src="https://cdn.tailwindcss.com"','src="/static/js/tailwindcss.js"')
        if admin and globals().get('FRAME_DIAGNOSTIC_SCRIPT'):
            html=html.replace('<head>','<head><script>'+FRAME_DIAGNOSTIC_SCRIPT.replace('</script','<\\/script')+'</script>',1)
        anchor='<script src="/static/js/'+('equipment_ai_providers.js' if admin else 'equipment_ai.js')+'"'
        if anchor not in html:
            raise ValueError('fixture script anchor missing')
        html=html.replace(anchor,'<script>'+(ADMIN_SCRIPT if admin else SCRIPT).replace('</script','<\\/script')+'</script>'+anchor)
        # The bundled production fallback supplies the actual common preflight/theme while external CDNs stay blocked.
        response=Response(html,content_type='text/html; charset=utf-8')
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'none'; img-src 'self' data:"
        return response

    @app.get('/api/check_session')
    def check_session():
        """[Role] Supplies the common frame's independent test-only session poll."""
        return jsonify(valid=True)

    @app.get('/api/user_settings')
    def fixture_preferences():
        """[Role] Supplies the same explicit light preference as the legacy fixture viewport.
        [Dependencies] Synthetic settings only. [Impact] Session preference restoration cannot reset theme nondeterministically.
        """
        return jsonify(success=True,settings={'theme':'light','layout_skin':'standard'})

    @app.get('/mobile')
    def mobile():
        """[Role] Uses a real 430px child viewport, avoiding Chromium's 500px top-window minimum."""
        html='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#e9edf2;display:flex;justify-content:center"><iframe id="fixture-phone" src="/" style="width:430px;height:900px;border:0;background:white"></iframe><pre id="browser-test-result" hidden></pre><script>addEventListener('message',event=>{if(event.origin===location.origin&&event.source===document.getElementById('fixture-phone').contentWindow&&event.data.fixtureResult)document.getElementById('browser-test-result').textContent=event.data.fixtureResult;});</script></body></html>'''
        return Response(html.replace('src="/"','src="/admin-fixture"') if request.args.get('view')=='admin' else html,content_type='text/html; charset=utf-8')

    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    results=[]
    try:
        for view,width,height in (('assistant',1440,1000),('assistant',430,920),('admin',1440,1000),('admin',430,920)):
            with tempfile.TemporaryDirectory(prefix='eq-assistant-browser-') as tmp:
                png=Path(tmp)/'screen.png'
                command=['/usr/bin/chromium','--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-proxy-server',
                    '--force-dark-mode',
                    '--disable-background-networking','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1',
                    '--user-data-dir='+str(Path(tmp)/'profile'),'--window-size='+str(max(width,500))+','+str(height),
                    '--virtual-time-budget=45000','--screenshot='+str(png),'--dump-dom','http://127.0.0.1:'+str(server.server_port)+(('/mobile?view='+view) if width<760 else '/admin-fixture' if view=='admin' else '/')]
                process=subprocess.run(command,capture_output=True,text=True,timeout=45)
                match=re.search(r'<pre id="browser-test-result"[^>]*>(.*?)</pre>',process.stdout,re.S)
                import html
                result=json.loads(html.unescape(match[1])) if match and match[1] else {'status':'fail','error':'browser fixture did not complete','width':width}
                result['exit_code']=process.returncode
                result['view']=view
                if png.exists():result['screenshot']=base64.b64encode(png.read_bytes()).decode()
                results.append(result)
    finally:
        server.shutdown();thread.join(timeout=5);server.server_close()
    return results

