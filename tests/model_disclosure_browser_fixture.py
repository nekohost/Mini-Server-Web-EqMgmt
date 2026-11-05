"""[MINI-COMMENT: ASSISTANT.MODEL.DISCLOSURE.BROWSER.FIXTURE]
[EN rev.2]
[Role] Verifies native default-collapsed model controls beside reasoning, separate expanded body space and retained selection/refresh behavior.
[Dependencies] Existing synthetic transport and reviewed real-frame Linux Chromium capture; no production DB/account/model.
[Impact] Records both disclosure geometries, errors outside the panel and the chosen screenshot state without weakening existing functional checks.
"""
from assistant_ui_browser_fixture import run_ui_browser


DRIVER = r'''
    server.conversations.get(cid).title='내 장비 대화';
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),panel=$('ai-model-settings'),summary=panel.querySelector('summary');
        const wait=async(test,label)=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const settle=async()=>{await sleep(100);void panel.offsetHeight;await sleep(100);};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const reads=()=>server.requests.filter(x=>x.path==='/api/ai/models').length;
        const posts=action=>server.requests.filter(x=>x.method==='POST'&&(!action||x.path.endsWith('/'+action)));
        const rect=element=>{const box=element.getBoundingClientRect();return {top:box.top,bottom:box.bottom,left:box.left,right:box.right,height:box.height,width:box.width};};
        const capture=()=>({panelOpen:panel.open,panel:rect(panel),summary:rect(summary),composer:rect($('ai-form')),chat:rect($('ai-scroll')),reasoning:rect($('ai-level')),model:rect($('ai-model')),refresh:rect($('ai-model-refresh')),support:rect($('ai-reasoning-support')),documentHeight:document.documentElement.scrollHeight,clientHeight:document.documentElement.clientHeight,width:innerWidth,height:innerHeight});
        try{
            await wait(()=>!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&$('equipment-ai').dataset.viewportFit,'initial hydration');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            assert(panel.tagName==='DETAILS'&&!panel.open&&!panel.hasAttribute('open')&&summary.textContent.trim()==='AI 모델 선택','native-model-panel-defaults-to-collapsed-after-hydration');
            assert(panel.contains($('ai-model'))&&panel.contains($('ai-model-refresh'))&&!panel.contains($('ai-level'))&&!panel.contains($('ai-send')),'only-model-and-refresh-are-inside-disclosure');
            assert(Boolean($('ai-level').compareDocumentPosition(panel)&Node.DOCUMENT_POSITION_FOLLOWING)&&Boolean(panel.compareDocumentPosition($('ai-reasoning-support'))&Node.DOCUMENT_POSITION_FOLLOWING),'reasoning-disclosure-support-dom-order');
            layout.initial=capture();
            const actionRow=document.querySelector('.ai-composer-actions'),inlineGroup=document.querySelector('.ai-inline-disclosures');
            assert($('equipment-ai').dataset.disclosureLayout==='stacked'?rect(inlineGroup).left>=layout.initial.reasoning.right-1&&rect(inlineGroup).bottom<=rect(actionRow).bottom+1:rect(inlineGroup).top>=layout.initial.reasoning.bottom-1,'collapsed-disclosures-use-measured-inline-two-lines-or-narrow-fallback');
            assert(!panel.contains($('ai-model-status'))&&$('ai-model-status').getAttribute('role')==='status','model-status-is-live-and-outside-collapsible-content');
            const answer=document.querySelector('.ai-answer');
            const extra=document.createElement('div');extra.textContent='대화 내용을 보존하는 화면 크기 확인용 문장입니다. '.repeat(350);answer.append(extra);
            $('ai-input').value='접기/펼치기 중 보존할 초안';$('ai-input').dispatchEvent(new Event('input'));await settle();
            const pane=$('ai-scroll');pane.scrollTop=70;
            const before={model:$('ai-model').value,level:$('ai-level').value,reads:reads(),posts:posts().length,top:pane.scrollTop};
            layout.collapsed=capture();summary.focus();summary.click();await settle();layout.expanded=capture();
            assert(panel.open&&$('ai-model').checkVisibility()&&$('ai-model-refresh').checkVisibility(),'native-summary-click-reveals-existing-controls');
            assert(layout.expanded.composer.height>layout.collapsed.composer.height+30&&layout.collapsed.chat.height>layout.expanded.chat.height+30,'collapsing-removes-control-row-and-increases-chat-space');
            layout.savedHeight=layout.expanded.composer.height-layout.collapsed.composer.height;
            assert(layout.expanded.model.top>=rect(actionRow).bottom&&rect($('ai-model-panel')).right<=layout.expanded.composer.right+1&&rect(document.querySelector('.ai-disclosure-spacer')).bottom>=rect($('ai-model-panel')).bottom,'expanded-model-body-reserves-separate-full-width-space-below-actions');
            const controls=[$('ai-model'),$('ai-model-refresh'),$('ai-level')];
            assert(controls.every(x=>Math.abs(rect(x).height-rect(controls[0]).height)<.5)&&rect(controls[0]).height>=(innerWidth<=760?44:36)-.5&&controls.every(x=>getComputedStyle(x).fontSize==='12px'),'moved-model-select-and-refresh-retain-shared-control-size');
            assert(rect($('ai-model')).width>20&&rect($('ai-model')).width<=136.5&&layout.expanded.model.left>=layout.expanded.composer.left&&layout.expanded.refresh.right<=layout.expanded.composer.right+1,'expanded-controls-fit-composer-and-model-width-cap');
            summary.click();await settle();
            assert(!panel.open&&$('ai-model').value===before.model&&$('ai-level').value===before.level&&$('ai-input').value==='접기/펼치기 중 보존할 초안'&&document.contains(answer),'closing-keeps-existing-nodes-model-reasoning-and-draft');
            assert(reads()===before.reads&&posts().length===before.posts&&Math.abs(pane.scrollTop-before.top)<=1,'toggle-does-not-refetch-save-submit-or-reset-reader');
            summary.click();await settle();
            let release;server.holdModels=new Promise(resolve=>{release=resolve;});let oldReads=reads();$('ai-model-refresh').click();
            await wait(()=>reads()>oldReads&&$('ai-model-refresh').disabled,'pending inventory');
            summary.click();await settle();
            assert(!panel.open&&!$('ai-model-status').hidden&&$('ai-model-status').checkVisibility()&&$('ai-model-status').textContent.includes('목록'),'loading-remains-visible-when-panel-is-closed');
            release();await wait(()=>!$('ai-model-refresh').disabled,'inventory finished');
            assert(!panel.open&&reads()===oldReads+1&&$('ai-model').value===before.model,'refresh-completion-keeps-panel-closed-and-current-model');
            summary.click();server.failModelReads=1;oldReads=reads();$('ai-model-refresh').click();await wait(()=>reads()>oldReads&&!$('ai-model-refresh').disabled&&$('ai-model-status').textContent.includes('오류'),'inventory error');
            summary.click();await settle();
            assert(!panel.open&&$('ai-model-status').checkVisibility()&&$('ai-notice').checkVisibility()&&$('ai-model-status').textContent.includes('오류'),'refresh-error-cause-stays-visible-outside-closed-panel');
            summary.click();oldReads=reads();$('ai-model-refresh').click();await wait(()=>reads()>oldReads&&!$('ai-model-refresh').disabled&&$('ai-model-status').hidden,'inventory retry');
            assert(panel.open&&$('ai-model').value===before.model&&$('ai-input').value==='접기/펼치기 중 보존할 초안','successful-retry-preserves-open-state-selection-and-draft');
            const selectionBefore=posts('selection').length,turnsBefore=posts('turns').length;
            $('ai-model').value='f'.repeat(32);$('ai-model').dispatchEvent(new Event('change'));await wait(()=>!$('ai-model').disabled&&$('ai-level').value==='default','alternate model saved');
            assert(panel.open&&posts('selection').length===selectionBefore+1&&$('ai-model-status').textContent.includes('대화 전용'),'model-change-keeps-panel-open-and-existing-save-path');
            summary.click();await settle();assert($('ai-model-status').checkVisibility()&&$('ai-level').disabled,'chat-only-model-explanation-remains-visible-while-collapsed');
            summary.click();$('ai-model').value=before.model;$('ai-model').dispatchEvent(new Event('change'));await wait(()=>!$('ai-model').disabled&&$('ai-level').value==='medium','original model restored');
            assert(panel.open&&$('ai-level').querySelector('[value=high]').disabled&&$('ai-level').querySelector('[value=max]').disabled&&!$('ai-reasoning-support').hidden,'reasoning-support-and-disabled-options-remain-independent');
            assert(posts('turns').length===turnsBefore&&posts().every(x=>x.headers['X-CSRFToken']==='fixture-csrf'),'settings-use-csrf-without-submitting-a-chat-turn');
            const expectedOpen=innerWidth===390||innerWidth===1440;
            if(panel.open!==expectedOpen)summary.click();await settle();layout.final=capture();
            assert(layout.final.documentHeight<=layout.final.clientHeight+1&&document.documentElement.scrollWidth<=innerWidth+1,'final-disclosure-state-keeps-fitted-page-without-outer-overflow');
            pane.scrollTop=0;
            report.textContent=JSON.stringify({status:'pass',view:expectedOpen?'model-disclosure-expanded':'model-disclosure-collapsed',checks,width:innerWidth,theme,layout,production_data_used:false,interaction:'native summary click and programmatic focus; physical keyboard/touch not exercised'});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'model-disclosure',checks,width:innerWidth,theme,error:error.message,layout,geometry:capture()});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
'''


def run_browser(project, assets):
    """[Role] Exercises mobile/tablet/desktop widths in both themes with real frames and synthetic data only."""
    from viewport_scrollbar_browser_fixture import capture_real_frames
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 1234').replace('above_base: true', 'above_base: false')
    return run_ui_browser(project, assets, setup + DRIVER, sizes=(320,390,820,1440), themes=('light','dark'), capture=capture_real_frames)
