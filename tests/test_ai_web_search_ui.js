/* [MINI-COMMENT: ASSISTANT.WEB.UI.TEST] [EN rev.2]
 * [Role] Exercises real opt-in controls, streaming citations, immutable source links and responsive layout with inert transport.
 * [Dependencies] Existing candidate DOM and synthetic history/model route behavior; native real-frame screenshots.
 * [Impact] No real query or business write is issued; hostile page text stays inert and conversation changes reset internet permission.
 */
function runAiWebSearchFixture(server,cid,oldCid,modelId,jid,sleep,theme) {
    const original=server.fetch.bind(server),queries=[];
    const searches=[{query:'Flask official documentation',engine:'Yahoo',searched_at:'2026-11-05T08:00:00Z',status:'ok',results:[
        {number:1,title:'Flask 공식 문서 <img src=x onerror="window.__webPwned=1">',url:'https://flask.palletsprojects.com/en/stable/',snippet:'검색 요약은 비신뢰 자료입니다. <script>window.__webPwned=1</script>'},
        {number:2,title:'차단해야 할 링크',url:'javascript:alert(1)',snippet:'실행 금지'},
        {number:3,title:'내부 주소',url:'https://192.168.0.2',snippet:'클릭 금지'}]}];
    server.fetch=async(path,options={})=>{
        const url=new URL(path,location.origin),result=await original(path,options),body=await result.json();
        if(url.pathname==='/api/ai/capabilities')body.web_search={available:true,default:false,engine:'Yahoo'};
        if(url.pathname==='/api/ai/jobs/'+jid){queries.push(url.search);body.web_search_version=1;body.web_searches=url.searchParams.get('w')==='1'?null:searches;}
        if(url.pathname.endsWith('/messages')&&server.sent){body.jobs=body.jobs.map(job=>({...job,state:server.polls>=3?'done':'queued',web_search_version:1,web_searches:searches}));}
        return server.respond(body,result.status);
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},report=document.createElement('pre');report.id='browser-test-result';report.hidden=true;document.body.append(report);
        const $=id=>document.getElementById(id),wait=async(test,label)=>{for(let i=0;i<1200;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const rect=node=>{const b=node.getBoundingClientRect();return Object.fromEntries(['left','right','top','bottom','width','height'].map(key=>[key,Math.round(b[key]*100)/100]));};
        const geometry=()=>({width:innerWidth,height:innerHeight,pageWidth:document.documentElement.scrollWidth,pageHeight:document.documentElement.scrollHeight,
            root:rect($('equipment-ai')),toggle:rect($('ai-web-search')),send:rect($('ai-send')),form:rect($('ai-form')),chat:rect($('ai-scroll')),fit:$('equipment-ai').dataset.viewportFit});
        try{
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';
            await wait(()=>$('ai-conversations').querySelector('.ai-conversation'),'history');
            $('ai-conversations').querySelector('.ai-conversation').click();
            await wait(()=>!$('ai-send').disabled&&!$('ai-web-search').hidden,'controls');
            const toggle=$('ai-web-search');assert(toggle.getAttribute('aria-pressed')==='false'&&!toggle.disabled,'internet-default-off');
            assert(toggle.title.includes('외부 Yahoo')&&toggle.getAttribute('aria-describedby')==='ai-web-search-help','external-query-disclosure-accessible');
            toggle.click();assert(toggle.getAttribute('aria-pressed')==='true','explicit-user-opt-in');
            $('ai-input').value='Flask 공식 문서의 주요 내용을 웹 검색으로 확인해 주세요.';$('ai-input').dispatchEvent(new Event('input',{bubbles:true}));
            $('ai-form').requestSubmit();await wait(()=>server.sent===1,'accepted opted turn');
            assert(server.requests.find(item=>item.path.endsWith('/turns')).data.web_search===true,'opt-in-sent-with-turn');
            await wait(()=>document.querySelector('.ai-web-sources'),'actual-source-render');
            let source=document.querySelector('.ai-web-sources');assert(!source.open,'sources-default-collapsed');source.open=true;
            const stable=source.querySelector('a');stable.focus();await wait(()=>queries.length>=2,'citation acknowledgement poll');await sleep(50);
            assert(source===document.querySelector('.ai-web-sources')&&source.open&&document.activeElement===stable,'poll-ack-preserves-source-open-state-and-focus');
            assert(queries.some(q=>new URLSearchParams(q).get('w')==='1'),'source-version-ack-avoids-repeated-evidence');
            assert(source.querySelectorAll('a').length===1,'unsafe-protocol-and-private-IP-links-rejected');
            assert(getComputedStyle(source.querySelector('ol')).listStyleType==='decimal','citation-numbers-survive-common-list-reset');
            assert(stable.target==='_blank'&&stable.rel.includes('noopener')&&stable.rel.includes('noreferrer')&&stable.referrerPolicy==='no-referrer','external-link-isolated-no-referrer');
            assert(source.textContent.includes('<img')&&source.textContent.includes('<script>')&&!source.querySelector('img,script')&&!window.__webPwned,'hostile-result-text-does-not-execute');
            await wait(()=>server.polls>=3&&!$('ai-send').disabled,'completed stream');
            assert(source===document.querySelector('.ai-web-sources')&&source.open,'answer-completion-preserves-citations');
            $('ai-model-settings').open=true;const model=$('ai-model');model.value='f'.repeat(32);model.dispatchEvent(new Event('change',{bubbles:true}));
            await wait(()=>toggle.disabled&&!model.disabled&&server.conversations.get(cid).selection_id==='f'.repeat(32),'chat-only model disable');assert(source.isConnected&&source.open,'model-switch-keeps-current-citations');
            model.value=modelId;model.dispatchEvent(new Event('change',{bubbles:true}));await wait(()=>!toggle.disabled,'tool-model restored');$('ai-model-settings').open=false;
            const current=[...$('ai-conversations').querySelectorAll('.ai-conversation')].find(n=>n.dataset.conversationId===cid);current.click();
            await wait(()=>toggle.getAttribute('aria-pressed')==='false'&&document.querySelector('.ai-web-sources'),'reloaded history');
            source=document.querySelector('.ai-web-sources');assert(source.querySelector('a').href===stable.href,'reload-restores-authoritative-sources');
            assert(toggle.getAttribute('aria-pressed')==='false','history-reopen-resets-consent');source.open=true;
            await sleep(200);layout.expanded=geometry();
            assert(document.documentElement.scrollWidth<=innerWidth+1,'no-horizontal-page-overflow');
            assert(layout.expanded.pageHeight<=innerHeight+1||layout.expanded.fit==='minimum','page-fits-or-declared-minimum-fallback');
            assert(layout.expanded.toggle.left>=0&&layout.expanded.toggle.right<=innerWidth+1&&layout.expanded.send.right<=innerWidth+1,'compact-controls-remain-in-viewport');
            assert(Math.abs(layout.expanded.toggle.height-layout.expanded.send.height)<=1,'search-and-send-control-heights-match');
            assert($('ai-scroll').clientHeight>=119,'chat-preserves-measured-minimum');
            assert(server.requests.filter(x=>x.method==='POST').every(x=>/\/(turns|selection)$/.test(x.path)),'no-business-or-lifecycle-mutations');
            $('ai-scroll').scrollTop=$('ai-scroll').scrollHeight;window.scrollTo(0,0);
            report.textContent=JSON.stringify({status:'pass',view:'web-search',width:innerWidth,theme,checks,layout,queryPolls:queries.length,production_data_used:false});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'web-search',width:innerWidth,theme,checks,error:error.message,layout,geometry:geometry()});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}
