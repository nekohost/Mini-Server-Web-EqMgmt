"""[MINI-COMMENT: ASSISTANT.PROVIDERS.BROWSER.FIXTURE]
[EN rev.6]
[Role] Exercises the real admin dialog/loading code with deterministic transport faults and queue states.
[Dependencies] Isolated Linux Chromium, bundled Tailwind, actual Jinja/CSS/JS and synthetic API/preferences responses.
[Impact] No production database/provider/service is touched; failures include bounded secret-free initialization evidence.
"""
import base64
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.serving import make_server


FRAME_DIAGNOSTIC_SCRIPT = r'''
window.__adminFrameErrors=[];
addEventListener('error',event=>window.__adminFrameErrors.push({message:String(event.message||'resource load failed').slice(0,240),line:event.lineno||0,column:event.colno||0}));
'''


SCRIPT = r'''
const adminRequests=[], pid='1'.repeat(32), gid='2'.repeat(32), mid='3'.repeat(32), jid='4'.repeat(32);
const adminBrowserErrors=[];
window.addEventListener('error',event=>adminBrowserErrors.push({type:'error',message:String(event.message||'resource load failed').slice(0,240)}));
window.addEventListener('unhandledrejection',event=>adminBrowserErrors.push({type:'unhandledrejection',message:String(event.reason&&event.reason.message||'promise rejected').slice(0,240)}));
let providers=[{id:pid,name:'PC A <img src=x>',revision:1,enabled:1,retired:0,manual:0,sort_order:0,
  base_url:'http://192.168.0.14:8080',adapter:'strata',resource_group:gid,has_key:1,last_checked:123,models:[
  {id:mid,label:'Test model',upstream:'qwen3.8-flash-next-iq3_xxs',published:1,present:1,manual:0,sort_order:0,context_tokens:65536,
   profile:JSON.stringify({chat:true,tools:true,levels:['off','low','medium','xhigh'],enabled_levels:['off','low','medium','xhigh'],default_level:'medium'}),verified_revision:1,profile_revision:1,
   enabled_levels:['off','low','medium','xhigh'],supported_levels:['off','low','medium','xhigh'],default_level:'medium',known_reasoning:true}]}];
let mode='', failNextRead=false, releasePost=null, probePhase='queued', acceptedKey=null;
const nativeFetch=window.fetch.bind(window);
const response=(result,status=200)=>new Response(JSON.stringify(result),{status,headers:{'Content-Type':'application/json'}});
window.fetch=async(path,options={})=>{
  const url=new URL(path,location.origin), write=options.method==='POST';
  if(!url.pathname.startsWith('/api/admin/ai/')&&!url.pathname.startsWith('/api/ai/jobs/'))return nativeFetch(path,options);
  const data=options.body?JSON.parse(options.body):null;adminRequests.push({path:url.pathname,write,data,headers:options.headers});
  if(url.pathname==='/api/admin/ai/probes')return response({success:true,found:Boolean(acceptedKey),job_id:jid,conversation_id:'5'.repeat(32)});
  if(url.pathname.startsWith('/api/ai/jobs/')){
    if(probePhase==='network')throw TypeError('synthetic status network interruption');
    return response({success:true,state:probePhase,steps:probePhase==='done'?2:0});
  }
  if(url.pathname==='/api/admin/ai/providers'&&!write){
    if(failNextRead||mode==='readFail'){failNextRead=false;mode='';throw TypeError('synthetic read interruption');}
    return response({success:true,providers,groups:[{id:gid,name:'Shared GPU'}],default_model:mid,encryption_configured:true});
  }
  if(mode==='conflict'){mode='';return response({success:false,message:'설정 revision 충돌'},409);}
  if(mode==='hold'){mode='';await new Promise(resolve=>{releasePost=resolve;});}
  let result={success:true}, provider=providers.find(item=>url.pathname.includes(item.id))||providers[0];
  if(url.pathname.endsWith('/probe')){acceptedKey=data.client_key;result.job_id=jid;}
  else if(url.pathname.endsWith('/discover'))provider.last_checked=456;
  else if(url.pathname.endsWith('/models')){
    if(data.id){Object.assign(provider.models.find(item=>item.id===data.id),{label:data.label,profile_revision:2});result.id=data.id;}
    else {const model={...provider.models[0],id:'6'.repeat(32),upstream:data.upstream,label:data.label};provider.models.push(model);result.id=model.id;}
  }else if(url.pathname==='/api/admin/ai/providers'){
    const created={...providers[0],...data,id:'7'.repeat(32),revision:1,models:[],has_key:1};delete created.api_key;providers.push(created);result.id=created.id;
  }else {Object.assign(provider,data,{revision:provider.revision+1,has_key:1});delete provider.api_key;result.id=provider.id;}
  if(mode==='ackRefreshFail'){mode='';failNextRead=true;}
  if(mode==='lostAck'){mode='';throw TypeError('synthetic lost POST response');}
  return response(result);
};
document.addEventListener('DOMContentLoaded',async()=>{
  const checks=[],report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
  let stage='provider-initialization';
  const $=id=>document.getElementById(id), wait=async(test)=>{for(let i=0;i<1600;i++){if(test())return;await new Promise(resolve=>setTimeout(resolve,10));}throw Error('condition timed out: '+stage);};
  const assert=(condition,name)=>{if(!condition)throw Error(name);checks.push(name);};
  const shown=async(title)=>{stage='dialog: '+title;await wait(()=>$('provider-dialog').open&&$('provider-dialog-title').textContent.includes(title));};
  const close=async(accept=true)=>{$(accept?'provider-dialog-accept':'provider-dialog-cancel').click();await wait(()=>!$('provider-dialog').open);await Promise.resolve();};
  const writeCount=()=>adminRequests.filter(item=>item.write).length;
  const modelForm=()=>document.querySelector('.provider-model-card');
  const setName=text=>{const input=$('provider-form').elements.name;input.value=text;input.dispatchEvent(new Event('input',{bubbles:true}));};
  const requestedDark=new URL(location.href).searchParams.get('dark')==='1';
  const settledBodyTransitions=[];
  // Fixture-only virtual transition settling: finish the body's finite color
  // transitions without changing its CSS, classes, media or final target values.
  const settleBodyTransitions=()=>{
    if(typeof document.body.getAnimations!=='function')return;
    getComputedStyle(document.body).backgroundColor;
    for(const animation of document.body.getAnimations({subtree:false})){
      const effect=animation.effect,timing=effect?.getComputedTiming();
      if(effect?.target!==document.body||!['background-color','color'].includes(animation.transitionProperty)||!Number.isFinite(timing?.endTime))continue;
      const entry={property:animation.transitionProperty,current_time:animation.currentTime,end_time:timing.endTime,before_background:getComputedStyle(document.body).backgroundColor};
      try{animation.finish();entry.finished=true;}catch(error){entry.error=error.name;}
      entry.after_background=getComputedStyle(document.body).backgroundColor;
      if(settledBodyTransitions.length<8)settledBodyTransitions.push(entry);
    }
  };
  const rgb=value=>{const parts=(value.match(/[\d.]+/g)||[]).map(Number);return [parts[0]||0,parts[1]||0,parts[2]||0,parts.length>3?parts[3]:1];};
  const luminance=channels=>channels.slice(0,3).map(value=>value/255).map(value=>value<=0.04045?value/12.92:((value+0.055)/1.055)**2.4).reduce((sum,value,index)=>sum+value*[0.2126,0.7152,0.0722][index],0);
  const background=element=>{const layers=[];for(let node=element;node;node=node.parentElement)layers.push(rgb(getComputedStyle(node).backgroundColor));return layers.reverse().reduce((color,layer)=>layer.slice(0,3).map((value,index)=>value*layer[3]+color[index]*(1-layer[3])),[255,255,255]);};
  const contrast=element=>{const bg=background(element),fg=rgb(getComputedStyle(element).color),front=fg.slice(0,3).map((value,index)=>value*fg[3]+bg[index]*(1-fg[3]));const values=[luminance(front),luminance(bg)].sort((a,b)=>a-b);return (values[1]+0.05)/(values[0]+0.05);};
  const tailwindEvidence=()=>{
    const matchingRules=[],mediaConditions=[],unreadableSheets=[];
    const walk=(rules,sheet,conditions=[])=>{
      for(const rule of rules){
        const next=rule.conditionText?[...conditions,{text:rule.conditionText,active:rule.media?matchMedia(rule.conditionText).matches:null}]:conditions;
        if(rule.conditionText&&rule.conditionText.includes('prefers-color-scheme')&&mediaConditions.length<12)mediaConditions.push({sheet,...next[next.length-1]});
        if(rule.selectorText&&/(?:bg-slate-(?:100|900)|text-slate-(?:100|800))/.test(rule.selectorText)&&matchingRules.length<24){
          let matchesBody=false;try{matchesBody=document.body.matches(rule.selectorText);}catch(_){}
          matchingRules.push({sheet,selector:rule.selectorText,conditions:next,matches_body:matchesBody,background:rule.style.backgroundColor,color:rule.style.color});
        }
        if(rule.cssRules)walk(rule.cssRules,sheet,next);
      }
    };
    [...document.styleSheets].forEach((sheet,index)=>{const name=sheet.href?new URL(sheet.href,location.href).pathname:'inline-'+index;try{walk(sheet.cssRules,name);}catch(error){unreadableSheets.push({sheet:name,error:error.name});}});
    return {dark_mode:window.tailwind?.config?.darkMode??null,config_keys:Object.keys(window.tailwind?.config||{}),
      config_script_count:[...document.scripts].filter(script=>/^\s*tailwind\.config\s*=/m.test(script.textContent)).length,
      matching_rules:matchingRules,media_conditions:mediaConditions,unreadable_sheets:unreadableSheets};
  };
  const diagnostic=()=>({stage,ready_state:document.readyState,pathname:location.pathname,
    provider_list_text:$('provider-list')?.textContent?.slice(0,500),root_aria_busy:$('ai-providers-admin')?.getAttribute('aria-busy'),
    notice:$('provider-notice')?.textContent?.slice(0,700),dialog_open:$('provider-dialog')?.open,dialog_title:$('provider-dialog-title')?.textContent,
    body_background:getComputedStyle(document.body).backgroundColor,body_text:getComputedStyle(document.body).color,
    body_transition:getComputedStyle(document.body).transition,
    body_animations:document.body.getAnimations().slice(0,6).map(animation=>({type:animation.constructor.name,state:animation.playState,pending:animation.pending,current_time:animation.currentTime,progress:animation.effect?.getComputedTiming().progress})),
    settled_body_transitions:settledBodyTransitions,
    requested_dark:requestedDark,dark:document.documentElement.classList.contains('dark'),cached_theme:localStorage.theme,system_dark:matchMedia('(prefers-color-scheme: dark)').matches,
    admin_requests:adminRequests.slice(-5).map(item=>({path:item.path,method:item.write?'POST':'GET',fields:Object.keys(item.data||{}).filter(key=>key!=='api_key'),revision:item.data?.revision,key_present:Boolean(item.data&&Object.hasOwn(item.data,'api_key'))})),
    scripts:[...document.scripts].filter(item=>/tailwindcss|equipment_ai_providers/.test(item.src)).map(item=>new URL(item.src,location.href).pathname),
    tailwind:tailwindEvidence(),early_errors:(window.__adminFrameErrors||[]).slice(-5),errors:adminBrowserErrors.slice(-5)});
  let measuredTheme;
  try{
    sessionStorage.removeItem('eqmgmt.ai.admin.probe.v1');
    await wait(()=>document.querySelector('#provider-list button')&&$('ai-providers-admin').getAttribute('aria-busy')==='false');
    stage='frame-theme';
    const expectedBackground=requestedDark?[15,23,42]:[241,245,249];
    await wait(()=>{settleBodyTransitions();return document.documentElement.classList.contains('dark')===requestedDark&&rgb(getComputedStyle(document.body).backgroundColor).slice(0,3).every((value,index)=>Math.abs(value-expectedBackground[index])<=1);});
    measuredTheme={requested_dark:requestedDark,applied_dark:document.documentElement.classList.contains('dark'),body_background:getComputedStyle(document.body).backgroundColor,body_text:getComputedStyle(document.body).color,
      system_dark:matchMedia('(prefers-color-scheme: dark)').matches,tailwind:tailwindEvidence(),settled_body_transitions:settledBodyTransitions};
    assert(measuredTheme.tailwind.dark_mode==='class','common-frame-tailwind-class-dark-mode');
    assert(Boolean(window.tailwind)&&measuredTheme.applied_dark===requestedDark,'bundled-frame-theme-applied');
    assert(contrast(document.body)>=4.5,'frame-text-contrast-at-least-4.5');
    document.querySelector('#provider-list button').click();
    const form=$('provider-form');
    assert(document.querySelectorAll('.provider-reasoning-options input').length===6,'six-reasoning-controls');
    assert(document.querySelector('[data-reasoning-level=high]').disabled&&document.querySelector('[data-reasoning-level=max]').disabled,'known-unsupported-values-stay-disabled');
    assert(!document.querySelector('#provider-list img')&&form.elements.api_key.value==='','safe-text-and-write-only-key');
    form.elements.manual.checked=true;form.elements.api_key.value='synthetic-secret-ui-value';mode='hold';
    $('provider-save').focus();form.requestSubmit();await wait(()=>releasePost);
    const heldCount=writeCount();form.requestSubmit();$('provider-new').click();
    assert(writeCount()===heldCount&&form.elements.name.disabled&&$('provider-controls').inert&&$('ai-providers-admin').getAttribute('aria-busy')==='true','duplicate-and-selection-locked');
    assert(!$('global-loading-overlay').classList.contains('hidden'),'existing-global-loading-reused');
    scrollTo(0,document.body.scrollHeight);releasePost();await shown('연결 저장 완료');
    const box=$('provider-dialog').getBoundingClientRect();
    assert(box.top>=0&&box.bottom<=innerHeight+1,'native-dialog-visible-from-mobile-bottom');
    measuredTheme.dialog_contrast=contrast($('provider-dialog-message'));
    assert(measuredTheme.dialog_contrast>=4.5&&contrast($('provider-dialog-title'))>=4.5,'result-dialog-text-contrast-at-least-4.5');
    assert(!$('provider-dialog').textContent.includes('synthetic-secret-ui-value')&&form.elements.api_key.value==='','credential-not-in-result-and-cleared-on-ack');
    await close();assert(document.activeElement.id==='provider-save','focus-restored-after-render');
    assert(!document.querySelector('[data-reasoning-level=high]').checked&&document.querySelector('[data-reasoning-level=high]').disabled,'unsupported-values-preserved-after-lock');
    modelForm().querySelector('input[type=text]').value='Renamed model';modelForm().requestSubmit();await shown('모델 설정 저장 완료');await close();
    assert(modelForm().querySelector('h3').textContent==='Renamed model','model-save-through-common-result');
    const policy=adminRequests.find(item=>item.path.endsWith('/models')&&item.data.id);
    assert(policy.data.reasoning_levels.join(',')==='off,low,medium,xhigh'&&policy.data.profile_revision===1,'saved-reasoning-contract-and-revision');
    const manual=$('provider-manual');manual.elements.upstream.value='manual-fixture-model';manual.elements.label.value='Manual fixture';manual.requestSubmit();await shown('수동 모델 등록 완료');await close();
    assert(document.querySelectorAll('.provider-model-card').length===2,'manual-model-registration-complete');
    $('provider-discover').click();await shown('모델 목록 조회 완료');await close();
    mode='readFail';const listBefore=$('provider-list').textContent;$('provider-reload').click();await shown('목록 조회 실패');
    assert($('provider-list').textContent===listBefore,'read-failure-preserves-existing-list');await close();
    setName('Conflict preserved');mode='conflict';form.requestSubmit();await shown('충돌');assert(form.elements.name.value==='Conflict preserved','409-preserves-user-input');await close();
    $('provider-reload').click();await shown('현재 설정 새로고침');
    $('provider-dialog').dispatchEvent(new Event('close'));await Promise.resolve();
    assert($('provider-dialog').open&&form.elements.name.value==='Conflict preserved','stale-close-event-keeps-current-confirmation-open');
    await close();await shown('목록 조회 완료');await close();
    setName('ACK saved');mode='ackRefreshFail';const beforeAck=writeCount();form.requestSubmit();await shown('목록 갱신 실패');
    assert(writeCount()===beforeAck+1&&$('provider-save').disabled,'ack-refresh-failure-not-retried');await close();
    $('provider-reconcile').click();await shown('완료 결과 확인');await close();
    assert(form.elements.name.value==='ACK saved'&&!$('provider-save').disabled,'ack-result-read-only-recovery');
    setName('Lost response preserved');form.elements.api_key.value='synthetic-unknown-key';mode='lostAck';const beforeLost=writeCount();form.requestSubmit();await shown('결과 확인 필요');
    assert(writeCount()===beforeLost+1&&form.elements.name.value==='Lost response preserved'&&form.elements.api_key.value==='synthetic-unknown-key','lost-response-preserves-input-without-repost');await close();
    $('provider-reconcile').click();await shown('현재 설정 확인');await close();
    assert(writeCount()===beforeLost+1&&form.elements.api_key.value==='','unknown-result-get-only-adoption');
    probePhase='queued';mode='lostAck';modelForm().querySelector('[data-probe]').click();await shown('기능 시험 접수 확인');await close();
    await wait(()=>$('provider-probe-status').textContent.includes('큐 대기'));
    assert($('global-loading-overlay').classList.contains('hidden')&&!form.elements.name.disabled&&modelForm().querySelector('[data-probe]').disabled,'probe-ack-ends-overlay-while-queue-stays-visible');
    probePhase='running';await wait(()=>$('provider-probe-status').textContent.includes('진행 중'));
    assert(!$('provider-dialog').open,'running-is-not-final-success');
    probePhase='network';await shown('시험 상태 조회 실패');await close();
    assert(!$('provider-probe-resume').hidden&&modelForm().querySelector('[data-probe]').disabled,'status-network-error-keeps-job-and-resume');
    const probeCount=adminRequests.filter(item=>item.path.endsWith('/probe')).length;
    probePhase='done';$('provider-probe-resume').click();await shown('기능 시험 성공');await close();
    assert(adminRequests.filter(item=>item.path.endsWith('/probe')).length===probeCount,'status-resume-does-not-submit-new-test');
    for(const terminal of ['failed','cancelled','recovery_required']){
      probePhase=terminal;modelForm().querySelector('[data-probe]').click();await shown('기능 시험 접수');await close();
      await shown(terminal==='failed'?'기능 시험 실패':terminal==='cancelled'?'기능 시험 취소됨':'기능 시험 종료 확인 필요');await close();
    }
    const preRetire=writeCount();$('provider-retire').click();await shown('연결 폐기');
    assert($('provider-dialog-message').textContent.includes('Lost response preserved')&&$('provider-dialog-message').textContent.includes('활성화할 수 없습니다'),'named-retirement-confirmation');await close(false);
    assert(writeCount()===preRetire,'retirement-cancel-does-not-write');
    $('provider-retire').click();await shown('연결 폐기');await close();await shown('연결 폐기 완료');await close();
    assert($('provider-save').disabled&&$('provider-retire').hidden,'retired-provider-cannot-reactivate');
    assert(!adminRequests.some(item=>/cancel|unload|reset/.test(item.path)),'no-shared-model-cancel-or-reset');
    assert(adminRequests.filter(item=>item.write).every(item=>item.headers['X-CSRFToken']==='fixture-csrf'),'every-post-carries-csrf');
    assert(document.documentElement.scrollWidth<=innerWidth+1,'responsive-no-document-overflow');
    scrollTo(0,0);$('provider-reload').click();await shown('목록 조회 완료');
    report.textContent=JSON.stringify({status:'pass',view:'admin',checks,width:innerWidth,dark:document.documentElement.classList.contains('dark'),theme:measuredTheme});
  }catch(error){report.textContent=JSON.stringify({status:'fail',view:'admin',checks,error:error.message,width:innerWidth,theme:measuredTheme,diagnostic:diagnostic()});}
  if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
  window.dispatchEvent(new Event('pagehide'));
});
'''


def run_browser(project, assets):
    """[Role] Runs extra 390px/tablet/dark admin scenarios using a loopback-only synthetic transport."""
    app = Flask('admin_providers_browser', static_folder=None)
    app.secret_key = 'synthetic-admin-browser-fixture-only'
    app.jinja_loader = ChoiceLoader([DictLoader({key.removeprefix('templates/'): value for key, value in assets.items() if key.startswith('templates/')}), FileSystemLoader(Path(project) / 'templates')])

    @app.get('/static/<path:filename>', endpoint='static')
    def static_file(filename):
        """[Role] Serves reviewed candidate assets before safe existing frame assets."""
        key = 'static/' + filename
        if key in assets:
            return Response(assets[key], content_type='text/css' if filename.endswith('.css') else 'application/javascript')
        return send_from_directory(Path(project) / 'static', filename)

    @app.get('/')
    def page():
        """[Role] Renders the actual admin page and injects only this fixture's deterministic transport."""
        document = render_template('equipment_ai_providers.html', user={'NickName': 'Fixture', 'Role': 'admin'}, assistant_csrf='fixture-csrf', csrf_token='fixture-csrf')
        document = document.replace('src="https://cdn.tailwindcss.com"', 'src="/static/js/tailwindcss.js"')
        document = document.replace('<head>', '<head><script>' + FRAME_DIAGNOSTIC_SCRIPT + '</script>', 1)
        anchor = '<script src="/static/js/equipment_ai_providers.js"'
        document = document.replace(anchor, '<script>' + SCRIPT.replace('</script', '<\\/script') + '</script>' + anchor)
        selected_theme = 'dark' if request.args.get('dark') == '1' else 'light'
        document = document.replace('<head>', '<head><script>localStorage.theme="' + selected_theme + '";</script>', 1)
        document = document.replace('</head>', '<style>html,body{margin:0;font:14px Arial,system-ui,sans-serif}*,*:before,*:after{box-sizing:border-box}.hidden{display:none!important}</style></head>')
        response = Response(document, content_type='text/html; charset=utf-8')
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'none'; img-src 'self' data:"
        return response

    @app.get('/viewport')
    def viewport():
        """[Role] Creates a real narrow viewport below Chromium's top-window minimum width."""
        width = int(request.args.get('width', '390'))
        if width not in (390, 430, 768, 1440):
            return '', 400
        source = '/?dark=' + ('1' if request.args.get('dark') == '1' else '0')
        document = '<html><body style="margin:0"><iframe id="fixture-phone" src="' + source + '" style="width:' + str(width) + 'px;height:950px;border:0"></iframe><pre id="browser-test-result" hidden></pre><script>addEventListener("message",e=>{if(e.origin===location.origin&&e.source===document.getElementById("fixture-phone").contentWindow&&e.data.fixtureResult)document.getElementById("browser-test-result").textContent=e.data.fixtureResult;});</script></body></html>'
        return Response(document, content_type='text/html; charset=utf-8')

    @app.get('/api/check_session')
    def session_status():
        """[Role] Supplies a neutral frame session response without account access."""
        return jsonify(valid=True)

    @app.get('/api/user_settings')
    def preferences():
        """[Role] Preserves the requested test theme through the real frame's server-preference synchronization."""
        selected_theme = 'dark' if re.search(r'(?:[?&])dark=1(?:&|$)', request.referrer or '') else 'light'
        return jsonify(success=True, settings={'theme': selected_theme})

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for width, dark in ((390, False), (430, True), (768, False), (1440, True)):
            with tempfile.TemporaryDirectory(prefix='eq-admin-browser-') as directory:
                shot = Path(directory) / 'screen.png'
                route = '/viewport?width=' + str(width) + '&dark=' + str(int(dark)) if width < 500 else '/?dark=' + str(int(dark))
                command = ['/usr/bin/chromium', '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-proxy-server', '--disable-background-networking', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', '--user-data-dir=' + str(Path(directory) / 'profile'), '--window-size=' + str(max(width, 500)) + ',1000', '--virtual-time-budget=22000', '--screenshot=' + str(shot), '--dump-dom', 'http://127.0.0.1:' + str(server.server_port) + route]
                process = subprocess.run(command, capture_output=True, text=True, timeout=45)
                match = re.search(r'<pre id="browser-test-result"[^>]*>(.*?)</pre>', process.stdout, re.S)
                result = json.loads(html.unescape(match[1])) if match and match[1] else {'status': 'fail', 'view': 'admin-extra', 'error': 'browser fixture did not finish', 'width': width}
                result.update(exit_code=process.returncode, requested_dark=dark)
                if shot.exists():
                    result['screenshot'] = base64.b64encode(shot.read_bytes()).decode()
                results.append(result)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    return results
