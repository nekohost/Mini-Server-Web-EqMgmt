/* [MINI-COMMENT: ASSISTANT.RECOVERY.UI.TEST] [EN rev.2]
 * [Role] Reproduces terminal state changes without lifecycle revisions and a delayed previous poll.
 * [Dependencies] Candidate owner-scoped DOM and inert authenticated transport only.
 * [Impact] Proves draft/search/error retention and manual-only resubmission while unknown requests remain locked.
 */
function runAiRecoveryFixture(server,cid,oldCid,modelId,jid,sleep,theme) {
    const original=server.fetch.bind(server), nextJid='6'.repeat(32), ctxJid='5'.repeat(32);
    const trashCid=[...server.conversations.values()].find(item=>item.is_deleted)?.id||'9'.repeat(32);
    const failure='AI 응답 연결이 끝까지 확인되지 않아 작업을 중단했습니다. 이전 요청의 종료 확인이 필요합니다.';
    const thought='검토한 내용을 보존합니다. '.repeat(200).slice(0,2994);
    let phase='failed', messageReads=0, oldPolls=0, nextPolls=0, failSnapshot=false, omitJob=false, holdSnapshot=false, contextLimitMode=false, releaseSnapshot=null, heldPoll=null;
    const record=(url,options)=>server.requests.push({path:url.pathname,search:url.search,method:options.method||'GET',data:options.body?JSON.parse(options.body):null,headers:options.headers||{}});
    const stopped=()=>({id:jid,state:phase,error:failure,error_code:'STREAM_INCOMPLETE',steps:2,answer_started:false});
    // 후속 완료 턴 뒤에 남는 과거 CONTEXT_LIMIT 실패 턴과 휴지통 읽기 전용 검증용 스냅샷을 구성한다.
    const contextLimitTurns=()=>({
        messages:[
            {id:201,role:'user',content:'긴 컨텍스트 요청',reasoning:'',job:ctxJid},
            {id:202,role:'assistant',content:'',reasoning:'',job:ctxJid},
            {id:203,role:'user',content:'짧은 후속 질문',reasoning:'',job:nextJid},
            {id:204,role:'assistant',content:'후속 응답은 정상 완료되었습니다.',reasoning:'',job:nextJid},
        ],
        jobs:[
            {id:nextJid,state:'done',steps:1,answer_started:true},
            {id:ctxJid,state:'failed',error:'입력 길이가 모델의 최대 컨텍스트 한도를 초과했습니다.',error_code:'CONTEXT_LIMIT',steps:1,answer_started:false},
        ],
    });
    server.conversations.get(cid).title='중단된 대화 복구 확인'; server.conversations.get(cid).next_level='xhigh';
    server.fetch=async(path,options={})=>{
        const url=new URL(path,location.origin);
        if(url.pathname==='/api/ai/jobs/'+jid){
            record(url,options); oldPolls++;
            return new Promise(resolve=>{heldPoll=()=>resolve(server.respond({success:true,state:'recovery_required',message_id:102,generation:3,r:2994,c:0,reasoning_length:2994,content_length:0,reasoning:'',content:'',answer_started:false,proposals:[],error:failure,error_code:'STREAM_INCOMPLETE'}));});
        }
        if(url.pathname==='/api/ai/jobs/'+nextJid){
            record(url,options); nextPolls++;
            return server.respond({success:true,state:'done',message_id:104,generation:1,r:0,c:13,reasoning_length:0,content_length:13,reasoning:'',content:'다음 요청을 확인했습니다.',answer_started:true,proposals:[]});
        }
        if(url.pathname===`/api/ai/conversations/${cid}/messages`&&failSnapshot){
            record(url,options); failSnapshot=false; throw new TypeError('synthetic snapshot disconnect');
        }
        if(url.pathname===`/api/ai/conversations/${cid}/messages`&&holdSnapshot){
            record(url,options); messageReads++; holdSnapshot=false;
            return new Promise(resolve=>{releaseSnapshot=()=>resolve(server.respond({success:true,conversation:{...server.conversations.get(cid)},messages:[{id:102,role:'assistant',content:'',reasoning:thought,job:jid}],proposals:[],jobs:[{...stopped(),state:'failed'}],next_before:null}));});
        }
        const response=await original(path,options), body=await response.json();
        if(url.pathname==='/api/ai/capabilities')body.web_search={available:true,default:false,engine:'Yahoo'};
        if(url.pathname===`/api/ai/conversations/${cid}/messages`){
            messageReads++;
            if(contextLimitMode){
                const turnsData=contextLimitTurns();
                body.messages=turnsData.messages; body.jobs=turnsData.jobs; body.proposals=[]; body.next_before=null;
            }else{
                body.messages=[{id:101,role:'user',content:'이전 질문을 확인해 주세요.',reasoning:'',job:jid},{id:102,role:'assistant',content:'',reasoning:thought,job:jid}];
                body.jobs=omitJob?[]:[stopped()]; body.proposals=[]; body.next_before=null;
                if(server.sent){
                    body.messages.push({id:103,role:'user',content:'다음 요청입니다.',reasoning:'',job:nextJid},{id:104,role:'assistant',content:'',reasoning:'',job:nextJid});
                    body.jobs.unshift({id:nextJid,state:nextPolls?'done':'queued',steps:0});
                }
            }
        }else if(contextLimitMode&&url.pathname===`/api/ai/conversations/${trashCid}/messages`){
            const turnsData=contextLimitTurns();
            body.messages=turnsData.messages; body.jobs=turnsData.jobs; body.proposals=[]; body.next_before=null;
        }
        if(url.pathname.endsWith('/turns'))body.job_id=nextJid;
        return server.respond(body,response.status);
    };
    document.addEventListener('DOMContentLoaded',async()=>{
        const checks=[],layout={},report=document.createElement('pre'); report.id='browser-test-result'; report.hidden=true; document.body.append(report);
        const $=id=>document.getElementById(id);
        const wait=async(test,label,attempts=500)=>{for(let i=0;i<attempts;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
        const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
        const clickConversation=id=>{const button=$('ai-conversations').querySelector(`[data-conversation-id="${id}"].ai-conversation`);if(!button)throw Error('conversation missing');button.click();};
        const turns=()=>server.requests.filter(r=>r.path.endsWith('/turns'));
        const capture=()=>({width:innerWidth,height:innerHeight,pageWidth:document.documentElement.scrollWidth,pageHeight:document.documentElement.scrollHeight,sendDisabled:$('ai-send').disabled,progress:$('ai-progress-text').textContent});
        try{
            window.frameElement.style.height=(innerWidth<=760?844:1000)+'px';
            await wait(()=>!$('ai-send').disabled&&$('ai-progress-text').textContent.includes('응답을 완료하지 못했습니다.'),'initial failed snapshot');
            assert($('ai-level').value==='xhigh'&&document.querySelector('.ai-thought')?.textContent.includes('검토한 내용을'),'failed-original-thought-and-supported-model-retained');
            assert(turns().length===0,'opening-failed-chat-does-not-repeat-request');
            const initialErrorBox=document.querySelector('.ai-message[data-role="assistant"] .ai-job-error');
            assert(initialErrorBox&&initialErrorBox.dataset.state==='failed'&&initialErrorBox.textContent.includes(failure.split(' 이전 요청의')[0])&&initialErrorBox.textContent.includes('오류 코드: STREAM_INCOMPLETE')&&initialErrorBox.textContent.includes('새 요청')&&!initialErrorBox.textContent.includes('종료 확인이 필요합니다.'),'failed-message-renders-durable-error-box-with-code');
            assert($('ai-progress').dataset.state==='failed'&&$('ai-progress-text').textContent.includes('(오류 코드: STREAM_INCOMPLETE)'),'progress-shows-stream-incomplete-error-code');
            phase='recovery_required'; clickConversation(cid);
            await wait(()=>$('ai-send').disabled&&$('ai-progress-text').textContent.includes('종료 확인이 필요합니다.'),'unknown execution remains blocked');
            const recoveryBox=document.querySelector('.ai-message[data-role="assistant"] .ai-job-error');
            assert(recoveryBox&&recoveryBox.dataset.state==='recovery_required'&&recoveryBox.textContent.includes('종료 확인 필요')&&recoveryBox.textContent.includes('오류 코드: STREAM_INCOMPLETE'),'recovery-required-message-error-box-stays-visible');
            await wait(()=>oldPolls>0,'previous job poll is deliberately pending');
            $('ai-input').value='종료 확인 후 보낼 초안'; $('ai-input').dispatchEvent(new Event('input',{bubbles:true}));
            assert(!$('ai-web-search'),'automatic-search-has-no-stale-toggle'); document.querySelector('.ai-thought').open=true;
            const reads=messageReads; window.dispatchEvent(new Event('focus'));
            await wait(()=>messageReads>reads,'unchanged lifecycle snapshot read'); await sleep(120);
            assert($('ai-send').disabled&&turns().length===0,'unknown-server-state-is-never-unlocked-or-replayed');
            omitJob=true; const missingReads=messageReads; window.dispatchEvent(new Event('focus'));
            await wait(()=>messageReads>missingReads,'snapshot without current job'); await sleep(120);
            assert($('ai-send').disabled&&turns().length===0,'missing-job-is-not-treated-as-confirmed-completion'); omitJob=false;
            phase='failed'; const terminalReads=messageReads; window.dispatchEvent(new Event('focus'));
            await wait(()=>messageReads>terminalReads,'terminal same-revision snapshot');
            await wait(()=>!$('ai-send').disabled,'terminal snapshot releases stale composer lock',180);
            assert($('ai-input').value==='종료 확인 후 보낼 초안'&&!$('ai-web-search'),'terminal-refresh-preserves-draft-and-automatic-search-ui');
            assert(document.querySelector('.ai-thought').open&&document.querySelector('.ai-thought').textContent.includes(thought),'terminal-refresh-retains-entire-thought-and-reader-choice');
            assert($('ai-progress-text').textContent.includes(failure.split(' 이전 요청의')[0])&&$('ai-progress-text').textContent.includes('새 요청')&&!$('ai-progress-text').textContent.includes('종료 확인이 필요합니다.'),'original-failure-cause-and-current-recovery-guidance-both-visible');
            const recoveredBox=document.querySelector('.ai-message[data-role="assistant"] .ai-job-error');
            assert(recoveredBox&&recoveredBox.dataset.state==='failed'&&recoveredBox.textContent.includes('오류 코드: STREAM_INCOMPLETE')&&recoveredBox.textContent.includes('새 요청')&&!recoveredBox.textContent.includes('종료 확인이 필요합니다.'),'recovered-message-error-box-updates-guidance');
            assert($('ai-progress-text').textContent.includes('(오류 코드: STREAM_INCOMPLETE)'),'recovered-progress-retains-error-code');
            assert(turns().length===0,'terminal-refresh-only-reads-does-not-send-an-inference');
            layout.recovered=capture();
            const retry=$('ai-refresh-state'); await wait(()=>retry&&!retry.hidden&&!retry.disabled,'state refresh completed'); assert(true,'read-only-state-retry-is-available');
            phase='recovery_required'; clickConversation(cid); await wait(()=>$('ai-send').disabled&&!retry.disabled,'reopen unresolved');
            failSnapshot=true; retry.click(); await wait(()=>!retry.disabled&&!$('ai-notice').hidden,'failed state read is retryable');
            assert($('ai-send').disabled&&$('ai-input').value==='종료 확인 후 보낼 초안','failed-read-retains-lock-and-draft');
            phase='failed'; retry.click(); await wait(()=>!retry.disabled&&!$('ai-send').disabled,'manual authenticated terminal recovery');
            $('ai-input').value='다음 요청입니다.';$('ai-input').dispatchEvent(new Event('input',{bubbles:true})); $('ai-form').requestSubmit();
            await wait(()=>server.sent===1&&nextPolls>0&&!$('ai-send').disabled,'next request polls independently of previous pending GET');
            assert(turns().length===1&&turns()[0].data.content==='다음 요청입니다.','only-one-explicit-new-turn-is-submitted');
            heldPoll?.(); await sleep(120);
            assert(!$('ai-send').disabled&&!$('ai-progress-text').textContent.includes('관리자에게 문의'),'late-previous-job-result-cannot-relock-new-request');
            assert($('ai-messages').textContent.includes('다음 요청을 확인했습니다.'),'next-request-result-renders-after-stopped-history');
            const liveAssistants=[...document.querySelectorAll('.ai-message[data-role="assistant"]')];
            assert(liveAssistants.length===2&&liveAssistants[0].querySelector('.ai-job-error')?.dataset.state==='failed'&&liveAssistants[0].querySelector('.ai-job-error')?.textContent.includes('오류 코드: STREAM_INCOMPLETE')&&!liveAssistants[1].querySelector('.ai-job-error'),'completed-next-turn-preserves-earlier-failed-message-error-box');
            await wait(()=>$('ai-more-conversations').hidden===false,'older conversation cursor'); $('ai-more-conversations').click();
            await wait(()=>$('ai-conversations').querySelector(`[data-conversation-id="${oldCid}"].ai-conversation`),'other conversation');
            server.sent=0; phase='recovery_required'; clickConversation(cid); await wait(()=>$('ai-send').disabled&&!retry.disabled,'prepare delayed snapshot');
            holdSnapshot=true; retry.click(); await wait(()=>releaseSnapshot,'state refresh snapshot held');
            clickConversation(oldCid); await wait(()=>$('ai-title').textContent==='이전 페이지 대화'&&!$('ai-send').disabled,'other conversation selected during recovery read');
            $('ai-input').value='다른 대화에 남길 초안'; releaseSnapshot(); await sleep(100);
            assert($('ai-title').textContent==='이전 페이지 대화'&&$('ai-input').value==='다른 대화에 남길 초안'&&!$('ai-send').disabled,'late-snapshot-cannot-replace-another-selected-chat');
            assert(server.requests.every(r=>r.method==='GET'||r.path.endsWith('/turns')),'state-confirmation-never-posts-cancel-ack-or-guard-release');

            // 후속 턴이 완료되거나 휴지통 읽기 전용 화면으로 열려도 이전 CONTEXT_LIMIT 실패 원인과 오류 코드가 메시지 본문 아래에 남는지 확인한다.
            contextLimitMode=true;
            clickConversation(cid);
            await wait(()=>!$('ai-send').disabled&&$('ai-messages').textContent.includes('후속 응답은 정상 완료되었습니다.')&&$('equipment-ai').getAttribute('aria-busy')==='false','context-limit multi-turn active view');
            const activeArticles=[...$('ai-messages').querySelectorAll('.ai-message[data-role="assistant"]')];
            assert($('ai-progress').hidden&&activeArticles.length===2,'completed-latest-turn-hides-bottom-progress');
            assert(activeArticles[0].querySelector('.ai-job-error')?.dataset.state==='failed'&&activeArticles[0].querySelector('.ai-job-error')?.textContent.includes('오류 코드: CONTEXT_LIMIT')&&activeArticles[0].querySelector('.ai-job-error')?.textContent.includes('입력 길이가 모델의 최대 컨텍스트 한도를 초과했습니다.')&&!activeArticles[1].querySelector('.ai-job-error'),'older-context-limit-error-remains-visible-after-done-turn');
            assert(document.documentElement.scrollWidth<=innerWidth+1&&$('ai-scroll').clientHeight>=119,'context-limit-active-view-fits-without-horizontal-overflow');

            const trashListBefore=server.requests.filter(r=>r.path==='/api/ai/conversations').length;
            $('ai-trash-tab').click();
            await wait(()=>server.requests.filter(r=>r.path==='/api/ai/conversations').length>trashListBefore&&$('ai-trash-tab').getAttribute('aria-pressed')==='true'&&$('ai-conversations').querySelector(`[data-conversation-id="${trashCid}"].ai-conversation`),'trash tab loaded');
            await sleep(40);
            clickConversation(trashCid);
            await wait(()=>$('ai-title').textContent.includes('미리 보관한')&&$('ai-messages').textContent.includes('후속 응답은 정상 완료되었습니다.')&&$('equipment-ai').getAttribute('aria-busy')==='false','context-limit read-only trash view');
            const trashArticles=[...$('ai-messages').querySelectorAll('.ai-message[data-role="assistant"]')];
            assert($('ai-progress').hidden&&$('ai-input').disabled,'trash-read-only-hides-progress-and-disables-composer');
            assert(trashArticles.length===2&&trashArticles[0].querySelector('.ai-job-error')?.dataset.state==='failed'&&trashArticles[0].querySelector('.ai-job-error')?.textContent.includes('오류 코드: CONTEXT_LIMIT')&&trashArticles[0].querySelector('.ai-job-error')?.textContent.includes('입력 길이가 모델의 최대 컨텍스트 한도를 초과했습니다.')&&!trashArticles[1].querySelector('.ai-job-error'),'read-only-trash-view-retains-context-limit-error-box');
            assert(document.documentElement.scrollWidth<=innerWidth+1,'context-limit-trash-view-has-no-horizontal-overflow');

            const activeListBefore=server.requests.filter(r=>r.path==='/api/ai/conversations').length;
            contextLimitMode=false;
            $('ai-active-tab').click();
            await wait(()=>server.requests.filter(r=>r.path==='/api/ai/conversations').length>activeListBefore&&$('ai-active-tab').getAttribute('aria-pressed')==='true'&&$('ai-conversations').querySelector(`[data-conversation-id="${cid}"].ai-conversation`),'active tab restored');
            await sleep(50);

            phase='failed'; clickConversation(cid); await wait(()=>!$('ai-send').disabled&&$('ai-progress-text').textContent.includes('새 요청'),'final failure guidance');
            $('ai-input').value='이 대화에서 계속 질문할 수 있습니다.'; document.querySelector('.ai-thought').open=false;
            await sleep(120); layout.final=capture();
            assert(layout.final.pageWidth<=innerWidth+1&&layout.final.pageHeight<=innerHeight+1,'recovery-ui-fits-narrow-and-desktop-viewport');
            assert(retry.getBoundingClientRect().height>=36&&getComputedStyle(retry).whiteSpace==='nowrap','state-retry-remains-readable-and-clickable-without-stacked-label');
            assert(document.querySelector('.ai-message[data-role="assistant"] .ai-job-error')?.textContent.includes('오류 코드: STREAM_INCOMPLETE')&&$('ai-progress-text').textContent.includes('(오류 코드: STREAM_INCOMPLETE)'),'final-recovery-view-shows-error-code-in-both-message-and-progress');
            assert($('ai-scroll').clientHeight>=119,'recovery-ui-preserves-minimum-chat-height');
            report.textContent=JSON.stringify({status:'pass',width:innerWidth,theme,checks,layout,postCount:turns().length,oldPolls,nextPolls});
        }catch(error){report.textContent=JSON.stringify({status:'fail',width:innerWidth,theme,checks,layout,error:error.message,stack:error.stack});}
        window.parent.postMessage({fixtureResult:report.textContent},location.origin);
    });
}
