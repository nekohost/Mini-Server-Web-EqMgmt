import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const MINI='D:/Project/Mini-Server-Web-EqMgmt';
const GENERAL_ROOT='D:/General';
const generalTool=rel=>pathToFileURL(path.join(GENERAL_ROOT,'.agent-governance','tooling',rel)).href;
const { executeTransition }=await import(generalTool('transition-engine.mjs'));
const { deliverConversationEvent }=await import(generalTool('routed-conversation-delivery.mjs'));
const { readState }=await import(generalTool('state-store.mjs'));
const miniReceiver=pathToFileURL(path.join(MINI,'.agent-governance','tooling','conversation-recorder','routed-ingest.mjs')).href;
const GENERAL={kind:'general',id:'general'};
function roots(){const base=fs.mkdtempSync(path.join(os.tmpdir(),'mini-general-routed-e2e-'));return {base,state:path.join(base,'state'),audit:path.join(base,'audit'),generalChat:path.join(base,'GeneralChat'),generalRecorder:path.join(base,'GeneralRecorder'),miniChat:path.join(base,'MiniChat')};}
function opts(r){return {allowTestRoots:true,dispatcherStateRoot:r.state,auditRoot:r.audit,chatRoot:r.generalChat,recorderStateRoot:r.generalRecorder,deliveryExecutor:miniExecutor(r.miniChat)};}
function source(key,id,revision,previousCursor,cursor,content,time){return {session_key:key,routing_revision:revision,provider:'chatgpt-remote',adapter_id:'general.normalized-event.v1',adapter_version:'1',thread_id:`thread-${key}`,source_event_id:id,previous_cursor:previousCursor,source_cursor:cursor,source_fingerprint:`fp-${id}`,occurred_at:time, timestamp_quality:'provider-exact',actor:'user',channel:'user',speaker:'사용자',content};}
function miniExecutor(chatRoot){return (_runtime,envelope)=>{
  const code=`import fs from 'node:fs';import { ingestRoutedEnvelope } from ${JSON.stringify(miniReceiver)};const e=JSON.parse(fs.readFileSync(0,'utf8'));const r=await ingestRoutedEnvelope(e,{workspaceRoot:${JSON.stringify(MINI)},chatRoot:process.env.MINI_CHAT_ROOT,allowTestRoots:true});process.stdout.write(JSON.stringify(r));`;
  const result=spawnSync(process.execPath,['--input-type=module','--eval',code],{input:JSON.stringify(envelope),encoding:'utf8',windowsHide:true,shell:false,env:{...process.env,MINI_CHAT_ROOT:chatRoot},timeout:5000,maxBuffer:1024*1024});
  if(result.error||result.status!==0)return {ok:false,reason:`mini-e2e:${result.error?.message??result.stderr??result.stdout}`};
  try{return {ok:true,result:JSON.parse(String(result.stdout).trim())};}catch{return {ok:false,reason:'mini-e2e-invalid-json'};}
};}
function initGeneral(r,key){return executeTransition({session_key:key,expected_revision:null,event_type:'initialize-owner',evidence:['user-explicit'],owner:GENERAL},{root:r.state,auditRoot:r.audit});}
function switchMini(r,key,revision){return executeTransition({session_key:key,expected_revision:revision,event_type:'full-switch',evidence:['user-explicit'],target_owner:{kind:'governed-workspace',id:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI)},target_governance:{owner_id:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI),workspace_path:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI),platform:'chatgpt-remote'}},{root:r.state,auditRoot:r.audit});}
function switchGeneral(r,key,revision){return executeTransition({session_key:key,expected_revision:revision,event_type:'full-switch',evidence:['user-explicit'],target_owner:GENERAL},{root:r.state,auditRoot:r.audit});}
function nestedMini(r,key,revision){return executeTransition({session_key:key,expected_revision:revision,event_type:'nested-handoff-enter',evidence:['governed-target'],target_owner:{kind:'governed-workspace',id:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI)},target_governance:{owner_id:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI),workspace_path:fs.realpathSync.native?fs.realpathSync.native(MINI):fs.realpathSync(MINI),platform:'chatgpt-remote'}},{root:r.state,auditRoot:r.audit});}
function nestedExit(r,key,revision){return executeTransition({session_key:key,expected_revision:revision,event_type:'nested-handoff-exit',evidence:['parent-continuity']},{root:r.state,auditRoot:r.audit});}
function textIf(file){return fs.existsSync(file)?fs.readFileSync(file,'utf8'):'';}
test('full switch routes visible turns only to the owner Chat and retry is idempotent',()=>{
  const r=roots();try{
    const key='full-switch';initGeneral(r,key);
    const g0=source(key,'g0',0,null,'c0','General-before','2026-09-10T23:58:00.000Z');
    assert.equal(deliverConversationEvent(g0,opts(r)).decision,'recorded');
    assert.equal(switchMini(r,key,0).decision,'switch-owner');
    const m1=source(key,'m1',1,'c0','c1','Mini-middle','2026-09-10T23:58:01.000Z');
    assert.equal(deliverConversationEvent(m1,opts(r)).decision,'recorded');
    assert.equal(switchGeneral(r,key,1).decision,'switch-owner');
    const g2=source(key,'g2',2,'c1','c2','General-after','2026-09-10T23:58:02.000Z');
    assert.equal(deliverConversationEvent(g2,opts(r)).decision,'recorded');
    assert.equal(deliverConversationEvent(m1,opts(r)).decision,'existing');
    const gf=textIf(path.join(r.generalChat,'2026','09','11.md')); const mf=textIf(path.join(r.miniChat,'2026','09','11.md'));
    assert.ok(gf.includes('General-before')&&gf.includes('General-after')&&!gf.includes('Mini-middle'));
    assert.ok(mf.includes('Mini-middle')&&!mf.includes('General-before')&&!mf.includes('General-after'));
    assert.equal((mf.match(/Mini-middle/g)??[]).length,1);
  }finally{fs.rmSync(r.base,{recursive:true,force:true});}
});
test('historical governed revision uses Mini owner even after current owner returns to General',()=>{
  const r=roots();try{
    const key='historical';initGeneral(r,key);assert.equal(switchMini(r,key,0).decision,'switch-owner');assert.equal(switchGeneral(r,key,1).decision,'switch-owner');
    const oldMini=source(key,'hm1',1,null,'h1','Historical-Mini','2026-09-10T23:59:00.000Z');
    assert.equal(deliverConversationEvent(oldMini,opts(r)).decision,'recorded');
    const nowGeneral=source(key,'hg2',2,'h1','h2','Current-General','2026-09-10T23:59:01.000Z');
    assert.equal(deliverConversationEvent(nowGeneral,opts(r)).decision,'recorded');
    const gf=textIf(path.join(r.generalChat,'2026','09','11.md'));const mf=textIf(path.join(r.miniChat,'2026','09','11.md'));
    assert.ok(mf.includes('Historical-Mini')&&!mf.includes('Current-General'));
    assert.ok(gf.includes('Current-General')&&!gf.includes('Historical-Mini'));
    assert.equal(readState(key,{root:r.state}).state.owner.kind,'general');
  }finally{fs.rmSync(r.base,{recursive:true,force:true});}
});

test('nested handoff routes detail to Mini then returns recording to General parent',()=>{
  const r=roots();try{
    const key='nested';initGeneral(r,key);assert.equal(nestedMini(r,key,0).decision,'enter-nested');
    const m1=source(key,'nm1',1,null,'n1','Nested-Mini','2026-09-11T00:00:00.000Z');assert.equal(deliverConversationEvent(m1,opts(r)).decision,'recorded');
    assert.equal(nestedExit(r,key,1).decision,'return-parent');
    const g2=source(key,'ng2',2,'n1','n2','Parent-General','2026-09-11T00:00:01.000Z');assert.equal(deliverConversationEvent(g2,opts(r)).decision,'recorded');
    const gf=textIf(path.join(r.generalChat,'2026','09','11.md'));const mf=textIf(path.join(r.miniChat,'2026','09','11.md'));
    assert.ok(mf.includes('Nested-Mini')&&!mf.includes('Parent-General'));assert.ok(gf.includes('Parent-General')&&!gf.includes('Nested-Mini'));
    assert.equal(readState(key,{root:r.state}).state.parent_stack.length,0);
  }finally{fs.rmSync(r.base,{recursive:true,force:true});}
});
