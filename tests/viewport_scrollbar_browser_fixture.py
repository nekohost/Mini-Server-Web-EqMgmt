"""[MINI-COMMENT: ASSISTANT.VIEWPORT.BROWSER.FIXTURE]
[EN rev.3]
[Role] Verifies measured page fitting, minimum fallback and themed native scrolling under live geometry changes.
[Dependencies] Reviewed synthetic chat transport and Linux-only Chromium UI fixture; no production model/account/DB.
[Impact] Records document/viewport dimensions and real element offsets, preserving draft/model/reader state through width, height and header changes.
"""
from assistant_ui_browser_fixture import run_ui_browser


def capture_real_frames(command, screenshot):
    """[Role] Drives isolated Linux Chromium over its private CDP pipe in real time, avoiding virtual-time RAF starvation.
    [Dependencies] Linux stdlib pipe/select/posix_spawn; existing loopback-only command and temporary browser profile.
    [Impact] No extra package, debugger TCP endpoint, production browser or remote service is used; the process group and descriptors are always released.
    """
    import base64
    import fcntl
    import json
    import os
    import select
    import signal
    import subprocess
    import time

    incoming, send = os.pipe()
    receive, outgoing = os.pipe()
    child_in = fcntl.fcntl(incoming, fcntl.F_DUPFD_CLOEXEC, 10)
    child_out = fcntl.fcntl(outgoing, fcntl.F_DUPFD_CLOEXEC, 10)
    quiet = os.open(os.devnull, os.O_WRONLY)
    args = [part for part in command[:-1] if not part.startswith(('--virtual-time-budget=', '--screenshot=')) and part != '--dump-dom']
    args += ['--remote-debugging-pipe', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', 'about:blank']
    pid = None
    try:
        pid = os.posix_spawn(args[0], args, os.environ, file_actions=[
            (os.POSIX_SPAWN_DUP2, child_in, 3), (os.POSIX_SPAWN_DUP2, child_out, 4),
            (os.POSIX_SPAWN_DUP2, quiet, 1), (os.POSIX_SPAWN_DUP2, quiet, 2),
        ], setpgroup=0)
        os.close(incoming); incoming = None
        os.close(outgoing); outgoing = None
        serial, pending, exceptions = 0, b'', []

        def call(method, params=None, session=None):
            """[Role] Correlates one bounded CDP reply while retaining diagnostic JavaScript exception events."""
            nonlocal serial, pending
            serial += 1
            message = {'id': serial, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            os.write(send, json.dumps(message).encode() + b'\0')
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if b'\0' not in pending:
                    if not select.select([receive], [], [], max(0, deadline - time.monotonic()))[0]:
                        break
                    chunk = os.read(receive, 65536)
                    if not chunk:
                        raise RuntimeError('isolated Chromium CDP pipe closed')
                    pending += chunk
                    continue
                raw, pending = pending.split(b'\0', 1)
                value = json.loads(raw)
                if value.get('method') == 'Runtime.exceptionThrown':
                    exceptions.append(value.get('params', {}).get('exceptionDetails', {}).get('text', 'JavaScript exception'))
                if value.get('id') == serial:
                    if 'error' in value:
                        raise RuntimeError(str(value['error']))
                    return value.get('result', {})
            raise TimeoutError('isolated Chromium CDP reply timed out: ' + method)

        target = call('Target.createTarget', {'url': command[-1]})['targetId']
        session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        call('Runtime.enable', session=session)
        call('Page.enable', session=session)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            value = call('Runtime.evaluate', {'expression': "document.getElementById('browser-test-result')?.textContent || ''", 'returnByValue': True}, session)
            if value.get('result', {}).get('value'):
                break
            time.sleep(.05)
        else:
            raise TimeoutError('real-frame UI fixture did not complete; exceptions=' + repr(exceptions[-3:]))
        markup = call('Runtime.evaluate', {'expression': 'document.documentElement.outerHTML', 'returnByValue': True}, session)['result']['value']
        capture = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False}, session)
        screenshot.write_bytes(base64.b64decode(capture['data']))
        return subprocess.CompletedProcess(args, 0, markup, '')
    finally:
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        for descriptor in (incoming, send, receive, outgoing, child_in, child_out, quiet):
            if descriptor is not None:
                os.close(descriptor)


DRIVER = r'''
    const nativeFixtureFetch=server.fetch.bind(server);
    for(let index=1;index<=35;index++)server.conversations.set((index+100).toString(16).padStart(32,'0'),{id:(index+100).toString(16).padStart(32,'0'),title:'스크롤 확인 대화 '+index,updated:-index,is_deleted:0,lifecycle_revision:0,selection_id:modelId,next_level:'medium'});
    server.fetch=async(path,options={})=>{
        const result=await nativeFixtureFetch(path,options),url=new URL(path,location.origin);
        if((options.method||'GET')==='GET'&&url.pathname==='/api/ai/conversations'){
            const value=await result.json();value.conversations=[...server.conversations.values()].filter(x=>!x.is_deleted).sort((a,b)=>b.updated-a.updated);value.next_cursor=null;return server.respond(value);
        }
        return result;
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id);
        const wait=async(test,label='condition')=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const settle=async()=>{await sleep(80);void $('equipment-ai').offsetHeight;await sleep(80);};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const capture=()=>({width:innerWidth,height:innerHeight,documentHeight:document.documentElement.scrollHeight,clientHeight:document.documentElement.clientHeight,documentWidth:document.documentElement.scrollWidth,mode:$('equipment-ai').dataset.viewportFit,available:Number($('equipment-ai').dataset.viewportAvailable),minimum:Number($('equipment-ai').dataset.viewportMinimum),rootHeight:$('equipment-ai').getBoundingClientRect().height,rootTop:$('equipment-ai').getBoundingClientRect().top+scrollY,scrollbar:getComputedStyle($('ai-scroll')).scrollbarColor,scrollbarWidth:getComputedStyle($('ai-scroll')).scrollbarWidth});
        const fit=label=>{
            const geometry=capture();layout[label]=geometry;
            if(geometry.available>=geometry.minimum){assert(geometry.mode==='fit',label+'-fits-when-minimum-is-met');assert(geometry.documentHeight<=geometry.clientHeight+1,label+'-no-document-vertical-scroll');}
            else{assert(geometry.mode==='minimum',label+'-minimum-fallback');assert(geometry.documentHeight>geometry.clientHeight,label+'-short-screen-keeps-page-access');}
            assert(geometry.documentWidth<=geometry.width+1,label+'-no-document-horizontal-overflow');
            return geometry;
        };
        try{
            await wait(()=>module.exports.markdown&&!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&$('equipment-ai').dataset.viewportFit,'ready');
            const originalWidth=innerWidth,frame=window.frameElement;
            frame.style.height=(innerWidth<=760?844:900)+'px';await settle();fit('initial');
            const answer=document.querySelector('.ai-answer');
            const table='| '+Array.from({length:20},(_,i)=>'항목 '+i).join(' | ')+' |\n| '+Array(20).fill('---').join(' | ')+' |\n'+Array(4).fill('| '+Array(20).fill('장비 정보').join(' | ')+' |').join('\n');
            module.exports.markdown(answer,table+'\n\n'+Array(50).fill('세로 스크롤 확인용 대화 내용입니다. 사용자가 요청한 정보를 계속 확인할 수 있습니다.').join('\n\n'));
            const region=answer.querySelector('.ai-table-scroll');region.querySelector('table').style.minWidth='2200px';
            await settle();
            const pane=$('ai-scroll');pane.scrollTop=90;region.scrollLeft=130;const sidebar=$('ai-sidebar');sidebar.scrollTop=70;
            assert(pane.scrollTop>0&&region.scrollLeft>0,'native-vertical-and-horizontal-scroll-offsets-work');
            if(innerWidth>760)assert(sidebar.scrollTop>0,'native-sidebar-scroll-offset-works');
            const colored=getComputedStyle(pane).scrollbarColor;
            assert(CSS.supports('scrollbar-color','red blue')&&colored!=='auto'&&getComputedStyle(pane).scrollbarWidth==='thin','native-scrollbar-has-theme-colors-and-thin-width');
            assert(getComputedStyle(region).scrollbarColor===colored&&getComputedStyle(sidebar).scrollbarColor===colored,'horizontal-list-and-conversation-share-theme-palette');
            assert(getComputedStyle(pane).overflowY==='auto'&&getComputedStyle(region).overflowX==='auto','native-scrolling-is-not-hidden-or-replaced');
            document.documentElement.classList.toggle('dark',theme!=='dark');await settle();
            assert(getComputedStyle(pane).scrollbarColor!==colored,'scrollbar-palette-changes-live-with-theme');
            document.documentElement.classList.toggle('dark',theme==='dark');await settle();
            const selected=$('ai-model').value,level=$('ai-level').value,source=answer;
            $('ai-input').value='리사이즈 중 보존할 초안';$('ai-input').dispatchEvent(new Event('input'));await settle();
            const oldTop=pane.scrollTop,oldLeft=region.scrollLeft,postsBefore=server.requests.filter(x=>x.method==='POST').length;
            frame.style.height='1100px';await settle();fit('taller');
            assert($('ai-input').value==='리사이즈 중 보존할 초안'&&$('ai-model').value===selected&&$('ai-level').value===level&&document.contains(source),'resize-preserves-draft-model-reasoning-and-message-node');
            assert(Math.abs(pane.scrollTop-oldTop)<=1&&Math.abs(region.scrollLeft-oldLeft)<=1,'height-resize-preserves-reader-scroll-offsets');
            const nav=document.querySelector('.app-nav-row'),beforeNav=$('equipment-ai').getBoundingClientRect().height;
            nav.style.paddingTop='32px';nav.style.paddingBottom='32px';await settle();fit('largerHeader');
            assert($('equipment-ai').getBoundingClientRect().height<beforeNav-20,'header-height-change-recomputes-remaining-space');
            nav.style.removeProperty('padding-top');nav.style.removeProperty('padding-bottom');await settle();
            frame.style.height='420px';await settle();fit('belowMinimum');
            assert(!['hidden','clip'].includes(getComputedStyle(document.documentElement).overflowY)&&!['hidden','clip'].includes(getComputedStyle(document.body).overflowY),'short-screen-content-not-clipped-by-page-overflow-rule');
            frame.style.height='1000px';frame.style.width=(originalWidth<=760?820:390)+'px';await settle();fit('breakpointCrossing');
            assert(Number($('equipment-ai').dataset.viewportMinimum)>=(innerWidth<=760?550:620),'current-breakpoint-minimum-preserved');
            frame.style.width=originalWidth+'px';frame.style.height=(originalWidth<=760?844:900)+'px';await settle();fit('restored');
            assert(server.requests.filter(x=>x.method==='POST').length===postsBefore,'geometry-and-theme-changes-do-not-send-business-or-model-requests');
            const stable=[];for(let i=0;i<12;i++){await sleep(20);stable.push($('equipment-ai').getBoundingClientRect().height);}
            assert(new Set(stable).size===1,'height-observation-settles-without-resize-loop');
            assert(!document.querySelector('.ai-footnote')&&!document.querySelector('.ai-bottom .ai-file-tools'),'merged-csv-footer-cleanup-preserved');
            const requested=document.createElement('p');module.exports.markdown(requested,'[CSV 가져오기 열기](/assistant?panel=csv-import)');$('ai-messages').append(requested);requested.querySelector('a').click();
            assert($('ai-file-dialog').open&&getComputedStyle($('ai-file-dialog')).scrollbarColor===getComputedStyle(pane).scrollbarColor,'csv-dialog-and-its-scrollbar-survive-viewport-merge');
            $('ai-file-close').click();await settle();fit('afterDialog');
            pane.scrollTop=0;region.scrollLeft=100;if(originalWidth>760)sidebar.scrollTop=30;
            report.textContent=JSON.stringify({status:'pass',view:'viewport-and-scrollbars',checks,width:innerWidth,theme,layout,reader:{top:pane.scrollTop,left:region.scrollLeft},production_data_used:false,keyboard:'programmatic scrolling/focus; physical touch and thumb drag not emulated'});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'viewport-and-scrollbars',checks,width:innerWidth,theme,error:error.message,layout,geometry:capture()});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
'''


def run_browser(project,assets):
    """[Role] Uses actual widths and repeated height/header changes in both themes with synthetic owner data."""
    source=assets['tests/test_equipment_ai_ui.js']
    anchor="    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor)!=1:
        raise ValueError('reviewed transport bootstrap anchor changed')
    return run_ui_browser(project,assets,source.split(anchor,1)[0]+DRIVER,sizes=(320,390,820,1440),themes=('light','dark'),capture=capture_real_frames)
