import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import { ingestRoutedEnvelope, fingerprintWorkspace } from './routed-ingest.mjs';

const MINI='D:/Project/Mini-Server-Web-EqMgmt';
const GENERAL='D:/General';
const sha=value=>crypto.createHash('sha256').update(String(value),'utf8').digest('hex').toUpperCase();
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])):value;
const shaJson=value=>crypto.createHash('sha256').update(JSON.stringify(canonical(value)),'utf8').digest('hex').toUpperCase();
function side(kind,fp){return {kind,workspace_root:fp.root,owner_id:fp.root,governance_version:fp.governanceVersion,rule_sha256:fp.fingerprints.rule,manifest_sha256:fp.fingerprints.manifest,capability_sha256:fp.fingerprints.capability,bootstrap_sha256:fp.fingerprints.bootstrap};}
function makeEnvelope(overrides={}){
  const target=fingerprintWorkspace(MINI); const authority=fingerprintWorkspace(GENERAL);
  const content=overrides.content??'routed 테스트 본문';
  const event={event_id:overrides.event_id??sha('event-1'),stream_digest:sha('stream-1'),session_digest:sha('session-1'),routing_revision:overrides.routing_revision??7,provider:'chatgpt-remote',occurred_at:'2026-09-10T23:55:00.000Z',timestamp_quality:'provider-exact',actor:overrides.actor??'user',channel:overrides.channel??'user',speaker:overrides.speaker??'사용자',content,content_sha256:sha(content),previous_cursor:null,source_cursor:'cursor-1',source_fingerprint:'source-fingerprint-1'};
  const body={schema_version:1,schema:'general.routed-conversation-envelope.v1',authority:side('general-dispatcher',authority),target:side('governed-workspace',target),event};
  return {...body,envelope_id:shaJson(body)};
}
function rehash(envelope){const copy=structuredClone(envelope);delete copy.envelope_id;copy.envelope_id=shaJson(copy);return copy;}
test('valid routed event records exactly once through existing writer',async()=>{
  const chat=fs.mkdtempSync(path.join(os.tmpdir(),'mini-routed-chat-'));
  try{
    const envelope=makeEnvelope();
    const first=await ingestRoutedEnvelope(envelope,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true});
    const second=await ingestRoutedEnvelope(envelope,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true});
    assert.equal(first.decision,'recorded'); assert.equal(second.decision,'existing');
    assert.equal(first.target_owner,fingerprintWorkspace(MINI).root);
    const file=path.join(chat,'2026','09','11.md'); const text=fs.readFileSync(file,'utf8');
    assert.equal((text.match(/routed 테스트 본문/g)??[]).length,1);
  }finally{fs.rmSync(chat,{recursive:true,force:true});}
});

test('target governance fingerprint mismatch is rejected before write',async()=>{
  const chat=fs.mkdtempSync(path.join(os.tmpdir(),'mini-routed-target-'));
  try{
    const envelope=makeEnvelope(); envelope.target.capability_sha256='0'.repeat(64); const forged=rehash(envelope);
    await assert.rejects(()=>ingestRoutedEnvelope(forged,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true}),/target-capability-fingerprint-mismatch/);
    assert.equal(fs.readdirSync(chat).length,0);
  }finally{fs.rmSync(chat,{recursive:true,force:true});}
});
test('General authority fingerprint mismatch is rejected before write',async()=>{
  const chat=fs.mkdtempSync(path.join(os.tmpdir(),'mini-routed-authority-'));
  try{
    const envelope=makeEnvelope(); envelope.authority.bootstrap_sha256='F'.repeat(64); const forged=rehash(envelope);
    await assert.rejects(()=>ingestRoutedEnvelope(forged,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true}),/authority-bootstrap-fingerprint-mismatch/);
    assert.equal(fs.readdirSync(chat).length,0);
  }finally{fs.rmSync(chat,{recursive:true,force:true});}
});

test('same event identity with changed content is rejected as conflict',async()=>{
  const chat=fs.mkdtempSync(path.join(os.tmpdir(),'mini-routed-conflict-'));
  try{
    const first=makeEnvelope(); await ingestRoutedEnvelope(first,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true});
    const changed=makeEnvelope({event_id:first.event.event_id,content:'변경된 본문'});
    await assert.rejects(()=>ingestRoutedEnvelope(changed,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true}),/routed-event-content-conflict/);
    const text=fs.readFileSync(path.join(chat,'2026','09','11.md'),'utf8');
    assert.ok(text.includes('routed 테스트 본문')); assert.ok(!text.includes('변경된 본문'));
  }finally{fs.rmSync(chat,{recursive:true,force:true});}
});
test('non-visible ChatGPT event is rejected',async()=>{
  const chat=fs.mkdtempSync(path.join(os.tmpdir(),'mini-routed-hidden-'));
  try{
    const envelope=makeEnvelope({actor:'assistant',channel:'system',speaker:'System'});
    await assert.rejects(()=>ingestRoutedEnvelope(envelope,{workspaceRoot:MINI,chatRoot:chat,allowTestRoots:true}),/visible-event-invalid/);
    assert.equal(fs.readdirSync(chat).length,0);
  }finally{fs.rmSync(chat,{recursive:true,force:true});}
});
