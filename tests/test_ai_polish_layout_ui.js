/* [MINI-COMMENT: ASSISTANT.POLISH.BROWSER.DRIVER] [EN rev.1]
 * [Role] Measures actual staged DOM geometry and drives server-evidence status transitions without real AI work.
 * [Dependencies] The reviewed synthetic lifecycle transport, native details, shared menu renderer and private Linux Chromium fixture.
 * [Impact] Distinguishes live frame/TTL/race assertions from screenshots; programmatic focus/text enlargement is not claimed as physical touch/keyboard or browser zoom.
 */
function runAiPolishLayoutFixture(server,cid,modelId,jid,sleep,theme) {
    const originalFetch = server.fetch.bind(server);
    const statusRequests = [];
    let status = {state:'ready',mode:'normal',message:'연결의 최근 정상 응답을 확인했습니다.'};
    server.fetch = async (path, options = {}) => {
        const url = new URL(path, location.origin);
        if (url.pathname !== '/api/ai/status') return originalFetch(path, options);
        const snapshot = {...status};
        statusRequests.push({search:url.search,headers:options.headers,credentials:options.credentials,cache:options.cache,signal:options.signal});
        if (snapshot.hold) await snapshot.hold;
        if (snapshot.mode === 'network') throw new TypeError('synthetic status disconnect');
        if (snapshot.mode === 'http') return server.respond({success:false},503);
        const now = Date.now()/1000;
        return server.respond({success:true,state:snapshot.state,scope:url.searchParams.has('job_id')?'job':'selection',
            checked_at:snapshot.mode==='expired'?now-10:now,expires_at:snapshot.mode==='expired'?now-1:now+(snapshot.ttl||60),message:snapshot.message});
    };
    server.conversations.get(cid).title='내 장비 대화';
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},transitions=[],report=document.createElement('pre');
        report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),root=$('equipment-ai'),star=$('ai-header-status');
        const wait=async(test,label)=>{for(let index=0;index<1200;index++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const settle=async()=>{await sleep(100);void root.offsetHeight;await sleep(100);};
        const rect=node=>{const box=node.getBoundingClientRect();return Object.fromEntries(['left','right','top','bottom','width','height'].map(key=>[key,Math.round(box[key]*1000)/1000]));};
        const overlaps=(left,right)=>left.left<right.right-.5&&left.right>right.left+.5&&left.top<right.bottom-.5&&left.bottom>right.top+.5;
        const geometry=()=>({nav:rect(document.querySelector('.app-nav-row')),links:rect(document.querySelector('.app-nav-links')),heading:rect(document.querySelector('.app-nav-heading')),controls:rect(document.querySelector('.app-nav-controls')),
            actions:rect(root.querySelector('.ai-composer-actions')),level:rect($('ai-level')),send:rect($('ai-send')),group:rect(root.querySelector('.ai-inline-disclosures')),modelPanel:rect($('ai-model-panel')),reasoningPanel:rect($('ai-reasoning-panel')),
            composer:rect($('ai-form')),scroll:rect($('ai-scroll')),disclosureLayout:root.dataset.disclosureLayout,viewportFit:root.dataset.viewportFit,documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,width:innerWidth,height:innerHeight});
        let serial=0;
        const context=(jobId=null)=>window.dispatchEvent(new CustomEvent('assistant-status-context',{detail:{selectionId:modelId+String(++serial),jobId}}));
        const showStatus=async(state,mode='normal',jobId=null,extra={})=>{
            status={state,mode,message:{ready:'최근 정상 응답을 확인했습니다.',waiting_other:'다른 장비관리 요청의 처리를 기다리고 있습니다.',unavailable:'선택한 연결의 응답 불가를 확인했습니다.'}[state]||'최근 확인이 필요합니다.',...extra};
            const before=statusRequests.length;context(jobId);
            await wait(()=>statusRequests.length>before&&star.dataset.state===(mode==='expired'?'stale':['http','network'].includes(mode)?'checking':state),'status '+state+'/'+mode);
            transitions.push({requested:state,mode,displayed:star.dataset.state,scope:star.dataset.scope,color:getComputedStyle(star).color,label:star.getAttribute('aria-label')});
        };
        try {
            await wait(()=>!$('ai-model').disabled&&document.querySelector('.ai-answer table')&&root.dataset.viewportFit&&!$('ai-reasoning-support').hidden,'initial hydration');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();
            assert(star.isConnected&&star.textContent.trim()==='✦'&&!star.closest('.app-nav-title')&&star.getAttribute('role')==='img','star-survives-title-formatting-with-accessible-description');
            assert(!root.querySelector('.ai-sidebar-footer,.ai-status-dot')&&!root.textContent.includes('장비관리 전용 작업 도구')&&!root.textContent.includes('대화는 내 계정에 저장됩니다.'),'sidebar-footer-copy-decoration-and-space-removed');
            await showStatus('ready');const readyColor=getComputedStyle(star).color;
            await showStatus('waiting_other','normal',jid);const waitingColor=getComputedStyle(star).color;
            assert(star.dataset.scope==='job'&&star.getAttribute('aria-label').includes('진행 중인 요청')&&new URLSearchParams(statusRequests.at(-1).search).get('job_id')===jid,'active-job-status-precedes-next-selection-and-describes-own-queue');
            await showStatus('unavailable');const dangerColor=getComputedStyle(star).color;
            assert(new Set([readyColor,waitingColor,dangerColor]).size===3&&star.title===star.getAttribute('aria-label'),'ready-waiting-unavailable-have-distinct-colors-and-shared-tooltip-name');
            await showStatus('ready','expired');
            assert(![readyColor,dangerColor].includes(getComputedStyle(star).color),'expired-evidence-is-neutral-without-false-normal-or-failure');
            await showStatus('ready','http');await showStatus('ready','network');
            assert(star.dataset.state==='checking'&&getComputedStyle(star).color!==dangerColor,'http-and-network-failure-do-not-mark-provider-unavailable');
            await showStatus('ready','normal',null,{ttl:.15});await wait(()=>star.dataset.state==='stale','evidence expiry timer');
            assert(star.dataset.state==='stale','fresh-evidence-expires-without-waiting-for-next-poll');
            let release;const held=new Promise(resolve=>{release=resolve;});
            status={state:'unavailable',mode:'normal',message:'이전 연결 장애',hold:held};const oldCount=statusRequests.length;context();
            await wait(()=>statusRequests.length>oldCount,'held old context');const oldRequest=statusRequests.at(-1);
            await showStatus('ready','normal',jid);release();await sleep(50);
            assert(oldRequest.signal.aborted&&star.dataset.state==='ready'&&star.dataset.scope==='job'&&!star.title.includes('이전 연결 장애'),'context-switch-aborts-and-rejects-late-old-status');
            await showStatus('ready','normal',null,{message:'<img src=x onerror="window.__statusPwned=1">'});
            assert(star.title.includes('<img')&&!star.querySelector('img')&&!window.__statusPwned,'status-message-is-text-only');
            const delays=[],nativeTimeout=window.setTimeout,priorHidden=Object.getOwnPropertyDescriptor(document,'hidden');
            window.setTimeout=function(callback,delay,...args){delays.push(delay);return nativeTimeout.call(window,callback,delay,...args);};
            Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));await sleep(20);
            assert(delays.includes(15000),'hidden-tab-status-polling-uses-reduced-frequency');
            Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));await sleep(50);
            assert(delays.includes(2500),'visible-tab-status-polling-resumes-normal-frequency');
            window.setTimeout=nativeTimeout;if(priorHidden)Object.defineProperty(document,'hidden',priorHidden);else delete document.hidden;
            assert(statusRequests.every(item=>item.headers['X-Assistant-Poll']==='1'&&item.credentials==='same-origin'&&item.cache==='no-store'),'all-status-requests-are-passive-authenticated-and-uncached');

            const trash=$('ai-trash-current'),rowTrash=root.querySelector('.ai-conversation-action.ai-trash-action');
            assert(trash.title==='휴지통으로 이동'&&trash.getAttribute('aria-label')==='휴지통으로 이동'&&rowTrash&&rowTrash.title==='휴지통으로 이동'&&rowTrash.getAttribute('aria-label').includes('내 장비 대화'),'current-and-history-trash-controls-have-safe-targeted-tooltips');
            assert(getComputedStyle(trash).color===dangerColor&&getComputedStyle(rowTrash).color===dangerColor&&getComputedStyle(trash).borderTopColor===dangerColor&&getComputedStyle(trash,'::before').maskImage!=='none','trash-outline-and-monochrome-symbol-share-header-danger-token');
            const openSidebar=getComputedStyle($('ai-sidebar')).display==='none';
            if(openSidebar){$('ai-menu-toggle').click();await settle();}
            layout.trashTargets={current:rect(trash),history:rect(rowTrash),sidebar:rect($('ai-sidebar')),sidebarDisplay:getComputedStyle($('ai-sidebar')).display};
            assert(rect(trash).height>=40&&rect(rowTrash).height>=36,'trash-targets-retain-touch-and-focus-space');trash.focus();assert(document.activeElement===trash,'trash-control-retains-programmatic-keyboard-focus');
            if(openSidebar){$('ai-menu-toggle').click();await settle();}

            const model=$('ai-model-settings'),support=$('ai-reasoning-support'),summaries=[model.querySelector('summary'),support.querySelector('summary')];
            assert(!model.open&&!support.open&&model.contains($('ai-model'))&&model.contains($('ai-model-refresh')),'both-native-disclosures-default-closed-and-retain-existing-controls');
            layout.collapsed=geometry();
            const checkPlacement=name=>{
                const current=geometry(),summaryRects=summaries.map(rect);
                if(current.disclosureLayout==='stacked') assert(current.group.left>=current.level.right-1&&current.group.right<=current.send.left+1&&summaryRects.at(-1).bottom<=current.actions.bottom+1&&!overlaps(summaryRects[0],summaryRects[1]),name+'-summaries-fit-two-lines-right-of-reasoning');
                else assert(current.group.top>=Math.max(current.level.bottom,current.send.bottom)-1&&!overlaps(current.group,current.level)&&!overlaps(current.group,current.send),name+'-insufficient-space-uses-measured-next-row-fallback');
            };
            checkPlacement('collapsed');
            const answer=document.querySelector('.ai-answer'),extra=document.createElement('p');extra.textContent='읽는 위치와 초안 보존 확인용 문장입니다. '.repeat(350);answer.append(extra);
            $('ai-input').value='화면 조절 중 보존할 초안';$('ai-scroll').scrollTop=70;
            const before={model:$('ai-model').value,level:$('ai-level').value,scroll:$('ai-scroll').scrollTop,reads:server.requests.filter(item=>item.path==='/api/ai/models').length,posts:server.requests.filter(item=>item.method==='POST').length};
            summaries[0].click();await settle();summaries[1].click();await settle();layout.expanded=geometry();
            assert(model.open&&support.open&&$('ai-model').checkVisibility()&&$('ai-reasoning-reasons').checkVisibility(),'disclosures-open-independently-with-native-summary-click');
            assert(layout.expanded.modelPanel.top>=layout.expanded.actions.bottom&&layout.expanded.reasoningPanel.top>=layout.expanded.modelPanel.bottom&&layout.expanded.modelPanel.left>=layout.expanded.actions.left-1&&layout.expanded.modelPanel.right<=layout.expanded.actions.right+1,'expanded-bodies-reserve-separate-full-width-nonoverlapping-space');
            assert(layout.expanded.composer.height>layout.collapsed.composer.height+30&&rect(root.querySelector('.ai-disclosure-spacer')).bottom>=layout.expanded.reasoningPanel.bottom,'measured-spacer-contains-both-open-bodies');
            assert(!model.contains($('ai-model-status'))&&$('ai-model-status').getAttribute('role')==='status','model-errors-remain-outside-collapsible-panels');
            summaries[0].click();await settle();assert(!model.open&&support.open,'closing-model-does-not-close-reasoning-support');summaries[1].click();await settle();
            assert($('ai-model').value===before.model&&$('ai-level').value===before.level&&$('ai-input').value==='화면 조절 중 보존할 초안'&&Math.abs($('ai-scroll').scrollTop-before.scroll)<=1&&document.contains(answer),'disclosure-toggle-preserves-model-reasoning-draft-reader-and-message-nodes');
            assert(server.requests.filter(item=>item.path==='/api/ai/models').length===before.reads&&server.requests.filter(item=>item.method==='POST').length===before.posts,'native-toggle-does-not-refresh-models-or-submit-data');
            for(const item of [model,support])item.style.fontSize='22px';await settle();
            assert(root.dataset.disclosureLayout==='flow','two-enlarged-summaries-use-height-based-fallback');checkPlacement('font-enlarged');
            for(const item of [model,support])item.style.removeProperty('font-size');await settle();

            const nav=document.querySelector('.app-nav-polish'),longName='아주 긴 메뉴 이름과 전체 안내를 확인하는 화면 이동';
            for(const id of ['main-menu-link','smart-back-btn','parent-menu-link']){const node=$(id);node.querySelector('span').textContent=longName;node.title=longName;node.setAttribute('aria-label',longName);}
            const user=nav.querySelector('.app-nav-user'),nickname='매우 긴 계정 이름과 소속 부서 표시';user.querySelector('.app-nav-nickname').textContent=nickname;user.title=nickname+' · 내 정보로 이동';user.setAttribute('aria-label',user.title);await settle();
            const checkNav=name=>{
                const current=geometry(),tools=rect(nav.querySelector('.app-nav-tools')),account=rect(nav.querySelector('.app-nav-account')),main=rect($('main-menu-link')),history=rect(nav.querySelector('.app-nav-history'));
                assert(current.links.right<=current.heading.left+1&&current.heading.right<=current.controls.left+1&&!overlaps(tools,account)&&tools.bottom<=account.top+1,name+'-left-center-right-and-two-control-rows-do-not-overlap');
                assert(Math.abs(main.top+main.height/2-history.top-history.height/2)<=1&&rect($('smart-back-btn')).bottom<=rect($('parent-menu-link')).top+1,name+'-main-stays-centered-beside-two-history-rows');
                assert(['main-menu-link','smart-back-btn','parent-menu-link'].every(id=>{const node=$(id),label=node.querySelector('span'),style=getComputedStyle(label);return style.webkitLineClamp==='2'&&label.clientHeight<=parseFloat(style.lineHeight)*2+1&&node.title===longName&&node.getAttribute('aria-label')===longName;}),name+'-long-menu-labels-clamp-at-two-lines-and-retain-full-names');
                assert(document.documentElement.scrollWidth<=innerWidth+1&&current.controls.right<=innerWidth+1,name+'-navigation-stays-within-viewport');
            };
            checkNav('long-labels');layout.longNavigation=geometry();
            const enlarged=Array.from(nav.querySelectorAll('.app-nav-link,.app-nav-control,.app-nav-role,.app-nav-title')).map(node=>({node,font:parseFloat(getComputedStyle(node).fontSize),inline:node.style.fontSize}));
            for(const item of enlarged)item.node.style.fontSize=item.font*2+'px';await settle();checkNav('font-enlarged');layout.enlargedNavigation=geometry();
            for(const item of enlarged)item.node.style.fontSize=item.inline;await settle();
            window.frameElement.style.height='620px';await settle();
            assert(root.dataset.viewportFit==='minimum'&&$('ai-scroll').clientHeight>=119&&document.documentElement.scrollWidth<=innerWidth+1,'short-height-retains-minimum-chat-space-and-page-scroll-fallback');
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';await settle();

            $('ai-trash-tab').click();await wait(()=>$('ai-trash-tab').getAttribute('aria-pressed')==='true'&&!$('ai-trash-help').hidden&&root.querySelector('.ai-trash-select'),'trash list');await settle();
            assert($('ai-trash-help').textContent==='휴지통으로 보낸 시각부터 30일 내에 복구 가능합니다.'&&getComputedStyle($('ai-history-title')).position==='absolute'&&$('ai-conversations').getAttribute('aria-label')==='휴지통 대화 목록','trash-shows-only-requested-guidance-and-keeps-accessible-list-name');
            const menuContainer=document.createElement('div');menuContainer.hidden=true;document.body.append(menuContainer);
            const menuCases=[['equipment','admin_center','my_approvals','assistant','future'],['future','equipment'],['admin_center'],[]];
            for(const codes of menuCases){const menus=codes.map(code=>({MenuCode:code,MenuName:code,Description:'합성 메뉴',Url:'/fixture/'+code})),copy=menus.slice(),ordered=window.MenuCards.orderPortal(menus);window.MenuCards.render(menuContainer,ordered);
                const actual=Array.from(menuContainer.querySelectorAll('a'),node=>new URL(node.href).pathname.split('/').at(-1)),expected=codes.filter(code=>code!=='admin_center').concat(codes.filter(code=>code==='admin_center'));
                assert(JSON.stringify(actual)===JSON.stringify(expected)&&menus.every((menu,index)=>menu===copy[index]),'portal-dom-admin-last-stable-permitted-case-'+menuCases.indexOf(codes));}
            menuContainer.remove();
            const open=theme==='dark'||innerWidth===390;model.open=open;support.open=open;await settle();
            if(innerWidth===320)$('ai-menu-toggle').click();
            await showStatus(innerWidth===820?'waiting_other':innerWidth===1440&&theme==='dark'?'unavailable':'ready','normal',innerWidth===820?jid:null);
            layout.final=geometry();
            assert(document.documentElement.scrollWidth<=innerWidth+1&&layout.final.scroll.height>=119,'final-view-has-no-horizontal-overflow-and-retains-chat-minimum');
            report.textContent=JSON.stringify({status:'pass',view:'ai-polish',checks,width:innerWidth,theme,layout,transitions,statusRequests:statusRequests.length,production_data_used:false,interaction:'real animation frames; native summary click/programmatic focus and synthetic text enlargement; physical keyboard/touch/browser zoom not exercised'});
        } catch(error) {
            report.textContent=JSON.stringify({status:'fail',view:'ai-polish',checks,width:innerWidth,theme,error:error.message,layout,transitions,geometry:geometry()});
        }
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}
