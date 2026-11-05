"""[MINI-COMMENT: ASSISTANT.SEND.HITBOX.BROWSER.FIXTURE]
[EN rev.6]
[Role] Checks the composer's real pointer hit targets and native send activation across measured layouts.
[Dependencies] Reviewed synthetic UI transport, Linux Chromium CDP pipe and candidate CSS/template only.
[Impact] Mouse/touch events target button coordinates; each accepted click must produce exactly one rejected synthetic turn, while disabled clicks produce none. Production services/accounts/models are never used.
"""
import base64
import fcntl
import json
import os
import select
import signal
import subprocess
import time

from assistant_ui_browser_fixture import run_ui_browser


def capture_pointer_frames(command, screenshot, mobile=False):
    """[Role] Dispatches real Chromium mouse/touch input on the loopback fixture through a private CDP pipe.
    [Dependencies] Linux stdlib descriptors and the fixture's request/ack bridge in its parent frame.
    [Impact] No debugger port or production browser is opened, and all descriptors/processes are released.
    """
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
            """[Role] Correlates bounded CDP replies and retains JavaScript exception diagnostics."""
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

        target = call('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        call('Runtime.enable', session=session)
        call('Page.enable', session=session)
        if mobile:
            from urllib.parse import parse_qs, urlsplit
            parameters = parse_qs(urlsplit(command[-1]).query)
            width = int(parameters['width'][0])
            mobile_metrics = {'width': width, 'height': 900, 'deviceScaleFactor': 3, 'mobile': True, 'screenWidth': width, 'screenHeight': 900}
            call('Emulation.setDeviceMetricsOverride', mobile_metrics, session)
            call('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5}, session)
            call('Emulation.setUserAgentOverride', {'userAgent': 'Mozilla/5.0 (Linux; Android 16; Synthetic cover-screen probe) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36'}, session)
        call('Page.navigate', {'url': command[-1]}, session)
        handled = None
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            state = call('Runtime.evaluate', {'expression': "({result:document.getElementById('browser-test-result')?.textContent||'',action:window.__hitboxAction||null})", 'returnByValue': True}, session)['result'].get('value', {})
            if state.get('result'):
                break
            action = state.get('action')
            if action and action['id'] != handled:
                handled = action['id']
                x, y = action.get('x'), action.get('y')
                if action['kind'] == 'emulation':
                    allowed = {'Emulation.setDeviceMetricsOverride', 'Emulation.setVirtualKeyboardGeometryOverride', 'Emulation.setVisibleSize', 'Emulation.setSmallViewportHeightDifferenceOverride', 'Emulation.setPageScaleFactor', 'Input.synthesizeScrollGesture'}
                    if action['method'] not in allowed:
                        raise ValueError('unsupported fixture emulation action')
                    try:
                        outcome = call(action['method'], action.get('params', {}), session)
                    except RuntimeError as error:
                        if "wasn't found" not in str(error):
                            raise
                        outcome = {'unsupported': True, 'error': str(error)}
                    call('Runtime.evaluate', {'expression': 'window.__hitboxActionResult=' + json.dumps({'id': handled, 'result': outcome})}, session)
                elif action['kind'] == 'touch-start':
                    call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'radiusX': 1, 'radiusY': 1}]}, session)
                elif action['kind'] == 'touch-end':
                    call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}, session)
                elif action['kind'] == 'touch-cancel':
                    call('Input.dispatchTouchEvent', {'type': 'touchCancel', 'touchPoints': []}, session)
                elif action['kind'] == 'touch':
                    call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'radiusX': 1, 'radiusY': 1}]}, session)
                    call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}, session)
                else:
                    call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y}, session)
                    call('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}, session)
                    call('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1}, session)
                call('Runtime.evaluate', {'expression': 'window.__hitboxAck=' + json.dumps(handled)}, session)
            time.sleep(.01)
        else:
            raise TimeoutError('pointer fixture did not complete; exceptions=' + repr(exceptions[-3:]))
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
    server.conversations.get(cid).title='보내기 영역 확인';
    const nativeHitboxFetch=server.fetch.bind(server);
    server.fetch=async(path,options={})=>{
        if((options.method||'GET')==='POST'&&new URL(path,location.origin).pathname.endsWith('/turns')&&server.holdNativeTurn){server.nativeTurnEntered=true;await server.holdNativeTurn;}
        return nativeHitboxFetch(path,options);
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),send=$('ai-send'),input=$('ai-input'),root=$('equipment-ai');
        const wait=async(test,label)=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const settle=async()=>{await sleep(80);void root.offsetHeight;await sleep(80);};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const posts=()=>server.requests.filter(x=>x.method==='POST'&&x.path.endsWith('/turns'));
        const box=node=>{const r=node.getBoundingClientRect();return Object.fromEntries(['left','top','right','bottom','width','height'].map(k=>[k,Math.round(r[k]*100)/100]));};
        const points=()=>{const r=send.getBoundingClientRect();return [['center',.5,.5],['top',.5,.08],['bottom',.5,.92],['left',.08,.5],['right',.92,.5],['upper-left',.2,.2],['upper-right',.8,.2],['lower-left',.2,.8],['lower-right',.8,.8]].map(([name,x,y])=>({name,x:r.left+r.width*x,y:r.top+r.height*y}));};
        let pointerId=0,trustedClicks=0;
        send.addEventListener('click',event=>{if(event.isTrusted)trustedClicks++;});
        const hitMap=()=>points().map(point=>{const hit=document.elementFromPoint(point.x,point.y);return {...point,hit:hit?hit.id||hit.className||hit.tagName:null,accepted:Boolean(hit&&send.contains(hit))};});
        const pointer=async(point,kind=innerWidth<=760?'touch':'mouse')=>{
            const frame=window.frameElement.getBoundingClientRect(),id=++pointerId;
            window.parent.__hitboxAction={id,kind,x:point.x+frame.left,y:point.y+frame.top};
            await wait(()=>window.parent.__hitboxAck===id,'native pointer acknowledgement');
        };
        const capture=label=>layout[label]={skin:document.documentElement.dataset.layoutSkin,send:box(send),icon:box(send.querySelector('span')),sendStyle:{transform:getComputedStyle(send).transform,before:{content:getComputedStyle(send,'::before').content,pointerEvents:getComputedStyle(send,'::before').pointerEvents},after:{content:getComputedStyle(send,'::after').content,pointerEvents:getComputedStyle(send,'::after').pointerEvents}},actions:box(document.querySelector('.ai-composer-actions')),bottom:box(document.querySelector('.ai-bottom')),modelPanel:box($('ai-model-panel')),reasoningPanel:box($('ai-reasoning-panel')),input:box(input),map:hitMap(),fit:root.dataset.viewportFit,minimum:Number(root.dataset.viewportMinimum),available:Number(root.dataset.viewportAvailable),documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,clientHeight:document.documentElement.clientHeight};
        const probe=async (label,multiline=false)=>{
            input.value=multiline?Array(12).fill('실제 포인터 다중행 '+label).join('\n'):'실제 포인터 '+label;input.dispatchEvent(new Event('input'));await settle();
            const unscrolled=capture(label+'-before-scroll');
            if(unscrolled.fit==='fit')assert(unscrolled.map.every(p=>p.accepted),label+'-fitted-button-is-unobstructed-before-any-scroll');
            send.scrollIntoView({block:'nearest'});await settle();
            const state=capture(label);
            assert(state.map.every(p=>p.accepted),label+'-nine-interior-points-hit-send');
            assert(state.send.height>=(innerWidth<=760?44:36)-.5,label+'-existing-control-height-retained');
            if(multiline)assert(state.input.height>100,label+'-actual-input-growth-exercised');
            for(const name of ['center','top','bottom','left','right']){
                const before=posts().length,beforeTrusted=trustedClicks,draft=input.value;
                server.rejectNextTurn=true;
                await pointer(points().find(p=>p.name===name));
                await wait(()=>posts().length===before+1&&!send.disabled,'one rejected synthetic turn from '+label+' '+name);
                await sleep(30);
                assert(posts().length===before+1&&trustedClicks===beforeTrusted+1&&input.value===draft,label+'-'+name+'-trusted-click-submits-once-and-keeps-rejected-draft');
            }
        };
        try{
            await wait(()=>!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&root.dataset.viewportFit,'hydration');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            for(const skin of ['standard','edge']){
                window.applyRoadmapSettings({layout_skin:skin});await settle();
                assert(document.documentElement.dataset.layoutSkin===skin,skin+'-actual-global-frame-skin-applied');
                await probe(skin+'-collapsed');
                $('ai-model-settings').open=true;await settle();await probe(skin+'-model-open');
                $('ai-reasoning-support').open=true;await settle();await probe(skin+'-both-open');
                $('ai-model-settings').open=false;await settle();await probe(skin+'-reasoning-open');
                $('ai-reasoning-support').open=false;await settle();await probe(skin+'-tall-input',true);
            }
            document.body.tabIndex=-1;document.body.focus();window.frameElement.style.height='480px';await settle();
            const short=capture('unfocused-minimum-fallback');assert(short.fit==='minimum'&&short.minimum>=(innerWidth<=760?550:620)&&short.documentHeight>short.clientHeight,'unfocused-short-viewport-preserves-original-minimum-height-and-page-access');
            await probe('short-viewport');
            const focusedShort=capture('after-short-native-sends');
            if(root.dataset.viewportCompact==='true')assert(focusedShort.fit==='fit'&&focusedShort.minimum<=focusedShort.available,'focused-short-viewport-reports-actual-effective-compact-minimum');
            else assert(focusedShort.fit==='minimum'&&focusedShort.minimum>=(innerWidth<=760?550:620),'short-viewport-outside-compact-retains-original-minimum');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            const before=posts().length,beforeTrusted=trustedClicks;
            let releaseTurn;server.holdNativeTurn=new Promise(resolve=>{releaseTurn=resolve;});server.rejectNextTurn=true;
            await pointer(points()[0]);await wait(()=>server.nativeTurnEntered&&send.disabled,'real-pending-submit-disables-send');
            for(const point of points().slice(0,5))await pointer(point);
            assert(posts().length===before&&trustedClicks===beforeTrusted+1,'pending-disabled-button-rejects-all-five-native-clicks');
            server.holdNativeTurn=null;releaseTurn();await wait(()=>posts().length===before+1&&!send.disabled,'pending rejection restores send');
            assert(posts().length===before+1&&trustedClicks===beforeTrusted+1,'pending-submit-retains-single-request-and-recovers-after-rejection');
            await settle();capture('final');
            assert(document.documentElement.scrollWidth<=innerWidth+1,'no-document-horizontal-overflow');
            assert(posts().every(x=>x.headers['X-CSRFToken']==='fixture-csrf')&&server.sent===0,'native-send-retains-csrf-and-never-creates-a-real-job');
            report.textContent=JSON.stringify({status:'pass',view:'send-hitbox',checks,width:innerWidth,theme,layout,native_pointer_count:pointerId,trusted_send_clicks:trustedClicks,turn_requests:posts().length,production_data_used:false,interaction:innerWidth<=760?'Chromium CDP touchStart/touchEnd':'Chromium CDP mouseMoved/mousePressed/mouseReleased'});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'send-hitbox',checks,width:innerWidth,theme,error:error.message,layout,native_pointer_count:pointerId,trusted_send_clicks:trustedClicks,turn_requests:posts().length,geometry:capture('failure')});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
'''


def run_browser(project, assets):
    """[Role] Covers PC/mobile and both themes using the reviewed transport prefix and actual pointer events."""
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 1234').replace('above_base: true', 'above_base: false')
    return run_ui_browser(project, assets, setup + DRIVER, sizes=(320,390,412,760,761,820,1440), themes=('light','dark'), capture=capture_pointer_frames)
