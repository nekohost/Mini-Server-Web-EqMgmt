"""[MINI-COMMENT: ASSISTANT.FOLD7.COVER.BROWSER.FIXTURE] [EN rev.5]
[Role] Measures narrow cover-screen composer hit areas under top-level mobile emulation and independent viewport/keyboard controls.
[Dependencies] Candidate UI transport and private Chromium CDP pipe; the fixture never represents a physical Samsung handset or keyboard.
[Impact] Records real layout/visual viewport evidence before scrolling, trusted touch sends and keyboard geometry so unsupported emulation cannot be mistaken for reproduced device behavior.
"""
from assistant_ui_browser_fixture import run_ui_browser


DRIVER = r'''
    const expectCompact=__EXPECT_COMPACT__;
    server.conversations.get(cid).title='커버 화면 보내기 확인';
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},overrideSupport={},report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),root=$('equipment-ai'),input=$('ai-input'),send=$('ai-send');
        let serial=0,trusted=0,activeSendPointer=null;const eventTrace=[];
        send.addEventListener('pointerdown',event=>{activeSendPointer=event.pointerId;});
        for(const type of ['pointerdown','pointerup','pointercancel','lostpointercapture','click','focusin','focusout'])document.addEventListener(type,event=>{
            if(!['ai-send','ai-input'].includes(event.target?.id)&&!event.target?.closest?.('#ai-send'))return;
            eventTrace.push({type,pointerId:event.pointerId,target:event.target?.id||event.target?.tagName,trusted:event.isTrusted,at:performance.now(),focused:document.activeElement?.id,send:box(send),compact:root.dataset.viewportCompact});
            if(eventTrace.length>80)eventTrace.shift();
        },true);
        send.addEventListener('click',event=>{if(event.isTrusted)trusted++;});
        const wait=async(test,label)=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const settle=async()=>{await sleep(120);void root.offsetHeight;await sleep(120);};
        const assert=(condition,label)=>{if(!condition)throw Error(label);checks.push(label);};
        const box=node=>{const r=node.getBoundingClientRect();return Object.fromEntries(['left','right','top','bottom','width','height'].map(k=>[k,Math.round(r[k]*100)/100]));};
        const turns=()=>server.requests.filter(x=>x.method==='POST'&&x.path.endsWith('/turns')).length;
        const bridge=async action=>{const id=++serial;window.__hitboxAction={id,...action};await wait(()=>window.__hitboxAck===id,'CDP action '+id);};
        const command=async(method,params={})=>{await bridge({kind:'emulation',method,params});overrideSupport[method]=window.__hitboxActionResult?.result;await settle();};
        const touch=async(x,y)=>{await bridge({kind:'touch',x,y});await settle();};
        const metric=(height=900,extra={})=>({width:innerWidth,height,deviceScaleFactor:3,mobile:true,screenWidth:innerWidth,screenHeight:900,...extra});
        const capture=label=>{
            const visual=window.visualViewport,r=send.getBoundingClientRect();
            const visible={top:visual?.offsetTop||0,left:visual?.offsetLeft||0,height:visual?.height||innerHeight,width:visual?.width||innerWidth};
            const map=[['center',.5,.5],['top',.5,.08],['bottom',.5,.92],['left',.08,.5],['right',.92,.5],['upper-left',.2,.2],['upper-right',.8,.2],['lower-left',.2,.8],['lower-right',.8,.8]].map(([name,fx,fy])=>{
                const x=r.left+r.width*fx,y=r.top+r.height*fy,hit=document.elementFromPoint(x,y);
                return {name,x,y,hit:hit?hit.id||hit.className||hit.tagName:null,sendHit:Boolean(hit&&send.contains(hit)),withinVisual:x>=visible.left&&x<=visible.left+visible.width&&y>=visible.top&&y<=visible.top+visible.height};
            });
            return layout[label]={innerWidth,innerHeight,clientHeight:document.documentElement.clientHeight,scrollY,visual:{...visible,scale:visual?.scale,pageTop:visual?.pageTop,pageLeft:visual?.pageLeft},keyboard:navigator.virtualKeyboard?{overlaysContent:navigator.virtualKeyboard.overlaysContent,rect:JSON.parse(JSON.stringify(navigator.virtualKeyboard.boundingRect))}:null,skin:document.documentElement.dataset.layoutSkin,focused:document.activeElement?.id,root:box(root),input:box(input),inputMaximum:input.style.maxHeight,inputScrollHeight:input.scrollHeight,pane:box($('ai-scroll')),send:box(send),bottom:box(document.querySelector('.ai-bottom')),fit:root.dataset.viewportFit,compact:root.dataset.viewportCompact,available:Number(root.dataset.viewportAvailable),minimum:Number(root.dataset.viewportMinimum),map};
        };
        const clickGrid=async label=>{
            const state=capture(label+'-before-touch');
            assert(state.map.every(p=>p.sendHit&&p.withinVisual),label+'-all-nine-points-unobstructed-without-scroll');
            for(const name of ['center','top','bottom','left','right']){
                const p=capture(label+'-'+name).map.find(point=>point.name===name),before=turns(),oldTrusted=trusted,draft=input.value;
                server.rejectNextTurn=true;await touch(p.x,p.y);await wait(()=>turns()===before+1&&!send.disabled,label+' native send');
                assert(turns()===before+1&&trusted===oldTrusted+1&&input.value===draft,label+'-'+name+'-one-trusted-send-retains-draft');
            }
        };
        try{
            await wait(()=>!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&root.dataset.viewportFit,'hydration');
            assert(window.parent===window&&navigator.maxTouchPoints>0&&innerWidth<=430,'direct-top-level-mobile-touch-emulation');
            assert(Math.abs(visualViewport.scale-1)<.01,'no-page-zoom');
            capture('mobile-baseline');
            for(const skin of ['standard','edge']){
                window.applyRoadmapSettings({layout_skin:skin});await settle();
                input.value='커버 화면 실제 포인터';input.dispatchEvent(new Event('input'));await settle();
                await clickGrid(skin+'-collapsed');
                const initial=box(input);await touch(initial.left+initial.width*.4,initial.top+initial.height*.4);
                assert(document.activeElement===input,skin+'-native-touch-focuses-input');
                input.value=Array(12).fill('커버 화면 다중행 초안').join('\n');input.dispatchEvent(new Event('input'));await settle();
                assert(box(input).height>=150,skin+'-focused-multiline-input-grows');
                capture(skin+'-focused-multiline');
                if(expectCompact){
                    const selector=box($('ai-level'));
                    await bridge({kind:'touch-start',x:selector.left+selector.width*.5,y:selector.top+selector.height*.5});
                    await command('Emulation.setDeviceMetricsOverride',metric(540));
                    assert(root.dataset.viewportCompact==='true'&&Number(root.dataset.viewportAvailable)<550,skin+'-unfinished-non-send-pointer-does-not-latch-measurement');
                    await bridge({kind:'touch-cancel'});await command('Emulation.setDeviceMetricsOverride',metric());
                }
                await command('Emulation.setSmallViewportHeightDifferenceOverride',{difference:80});capture(skin+'-addressbar-svh-override');
                await command('Emulation.setVirtualKeyboardGeometryOverride',{keyboardRect:{x:0,y:540,width:innerWidth,height:360}});capture(skin+'-keyboard-geometry-only');
                await command('Emulation.setDeviceMetricsOverride',metric(900,{viewport:{x:0,y:0,width:innerWidth,height:540,scale:1}}));capture(skin+'-visible-viewport-crop');
                await command('Emulation.setDeviceMetricsOverride',metric(900,{dontSetVisibleSize:true}));
                await command('Emulation.setVisibleSize',{width:innerWidth,height:540});capture(skin+'-visible-size-only');
                await command('Emulation.setDeviceMetricsOverride',metric());
                await command('Emulation.setVirtualKeyboardGeometryOverride',{});
                await command('Emulation.setSmallViewportHeightDifferenceOverride',{difference:0});
                await command('Emulation.setDeviceMetricsOverride',metric(540));capture(skin+'-layout-resize-540-before-scroll');
                await command('Input.synthesizeScrollGesture',{x:innerWidth*.5,y:250,yDistance:-350,speed:700,gestureSourceType:'touch'});capture(skin+'-layout-resize-540-after-native-scroll');
                if(expectCompact){
                    const focused=capture(skin+'-compact-540');
                    assert(focused.compact==='true'&&focused.input.height<160&&focused.inputScrollHeight>focused.input.height,skin+'-compact-540-keeps-bounded-native-textarea-scroll');
                    await clickGrid(skin+'-compact-540');
                }
                await command('Emulation.setDeviceMetricsOverride',metric(576));
                const partial=capture(skin+'-partial-button-before-scroll');
                if(expectCompact){
                    assert(partial.compact==='true'&&partial.map.every(p=>p.withinVisual&&p.sendHit),skin+'-compact-576-whole-send-visible-without-scroll');
                    await clickGrid(skin+'-compact-576');
                    const before=turns(),p=capture(skin+'-before-held-pointer').map.find(p=>p.name==='bottom'),oldRoot=box(root),oldSend=box(send);
                    server.rejectNextTurn=true;await bridge({kind:'touch-start',x:p.x,y:p.y});document.body.tabIndex=-1;document.body.focus();await settle();
                    assert(Math.abs(box(root).height-oldRoot.height)<.5&&Math.abs(box(send).top-oldSend.top)<.5,skin+'-pointer-held-focus-change-cannot-move-send');
                    window.dispatchEvent(new PointerEvent('pointerup',{pointerId:activeSendPointer,pointerType:'touch',clientX:p.x,clientY:p.y,bubbles:true}));
                    await settle();
                    assert(Math.abs(box(root).height-oldRoot.height)<.5&&Math.abs(box(send).top-oldSend.top)<.5,skin+'-modeled-delayed-native-activation-keeps-send-after-pointerup');
                    await bridge({kind:'touch-end'});await wait(()=>turns()===before+1&&!send.disabled,skin+' held-pointer submit');
                    document.body.focus();await settle();assert(root.dataset.viewportCompact==='false'&&Number(root.dataset.viewportMinimum)>=550,skin+'-blur-restores-normal-minimum-after-touch-completes');
                    input.focus();await settle();
                    const cancelled=capture(skin+'-before-cancelled-pointer').map.find(p=>p.name==='bottom');
                    await bridge({kind:'touch-start',x:cancelled.x,y:cancelled.y});document.body.focus();await settle();
                    await bridge({kind:'touch-cancel'});await settle();
                    assert(root.dataset.viewportCompact==='false'&&Number(root.dataset.viewportMinimum)>=550,skin+'-cancelled-send-pointer-releases-measurement');
                    input.focus();await settle();
                    const blurred=capture(skin+'-before-window-blur').map.find(p=>p.name==='bottom');
                    await bridge({kind:'touch-start',x:blurred.x,y:blurred.y});document.body.focus();window.dispatchEvent(new Event('blur'));await settle();
                    assert(root.dataset.viewportCompact==='false',skin+'-window-blur-releases-held-send-pointer');
                    await bridge({kind:'touch-cancel'});input.focus();await settle();
                    const abandoned=capture(skin+'-before-abandoned-activation').map.find(p=>p.name==='bottom');
                    send.dispatchEvent(new PointerEvent('pointerdown',{pointerId:909,pointerType:'touch',isPrimary:true,bubbles:true}));document.body.focus();
                    window.dispatchEvent(new PointerEvent('pointerup',{pointerId:909,pointerType:'touch',clientX:abandoned.x,clientY:abandoned.y,bubbles:true}));
                    await sleep(750);await settle();assert(root.dataset.viewportCompact==='false',skin+'-abandoned-click-recovers-within-ui-only-bound');
                    input.focus();await settle();
                }else{
                    assert(partial.send.top<innerHeight&&partial.send.bottom>innerHeight,skin+'-reduced-mobile-viewport-clips-lower-button');
                    for(const name of ['top','bottom']){
                        const p=partial.map.find(point=>point.name===name),before=turns(),oldTrusted=trusted;
                        server.rejectNextTurn=true;await touch(p.x,p.y);await sleep(120);
                        const expected=name==='top'?1:0;
                        assert(turns()===before+expected&&trusted===oldTrusted+expected,skin+'-partial-button-'+name+'-native-touch-accepted-'+expected);
                    }
                }
                window.scrollTo(0,document.documentElement.scrollHeight);await settle();
                await clickGrid(skin+'-partial-button-after-document-scroll');
                await command('Emulation.setDeviceMetricsOverride',metric());window.scrollTo(0,0);await settle();
                if(expectCompact){
                    input.focus();const draft=input.value,selected=input.selectionStart;
                    Object.defineProperty(visualViewport,'height',{configurable:true,get:()=>540});visualViewport.dispatchEvent(new Event('resize'));await settle();
                    const modeled=capture(skin+'-modeled-visual-api-height-540');
                    assert(innerHeight===900&&modeled.visual.height===540&&modeled.compact==='true'&&modeled.map.every(p=>p.withinVisual&&p.sendHit),skin+'-modeled-visual-api-shrink-keeps-complete-send');
                    delete visualViewport.height;visualViewport.dispatchEvent(new Event('resize'));await settle();
                    assert(root.dataset.viewportCompact==='false'&&input.style.maxHeight===''&&input.value===draft&&input.selectionStart===selected,skin+'-viewport-recovery-restores-bound-and-preserves-draft-selection');
                    await command('Emulation.setPageScaleFactor',{pageScaleFactor:2});
                    assert(root.dataset.viewportCompact==='false'&&root.dataset.viewportFit==='minimum'&&Number(root.dataset.viewportMinimum)>=550,skin+'-native-page-zoom-preserves-normal-minimum-fallback');
                    await command('Emulation.setPageScaleFactor',{pageScaleFactor:1});
                }
                $('ai-model-settings').open=true;$('ai-reasoning-support').open=true;await settle();
                await clickGrid(skin+'-both-disclosures');
                $('ai-model-settings').open=false;$('ai-reasoning-support').open=false;await settle();
            }
            await command('Emulation.setDeviceMetricsOverride',metric(580));input.focus();await settle();
            capture('final');
            assert(server.sent===0,'only-rejected-synthetic-turns-no-real-model-jobs');
            assert(document.documentElement.scrollWidth<=innerWidth+1,'no-horizontal-document-overflow');
            report.textContent=JSON.stringify({status:'pass',view:'fold7-cover-mobile-probe',checks,width:innerWidth,theme,layout,overrideSupport,trusted_send_clicks:trusted,turn_requests:turns(),native_action_count:serial,production_data_used:false,physical_handset_test:false,emulation:'Chromium top-level mobile metrics/DPR3/touch; independent keyboard geometry/visible-area/layout resize; CSS widths are probes, not verified handset CSS viewport'});
        }catch(error){capture('failure');report.textContent=JSON.stringify({status:'fail',view:'fold7-cover-mobile-probe',checks,width:innerWidth,theme,layout,eventTrace,error:error.message,trusted_send_clicks:trusted,turn_requests:turns(),physical_handset_test:false});}
        window.dispatchEvent(new Event('pagehide'));
    });
})();
'''


def run_browser(project, assets):
    """[Role] Uses direct top-level mobile frames so visualViewport evidence is not an iframe-height simulation."""
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 1234').replace('above_base: true', 'above_base: false')

    def mobile_capture(command, screenshot):
        """[Role] Replaces the iframe-only harness URL with the same candidate page in the mobile top-level viewport."""
        from send_hitbox_browser_fixture import capture_pointer_frames
        direct = [*command[:-1], command[-1].replace('/viewport?', '/?')]
        return capture_pointer_frames(direct, screenshot, mobile=True)

    # Require corrected behavior independently of implementation feature detection.
    driver = DRIVER.replace('__EXPECT_COMPACT__', 'true')
    return run_ui_browser(project, assets, setup + driver, sizes=(360,384,412,430), themes=('light','dark'), capture=mobile_capture)
