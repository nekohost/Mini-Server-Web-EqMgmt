// Linux-only behavior fixtures. Windows runs syntax checks, not application behavior.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const code=readFileSync(new URL('../static/js/strata_bridge.js',import.meta.url),'utf8');
const linux={skip:process.platform==='win32'};
function fixture(identity='a'.repeat(32), responseCode=200, initial={}) {
    class StorageMock {
        constructor(){this.data=new Map(Object.entries(initial));}
        get length(){return this.data.size;}
        getItem(key){return this.data.has(String(key))?this.data.get(String(key)):null;}
        setItem(key,value){this.data.set(String(key),String(value));}
        removeItem(key){this.data.delete(String(key));}
        key(index){return [...this.data.keys()][index]??null;}
    }
    const storage=new StorageMock(), calls=[], messages=[];
    const listeners={};
    const window={localStorage:storage,location:{origin:'https://fixture.example'},
        fetch:async (...args)=>{calls.push(args);return new Response('{}',{status:responseCode});},
        addEventListener:(name,fn)=>{listeners[name]=fn;},
        parent:{postMessage:(data,origin)=>messages.push({data,origin}),document:{addEventListener:()=>{}}}};
    const document={baseURI:'https://fixture.example/strata/',querySelector:selector=>({content:
        selector.includes('namespace')?identity:'csrf-fixture'})};
    vm.runInNewContext(code,{window,document,Storage:StorageMock,URL,Request,Headers,TypeError});
    return {window,storage,calls,messages,listeners};
}

test('relative POST resolves to the gateway and gets CSRF without a shared key',linux,async()=>{
    const f=fixture();
    await f.window.fetch('v1/chat/completions',{method:'POST',headers:{Authorization:'Bearer rejected-browser-key'},body:'{}'});
    assert.equal(f.calls[0][0].url,'https://fixture.example/strata/v1/chat/completions');
    assert.equal(f.calls[0][1].headers.get('X-CSRFToken'),'csrf-fixture');
    assert.equal(f.calls[0][1].headers.get('Authorization'),null);
    assert.equal(f.calls[0][1].credentials,'same-origin');
    assert.equal(f.calls[0][1].cache,'no-store');
});
test('Request inputs retain body and abort signal',linux,async()=>{
    const f=fixture(), controller=new AbortController();
    const input=new Request('https://fixture.example/strata/settings',{
        method:'POST',body:'{"shared":false}',signal:controller.signal});
    await f.window.fetch(input);
    assert.equal(await f.calls[0][0].clone().text(),'{"shared":false}');
    controller.abort();
    assert.equal(f.calls[0][0].signal.aborted,true);
});
test('storage is session scoped and never keeps an API key',linux,()=>{
    const f=fixture();
    f.storage.setItem('strata.chat','private chat');
    f.storage.setItem('strata.apikey','should-not-be-stored');
    assert.equal(f.storage.data.get('eqmgmt.strata.'+'a'.repeat(32)+'.strata.chat'),'private chat');
    assert.equal(f.storage.getItem('strata.apikey'),null);
    assert.ok(![...f.storage.data.values()].includes('should-not-be-stored'));
});
test('a new account/session clears only the previous Strata namespace',linux,()=>{
    const previous='eqmgmt.strata.'+'b'.repeat(32)+'.';
    const f=fixture('a'.repeat(32),200,{'eqmgmt.strata.active':previous,[previous+'strata.chat']:'old','equipment.preference':'keep'});
    assert.equal(f.storage.data.has(previous+'strata.chat'),false);
    assert.equal(f.storage.getItem('equipment.preference'),'keep');
});
test('cross-origin and non-gateway requests are refused before the network',linux,async()=>{
    const f=fixture();
    await assert.rejects(f.window.fetch('https://evil.example/'),/configured gateway/);
    await assert.rejects(f.window.fetch('/api/users'),/configured gateway/);
    assert.equal(f.calls.length,0);
});
test('access failure clears this session and notifies only the embedding origin',linux,async()=>{
    const f=fixture('a'.repeat(32),401);
    f.storage.setItem('strata.chat','private chat');
    await f.window.fetch('metrics');
    assert.equal(f.storage.getItem('strata.chat'),null);
    assert.equal(f.messages[0].origin,'https://fixture.example');
    assert.equal(f.messages[0].data.type,'eqmgmt-strata-access-error');
});
