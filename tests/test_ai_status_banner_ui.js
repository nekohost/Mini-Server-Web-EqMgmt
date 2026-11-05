/* [MINI-COMMENT: ASSISTANT.STATUS.BANNER.DRIVER] [EN rev.2]
 * [Role] Checks atomic header/banner state, one existing poll path and responsive space above the actual composer.
 * [Dependencies] Synthetic local status replies, native details and real animation-frame capture; current app features remain live.
 * [Impact] Distinguishes safe response-unavailable guidance from a server-down claim and records shared TTL/races, complete 500-character reasons, border-box chat minimums and reachable enlarged inputs without dropping warning text.
 */
function runAiStatusBannerFixture(server,cid,modelId,jid,sleep,theme) {
    const originalFetch=server.fetch.bind(server),requests=[];
    let status={state:'ready',message:'선택한 연결의 최근 정상 응답을 확인했습니다.'};
    server.fetch=async(path,options={})=>{
        const url=new URL(path,location.origin);
        if(url.pathname!=='/api/ai/status')return originalFetch(path,options);
        const current={...status};requests.push({search:url.search,headers:options.headers,cache:options.cache,credentials:options.credentials,signal:options.signal});
        if(current.hold)await current.hold;
        if(current.mode==='network')throw new TypeError('synthetic status disconnect');
        if(current.mode==='http')return server.respond({success:false},503);
        const now=Date.now()/1000;
        return server.respond({success:true,state:current.state,scope:url.searchParams.has('job_id')?'job':'selection',checked_at:current.mode==='expired'?now-10:now,
            expires_at:current.mode==='expired'?now-1:now+(current.ttl||60),message:current.message});
    };
    server.conversations.get(cid).title='상태 안내 확인 대화';
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},transitions=[],inconsistencies=[],report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),root=$('equipment-ai'),star=$('ai-header-status'),banner=$('ai-connection-status'),mark=$('ai-connection-status-mark');
        const summary=$('ai-connection-status-summary'),reason=$('ai-connection-status-reason');
        const wait=async(test,label)=>{for(let index=0;index<1200;index++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const settle=async()=>{await sleep(100);void root.offsetHeight;await sleep(100);await wait(()=>$('ai-scroll').clientHeight>=119,'measured chat space after layout');};
        const rect=node=>{if(!node)return null;const box=node.getBoundingClientRect();return Object.fromEntries(['left','right','top','bottom','width','height'].map(key=>[key,Math.round(box[key]*1000)/1000]));};
        const geometry=()=>({banner:rect(banner),form:rect($('ai-form')),input:rect($('ai-input')),send:rect($('ai-send')),scroll:rect($('ai-scroll')),root:rect(root),
            state:star?.dataset.state,scope:star?.dataset.scope,hidden:banner?.hidden,summary:summary?.textContent,reason:reason?.textContent,headerColor:star?getComputedStyle(star).color:null,
            bannerColor:mark?getComputedStyle(mark).color:null,viewportFit:root?.dataset.viewportFit,viewportMinimum:root?.dataset.viewportMinimum,chatClientHeight:$('ai-scroll')?.clientHeight,
            reasonBox:rect(reason),reasonTextLength:reason?.textContent.length,reasonClientHeight:reason?.clientHeight,reasonScrollHeight:reason?.scrollHeight,
            bottomClientHeight:root?.querySelector('.ai-bottom')?.clientHeight,bottomScrollHeight:root?.querySelector('.ai-bottom')?.scrollHeight,
            documentWidth:document.documentElement.scrollWidth,width:innerWidth,height:innerHeight});
        let serial=0,lastContext=null,observer=null;
        const emit=(jobId=null)=>{lastContext={selectionId:++serial%2?'f'.repeat(32):modelId,jobId};window.dispatchEvent(new CustomEvent('assistant-status-context',{detail:lastContext}));};
        const snapshot=()=>({header:star.dataset.state,banner:banner.dataset.state,mark:mark.dataset.state,headerScope:star.dataset.scope,bannerScope:banner.dataset.scope,
            headerChecked:star.dataset.checkedAt||'',bannerChecked:banner.dataset.checkedAt||'',headerExpires:star.dataset.expiresAt||'',bannerExpires:banner.dataset.expiresAt||'',hidden:banner.hidden});
        const consistent=()=>{
            const value=snapshot(),visible=['waiting_other','unavailable'].includes(value.header);
            return value.header===value.banner&&value.header===value.mark&&value.headerScope===value.bannerScope&&value.headerChecked===value.bannerChecked&&value.headerExpires===value.bannerExpires&&value.hidden===!visible;
        };
        const show=async(state,{jobId=null,mode='normal',...extra}={})=>{
            status={state,mode,message:state==='waiting_other'?'장비관리 내부 큐의 선행 요청을 처리하고 있습니다.':state==='unavailable'?'선택한 연결의 접속 시간 초과를 확인했습니다.':'선택한 연결의 최근 상태를 확인했습니다.',...extra};
            const before=requests.length;emit(jobId);
            const expected=mode==='expired'?'stale':['http','network'].includes(mode)?'checking':state;
            await wait(()=>requests.length>before&&star.dataset.state===expected&&consistent(),'state '+expected);
            await sleep(20);
            assert(requests.length===before+1,'one-status-request-for-context-'+serial);
            assert(getComputedStyle(star).color===getComputedStyle(mark).color,'same-semantic-star-color-'+serial);
            transitions.push({...snapshot(),message:reason.textContent,color:getComputedStyle(mark).color});
        };
        const checkGeometry=name=>{
            const value=layout[name]=geometry();
            assert(!banner.hidden&&value.banner.bottom<=value.form.top+1&&value.form.top<=value.input.top&&value.banner.left>=value.root.left-1&&value.banner.right<=value.root.right+1,name+'-banner-is-in-flow-directly-above-input');
            assert(value.scroll.height>=119&&value.send.right<=value.root.right+1&&value.documentWidth<=innerWidth+1,name+'-chat-minimum-and-horizontal-bounds-preserved');
        };
        try{
            await wait(()=>banner&&mark&&summary&&reason&&!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&root.dataset.viewportFit,'hydrated status DOM');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            assert($('ai-form').previousElementSibling===banner&&banner.getAttribute('role')==='status'&&banner.getAttribute('aria-live')==='polite'&&banner.getAttribute('aria-atomic')==='true'&&($('ai-input').getAttribute('aria-describedby')||'').split(/\s+/).includes(banner.id),'input-adjacent-live-region-is-associated-and-atomic');
            observer=new MutationObserver(()=>{if(!consistent())inconsistencies.push(snapshot());});
            for(const node of [star,banner,mark])observer.observe(node,{attributes:true,attributeFilter:['data-state','data-scope','data-checked-at','data-expires-at','hidden']});
            $('ai-notice').textContent='이미 표시된 오류 안내는 유지됩니다.';$('ai-notice').hidden=false;
            const stable={model:$('ai-model').value,level:$('ai-level').value,draft:'상태 안내 중 보존할 초안'};$('ai-input').value=stable.draft;
            const extra=document.createElement('p');extra.textContent='기존 대화와 읽는 위치를 보존합니다. '.repeat(350);document.querySelector('.ai-answer').append(extra);$('ai-scroll').scrollTop=70;stable.top=$('ai-scroll').scrollTop;
            await show('ready');assert(banner.hidden&&!summary.textContent&&!reason.textContent,'ready-does-not-leave-a-warning');
            await show('waiting_other',{jobId:jid});await settle();
            assert(summary.textContent==='다른 세션/사용자의 요청 처리 중'&&reason.textContent.includes('진행 중인 요청')&&reason.textContent.includes(status.message),'waiting-guidance-uses-job-scope-and-confirmed-reason');
            checkGeometry('waiting');
            await show('unavailable');await settle();
            assert(summary.textContent==='AI 서버의 응답을 받지 못하고 있습니다.'&&reason.textContent.includes('다음 요청 연결')&&reason.textContent.includes(status.message)&&!summary.textContent.includes('다운'),'unavailable-explains-response-failure-without-server-down-claim');
            checkGeometry('unavailable');
            let textChanges=0;const textObserver=new MutationObserver(records=>{textChanges+=records.length;});textObserver.observe(banner,{subtree:true,childList:true,characterData:true});
            const beforeRefresh=requests.length;document.dispatchEvent(new Event('visibilitychange'));
            await wait(()=>requests.length===beforeRefresh+1,'same-evidence refresh');await sleep(50);textObserver.disconnect();
            assert(textChanges===0&&summary.textContent==='AI 서버의 응답을 받지 못하고 있습니다.','identical-poll-does-not-rewrite-live-text');
            const duplicateCount=requests.length;window.dispatchEvent(new CustomEvent('assistant-status-context',{detail:lastContext}));await sleep(40);
            assert(requests.length===duplicateCount,'duplicate-context-does-not-add-a-banner-poll');
            await show('unavailable',{ttl:.3});await wait(()=>star.dataset.state==='stale'&&banner.hidden&&consistent(),'shared TTL expiry');
            assert(!summary.textContent&&!reason.textContent,'shared-ttl-expiry-removes-old-red-text');
            await show('unavailable',{mode:'expired'});assert(banner.hidden,'already-expired-red-evidence-is-hidden');
            await show('waiting_other');await show('ready',{mode:'http'});assert(banner.hidden,'http-failure-removes-old-waiting-guidance');
            await show('unavailable');await show('ready',{mode:'network'});assert(banner.hidden,'network-failure-removes-old-red-guidance');
            let release;status={state:'unavailable',message:' 이전 연결의 늦은 장애 응답',hold:new Promise(resolve=>{release=resolve;})};const beforeHeld=requests.length;emit(jid);
            assert(star.dataset.state==='checking'&&banner.hidden&&consistent(),'context-change-clears-old-warning-synchronously');
            await wait(()=>requests.length>beforeHeld,'held old context');const oldRequest=requests.at(-1);
            await show('ready');release();await sleep(40);
            assert(oldRequest.signal.aborted&&banner.hidden&&star.dataset.state==='ready'&&!reason.textContent.includes('이전 연결'),'late-old-context-cannot-restore-red-banner');
            await show('unavailable',{message:'<img src=x onerror="window.__bannerPwned=1"> 연결 사유'});
            assert(reason.textContent.includes('<img')&&!banner.querySelector('img,script')&&!window.__bannerPwned,'server-reason-is-safe-text');
            await show('waiting_other',{jobId:jid});$('ai-model-settings').open=true;$('ai-reasoning-support').open=true;await settle();checkGeometry('expandedPanels');
            const longReason='연결을 확인한 사유를 안내합니다. 다음 요청 연결과 장비관리 내부 상태만 확인했습니다. '.repeat(12).slice(0,500);
            await show('unavailable',{message:longReason});await settle();
            assert(longReason.length===500&&reason.textContent.endsWith(longReason)&&reason.scrollHeight<=reason.clientHeight+1,'all-500-reason-characters-remain-present-and-unclipped');
            checkGeometry('longReason');
            const copy=root.querySelector('.ai-connection-status-copy'),saved={copy:copy.style.fontSize,reason:reason.style.fontSize,mark:mark.style.fontSize};
            copy.style.fontSize='24px';reason.style.fontSize='22px';mark.style.fontSize='46px';await settle();checkGeometry('enlargedText');
            window.frameElement.style.height='620px';await settle();checkGeometry('shortEnlarged');
            assert(root.dataset.viewportFit==='minimum','short-enlarged-status-uses-page-scroll-fallback');
            assert(reason.textContent.endsWith(longReason)&&reason.scrollHeight<=reason.clientHeight+1,'enlarged-long-reason-remains-complete-and-readable-by-native-scroll');
            $('ai-input').scrollIntoView({block:'center'});await sleep(30);const input=rect($('ai-input'));
            assert(input.top>=-1&&input.bottom<=innerHeight+1,'input-remains-reachable-under-tall-guidance');
            copy.style.fontSize=saved.copy;reason.style.fontSize=saved.reason;mark.style.fontSize=saved.mark;
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            assert($('ai-model').value===stable.model&&$('ai-level').value===stable.level&&$('ai-input').value===stable.draft,'banner-transitions-preserve-model-reasoning-and-draft');
            assert($('ai-notice').textContent==='이미 표시된 오류 안내는 유지됩니다.'&&!$('ai-notice').hidden,'existing-error-notice-remains-independent');
            assert(requests.every(item=>item.headers['X-Assistant-Poll']==='1'&&item.cache==='no-store'&&item.credentials==='same-origin'),'banner-reuses-only-existing-passive-status-transport');
            await show(theme==='dark'?'unavailable':'waiting_other',{jobId:theme==='dark'?null:jid});await settle();checkGeometry('final');
            await sleep(0);assert(inconsistencies.length===0,'all-observed-header-banner-updates-are-atomic');
            $('ai-scroll').scrollTop=0;window.scrollTo(0,0);
            report.textContent=JSON.stringify({status:'pass',view:'input-status-banner',checks,width:innerWidth,theme,layout,transitions,statusRequests:requests.length,inconsistencies,production_data_used:false,interaction:'real frames and programmatic focus/text enlargement; no physical keyboard/touch or browser zoom'});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'input-status-banner',checks,width:innerWidth,theme,error:error.message,layout,transitions,inconsistencies,geometry:geometry()});}
        finally{observer?.disconnect();}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}
