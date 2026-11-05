/* [MINI-COMMENT: ASSISTANT.WEB.UI.TEST] [EN rev.3]
 * [Role] Exercises real opt-in controls, streaming citations, immutable source links and responsive layout with inert transport.
 * [Dependencies] Existing candidate DOM and synthetic history/model route behavior; native real-frame screenshots.
 * [Impact] No real query or business write is issued; hostile page text stays inert and conversation changes reset internet permission.
 */
function runAiWebSearchFixture(server,cid,oldCid,modelId,jid,sleep,theme) {
    const original=server.fetch.bind(server),queries=[];
    const searches=[{query:'Flask official documentation',engine:'Yahoo',searched_at:'2026-11-05T08:00:00Z',status:'ok',results:[
        {number:1,title:'Flask 공식 문서 <img src=x onerror="window.__webPwned=1">',url:'https://flask.palletsprojects.com/en/stable/',snippet:'검색 요약은 비신뢰 자료입니다. <script>window.__webPwned=1</script>'},
        {number:2,title:'차단해야 할 링크',url:'javascript:alert(1)',snippet:'실행 금지'},
        {number:3,title:'내부 주소',url:'https://192.168.0.2',snippet:'클릭 금지'}]},
        {query:'repo:pallets/flask issue',engine:'GitHub',scope:'issues',status:'partial',searched_at:'2026-11-05T08:00:00Z',results:[{number:1,title:'공개 이슈 근거',url:'https://github.com/pallets/flask/issues/1',snippet:'공개 이슈 요약'}]}];
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
            root:rect($('equipment-ai')),send:rect($('ai-send')),form:rect($('ai-form')),chat:rect($('ai-scroll')),fit:$('equipment-ai').dataset.viewportFit});
        try{
            window.frameElement.style.height=(innerWidth<=760?844:900)+'px';
            await wait(()=>$('ai-conversations').querySelector('.ai-conversation'),'history');
            $('ai-conversations').querySelector('.ai-conversation').click();
            await wait(()=>!$('ai-send').disabled,'controls');
            assert(!$('ai-web-search')&&!$('ai-web-search-help'),'automatic-search-removes-toggle-and-obsolete-help');
            $('ai-input').value='Flask 공식 문서의 주요 내용을 웹 검색으로 확인해 주세요.';$('ai-input').dispatchEvent(new Event('input',{bubbles:true}));
            $('ai-form').requestSubmit();await wait(()=>server.sent===1,'accepted opted turn');
            assert(!Object.hasOwn(server.requests.find(item=>item.path.endsWith('/turns')).data,'web_search'),'new-turn-delegates-search-decision-to-server-auto-mode');
            await wait(()=>document.querySelector('.ai-web-sources'),'actual-source-render');
            let source=document.querySelector('.ai-web-sources');assert(!source.open,'sources-default-collapsed');source.open=true;
            const stable=source.querySelector('a');stable.focus();await wait(()=>queries.length>=2,'citation acknowledgement poll');await sleep(50);
            assert(source===document.querySelector('.ai-web-sources')&&source.open&&document.activeElement===stable,'poll-ack-preserves-source-open-state-and-focus');
            assert(queries.some(q=>new URLSearchParams(q).get('w')==='1'),'source-version-ack-avoids-repeated-evidence');
            assert(source.querySelectorAll('a').length===2,'unsafe-protocol-and-private-IP-links-rejected');
            assert(source.querySelector('summary').textContent.includes('Yahoo / GitHub'),'actual-multiple-providers-have-distinct-source-labels');
            assert(source.textContent.includes('GitHub · 공개 이슈 · 일부 결과'),'github-scope-and-partial-results-are-not-mislabeled-as-general-web');
            assert(getComputedStyle(source.querySelector('ol')).listStyleType==='decimal','citation-numbers-survive-common-list-reset');
            assert(stable.target==='_blank'&&stable.rel.includes('noopener')&&stable.rel.includes('noreferrer')&&stable.referrerPolicy==='no-referrer','external-link-isolated-no-referrer');
            assert(source.textContent.includes('<img')&&source.textContent.includes('<script>')&&!source.querySelector('img,script')&&!window.__webPwned,'hostile-result-text-does-not-execute');
            await wait(()=>server.polls>=3&&!$('ai-send').disabled,'completed stream');
            assert(source===document.querySelector('.ai-web-sources')&&source.open,'answer-completion-preserves-citations');
            $('ai-model-settings').open=true;const model=$('ai-model');model.value='f'.repeat(32);model.dispatchEvent(new Event('change',{bubbles:true}));
            await wait(()=>!model.disabled&&server.conversations.get(cid).selection_id==='f'.repeat(32),'chat-only model selected');assert(source.isConnected&&source.open,'model-switch-keeps-current-citations');
            model.value=modelId;model.dispatchEvent(new Event('change',{bubbles:true}));await wait(()=>!model.disabled&&server.conversations.get(cid).selection_id===modelId,'tool-model restored');$('ai-model-settings').open=false;
            const current=[...$('ai-conversations').querySelectorAll('.ai-conversation')].find(n=>n.dataset.conversationId===cid);current.click();
            await wait(()=>document.querySelector('.ai-web-sources')&&!$('ai-send').disabled,'reloaded history');
            source=document.querySelector('.ai-web-sources');assert(source.querySelector('a').href===stable.href,'reload-restores-authoritative-sources');
            assert(!$('ai-web-search'),'history-reopen-keeps-automatic-search-without-toggle');source.open=true;
            await sleep(200);layout.expanded=geometry();
            assert(document.documentElement.scrollWidth<=innerWidth+1,'no-horizontal-page-overflow');
            assert(layout.expanded.pageHeight<=innerHeight+1||layout.expanded.fit==='minimum','page-fits-or-declared-minimum-fallback');
            assert(layout.expanded.send.right<=innerWidth+1,'send-control-remains-in-viewport-without-search-button');
            assert($('ai-scroll').clientHeight>=119,'chat-preserves-measured-minimum');
            assert(server.requests.filter(x=>x.method==='POST').every(x=>/\/(turns|selection)$/.test(x.path)),'no-business-or-lifecycle-mutations');
            $('ai-scroll').scrollTop=$('ai-scroll').scrollHeight;window.scrollTo(0,0);
            report.textContent=JSON.stringify({status:'pass',view:'web-search',width:innerWidth,theme,checks,layout,queryPolls:queries.length,production_data_used:false});
        }catch(error){report.textContent=JSON.stringify({status:'fail',view:'web-search',width:innerWidth,theme,checks,error:error.message,layout,geometry:geometry()});}
        if(window.parent!==window)window.parent.postMessage({fixtureResult:report.textContent},location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}
