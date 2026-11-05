"""[MINI-COMMENT: ASSISTANT.CSV.POPUP.BROWSER.FIXTURE]
[EN rev.1]
[Role] Exercises requested CSV/attachment dialogs against a synthetic transport and captures exact-width themed screenshots.
[Dependencies] The reviewed UI fixture transport prefix, real candidate HTML/CSS/JS and Linux-only run_ui_browser.
[Impact] No real account, model, equipment, upload or download is used; late responses and ambiguous commits are tested without production mutations.
"""
from assistant_ui_browser_fixture import run_ui_browser


SCRIPT = r'''
    document.addEventListener('DOMContentLoaded', async () => {
        const checks=[], layout={}, report=document.createElement('pre'); report.id='browser-test-result'; report.hidden=true; document.body.append(report);
        const $=id=>document.getElementById(id);
        const wait=async(test,label='condition')=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const requests=()=>server.requests.filter(x=>x.method==='POST');
        const posts=action=>requests().filter(x=>x.path.endsWith('/'+action));
        const file=()=>{const selected=new DataTransfer();selected.items.add(new File(['Name,OptionId\n팝업 확인 장비,3'],'장비-가져오기.csv',{type:'text/csv'}));$('ai-csv-file').files=selected.files;$('ai-csv-file').dispatchEvent(new Event('change'));};
        const response=()=>{
            const element=document.createElement('p');element.className='ai-answer';
            module.exports.markdown(element,'요청하신 작업을 아래에서 진행할 수 있습니다.\n[CSV 가져오기 열기](/assistant?panel=csv-import) · [내 장비 CSV](/api/ai/csv/export?scope=my) · [공개 장비 CSV](/api/ai/csv/export?scope=public) · [파일 첨부 열기](/assistant?panel=attachment)');
            $('ai-messages').append(element);return element;
        };
        const originalFetch=server.fetch.bind(server);let mode='',releasePreview=null,releaseCommit=null;
        server.fetch=async(path,options={})=>{
            const url=new URL(path,location.origin);
            if(url.pathname.endsWith('/csv/preview')&&mode==='hold'){
                const pending=originalFetch(path,options);mode='';await new Promise(resolve=>{releasePreview=resolve;});return pending;
            }
            if(url.pathname.endsWith('/csv/preview')&&mode==='invalid'){
                mode='';await originalFetch(path,options);return server.respond({success:false,message:'CSV 3행의 옵션 번호를 확인해 주세요.'},422);
            }
            if(url.pathname.endsWith('/csv/preview')&&mode==='rows'){
                mode='';await originalFetch(path,options);return server.respond({success:true,count:2,rows:[{Name:'업무용 노트북',OptionId:3,IsPublic:0},{Name:'예비 장비',OptionId:3,IsPublic:0}],errors:[],token:'synthetic-popup-preview'});
            }
            if(url.pathname.endsWith('/csv/commit')&&mode==='lost'){
                mode='';await originalFetch(path,options);throw new TypeError('synthetic lost commit acknowledgement');
            }
            if(url.pathname.endsWith('/csv/commit')&&mode==='hold-commit'){
                const pending=originalFetch(path,options);mode='';await new Promise(resolve=>{releaseCommit=resolve;});return pending;
            }
            return originalFetch(path,options);
        };
        try{
            if(window.frameElement&&typeof popupFixtureHeight==='number') { window.frameElement.style.height=popupFixtureHeight+'px'; await sleep(15); }
            await wait(()=>module.exports.markdown&&!$('ai-model').disabled&&document.querySelector('.ai-answer table'),'initial assistant');
            assert(!document.querySelector('.ai-footnote')&&!document.querySelector('.ai-bottom .ai-file-tools'),'footer-disclaimer-and-file-toolbar-absent');
            assert(!$('ai-file-dialog').open&&$('ai-file-dialog').getBoundingClientRect().height===0,'no-unrequested-popup-or-layout-footprint');
            const bad=document.createElement('div');
            module.exports.markdown(bad,'[외부](https://example.invalid/) [변형](/assistant?panel=csv-import&owner=1) [경로](/assistant?panel=csv-import#run) [다른 범위](/api/ai/csv/export?scope=all) <img src=x onerror="window.__assistantPwned=1">');
            assert(!bad.querySelector('a,img,script')&&!window.__assistantPwned,'untrusted-workspace-urls-and-html-stay-text');
            assert(module.exports.fileWorkspaceTarget('/api/ai/csv/export?scope=my\n')===null&&module.exports.fileWorkspaceTarget('/assistant?panel=csv-import&owner=1')===null,'workspace-map-requires-literal-path-without-trailing-data');
            const links=response();
            const anchor=panel=>links.querySelector('a[data-ai-workspace="'+panel+'"]');
            const beforeOpen=requests().length;anchor('csv-import').focus();anchor('csv-import').click();
            assert($('ai-file-dialog').open&&$('ai-file-title').textContent==='CSV 가져오기'&&document.activeElement===$('ai-file-title'),'request-link-opens-labelled-focused-dialog');
            assert(requests().length===beforeOpen,'opening-dialog-does-not-upload-or-register');
            assert(!$('ai-csv-form').hidden&&$('ai-upload-form').hidden&&$('ai-csv-export').hidden,'only-requested-panel-is-visible');
            assert(anchor('csv-import').getAttribute('aria-haspopup')==='dialog'&&$('ai-file-dialog').getAttribute('aria-labelledby')==='ai-file-title','dialog-and-trigger-accessible-labels');
            file();const commitBefore=posts('commit').length;mode='hold';$('ai-csv-form').requestSubmit();
            await wait(()=>releasePreview&&$('ai-file-controls').disabled,'pending preview');
            const previewBefore=posts('preview').length;$('ai-csv-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
            assert(posts('preview').length===previewBefore&&posts('commit').length===commitBefore,'pending-preview-blocks-duplicate-submission-and-auto-commit');
            $('ai-file-close').click();assert(!$('ai-file-dialog').open&&document.activeElement===anchor('csv-import'),'close-restores-link-and-retains-pending-request');
            releasePreview();releasePreview=null;await wait(()=>!$('ai-csv-preview').hidden&&!$('ai-file-controls').disabled,'closed preview result');
            anchor('csv-import').click();
            assert(!$('ai-csv-preview').hidden&&!$('ai-csv-confirm').hidden&&posts('preview').length===previewBefore,'reopening-keeps-preview-without-reupload');
            assert($('ai-notice').hidden,'reopen-clears-its-own-outside-file-result-notice');
            assert($('ai-file-notice').textContent.includes('확인')&&$('ai-csv-preview').textContent.includes('비공개'),'preview-feedback-and-business-language-visible-in-popup');
            $('ai-csv-confirm').click();$('ai-csv-confirm').click();await wait(()=>$('ai-file-notice').textContent.includes('1개 장비가 등록되었습니다.'),'explicit commit');
            assert(posts('commit').length===commitBefore+1&&$('ai-csv-confirm').hidden,'explicit-confirm-once-consumes-preview');
            file();assert($('ai-csv-confirm').hidden&&$('ai-csv-preview').hidden,'file-change-invalidates-old-preview');
            mode='invalid';$('ai-csv-form').requestSubmit();await wait(()=>$('ai-file-notice').textContent.includes('3행'),'preview error');
            assert($('ai-csv-confirm').hidden&&!$('ai-file-controls').disabled,'preview-error-shown-without-confirm-and-user-can-retry');
            $('ai-csv-form').requestSubmit();await wait(()=>!$('ai-csv-confirm').hidden&&!$('ai-file-controls').disabled,'retry preview');
            mode='lost';const lostBefore=posts('commit').length;$('ai-csv-confirm').click();await wait(()=>$('ai-file-notice').textContent.includes('등록 결과를 확인하지 못했습니다.'),'ambiguous commit');
            assert(posts('commit').length===lostBefore+1&&$('ai-csv-confirm').hidden&&$('ai-file-notice').textContent.includes('자동으로 다시 등록하지 않습니다'),'lost-commit-ack-does-not-replay-and-keeps-reason');
            $('ai-file-dialog').dispatchEvent(new Event('cancel',{cancelable:true}));
            assert(!$('ai-file-dialog').open&&document.activeElement===anchor('csv-import'),'escape-cancel-event-closes-and-restores-focus');
            anchor('csv-export').click();
            assert($('ai-file-title').textContent==='CSV 내보내기'&&$('ai-csv-export-scope').textContent.includes('내 장비')&&$('ai-csv-download').getAttribute('href')==='/api/ai/csv/export?scope=my','my-csv-download-link-opens-scoped-popup');
            const exportBefore=requests().length;
            links.querySelector('a[data-ai-scope="public"]').click();
            assert($('ai-csv-export-scope').textContent.includes('공개 장비')&&$('ai-csv-download').getAttribute('href')==='/api/ai/csv/export?scope=public'&&requests().length===exportBefore,'public-export-keeps-exact-authorized-scope-without-write');
            $('ai-file-close').click();anchor('attachment').click();
            assert($('ai-file-title').textContent==='내 장비에 파일 첨부'&&!$('ai-upload-form').hidden&&$('ai-csv-form').hidden,'attachment-feature-preserved-in-own-popup');
            const attachment=new DataTransfer();attachment.items.add(new File(['synthetic PNG bytes'],'장비사진.png',{type:'image/png'}));$('ai-upload-file').files=attachment.files;$('ai-upload-equipment').value='7';
            $('ai-upload-form').requestSubmit();await wait(()=>$('ai-file-notice').textContent.includes('첨부되었습니다.'),'attachment result');
            assert(posts('files').length===1&&$('ai-upload-file').files.length===0,'attachment-uses-existing-endpoint-and-clears-selection');
            $('ai-file-close').click();anchor('csv-import').click();file();mode='hold';$('ai-csv-form').requestSubmit();await wait(()=>releasePreview,'stale preview pending');
            $('ai-file-close').click();
            await wait(()=>!$('ai-more-conversations').hidden,'older conversation control');$('ai-more-conversations').click();
            await wait(()=>document.querySelector('#ai-conversations [data-conversation-id="'+oldCid+'"]'),'older conversation loaded');
            document.querySelector('#ai-conversations [data-conversation-id="'+oldCid+'"]').click();await wait(()=>!$('ai-model').disabled&&$('ai-title').textContent==='이전 페이지 대화','conversation switched');
            releasePreview();releasePreview=null;await sleep(25);
            assert(!$('ai-file-dialog').open&&$('ai-csv-preview').hidden&&$('ai-csv-confirm').hidden&&$('ai-csv-file').files.length===0,'conversation-change-discards-files-token-popup-and-late-response');
            const switchedLinks=response();switchedLinks.querySelector('a[data-ai-workspace="csv-import"]').click();file();$('ai-csv-form').requestSubmit();await wait(()=>!$('ai-csv-confirm').hidden&&!$('ai-file-controls').disabled,'new-context preview');
            mode='hold-commit';const switchedCommitBefore=posts('commit').length;$('ai-csv-confirm').click();await wait(()=>releaseCommit,'pending commit');$('ai-file-close').click();
            document.querySelector('#ai-conversations [data-conversation-id="'+cid+'"]').click();await wait(()=>!$('ai-model').disabled&&document.querySelector('#ai-conversations [data-conversation-id="'+cid+'"][aria-current="true"]'),'switch while write pending');
            releaseCommit();releaseCommit=null;await wait(()=>$('ai-notice').textContent.includes('이전 대화에서 요청한 파일 작업: 1개 장비가 등록되었습니다.'),'same-account previous write outcome');
            assert(posts('commit').length===switchedCommitBefore+1&&!$('ai-file-dialog').open&&$('ai-csv-confirm').hidden,'conversation-switch-keeps-write-outcome-without-replay-or-preview-leak');
            assert(requests().every(x=>x.headers['X-CSRFToken']==='fixture-csrf'),'all-upload-preview-commit-writes-retain-csrf');
            const finalLinks=response();const finalPanel=innerWidth===320?'attachment':innerWidth===820?'csv-export':'csv-import';
            finalLinks.querySelector('a[data-ai-workspace="'+finalPanel+'"]').click();
            if(finalPanel==='csv-import'){file();mode='rows';$('ai-csv-form').requestSubmit();await wait(()=>!$('ai-csv-confirm').hidden&&!$('ai-file-controls').disabled,'final preview');}
            const box=$('ai-file-dialog').getBoundingClientRect();
            assert(box.width>0&&box.left>=0&&box.right<=innerWidth+1&&box.top>=0&&box.bottom<=innerHeight+1,'popup-contained-by-actual-viewport');
            assert(document.documentElement.scrollWidth<=innerWidth+1&&$('ai-file-dialog').scrollWidth<=$('ai-file-dialog').clientWidth+1,'no-page-or-popup-horizontal-overflow');
            assert($('ai-file-close').getBoundingClientRect().height>=44,'popup-close-touch-target');
            layout.popup={left:box.left,top:box.top,width:box.width,height:box.height,scrollHeight:$('ai-file-dialog').scrollHeight,clientHeight:$('ai-file-dialog').clientHeight,panel:finalPanel,viewportHeight:innerHeight};
            report.textContent=JSON.stringify({status:'pass',checks,width:innerWidth,theme,view:'requested-file-popup',layout,requests:server.requests.length,keyboard:'programmatic focus and cancel event; no native phone keyboard',production_data_used:false});
        }catch(error){report.textContent=JSON.stringify({status:'fail',checks,width:innerWidth,theme,view:'requested-file-popup',error:error.message,notice:$('ai-file-notice')?.textContent,layout,requests:server.requests.slice(-6)});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
})();
'''


def run_browser(project, assets, sizes=(320,390,820,1440), heights=None):
    """[Role] Reuses only the deterministic transport bootstrap and runs new popup checks at mobile/tablet/desktop widths."""
    baseline = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if baseline.count(anchor) != 1:
        raise ValueError('reviewed UI transport bootstrap anchor changed')
    bootstrap = baseline.split(anchor, 1)[0]
    if bootstrap.count('used_chars: 32000001') != 1 or bootstrap.count('above_base: true') != 1:
        raise ValueError('synthetic storage fixture anchor changed')
    bootstrap = bootstrap.replace('used_chars: 32000001','used_chars: 1234').replace('above_base: true','above_base: false')
    import json
    viewport = '    const popupFixtureHeight = (' + json.dumps(heights or {}) + ')[innerWidth];\n'
    script = bootstrap + viewport + SCRIPT
    return run_ui_browser(project, assets, script, sizes=sizes, themes=('light','dark'))


def run_short_browser(project, assets):
    """[Role] Verifies a normal phone and a reduced-height narrow viewport using the same actual dialog flow."""
    return run_browser(project,assets,sizes=(320,390),heights={320:620,390:844})
