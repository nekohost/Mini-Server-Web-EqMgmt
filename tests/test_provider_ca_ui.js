/* Browser-only contract. All HTTP is fulfilled in memory. TLS/DB/worker are covered by verify.py. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const tempRoot = require('node:os').tmpdir();
const stage = path.resolve(__dirname, '..');
const temp = fs.mkdtempSync(path.join(tempRoot, 'eqca-'));
for (const key of ['TMP','TEMP','TMPDIR']) process.env[key] = temp;

async function run() {
    const {chromium} = require('playwright');
    const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_BIN || undefined,
        args: ['--disable-background-networking','--disable-component-update','--no-first-run']});
    try {
        const width = Number(process.env.EQ_PROVIDER_UI_WIDTH || 390);
        const page = await browser.newPage({viewport:{width,height:840}});
        const errors = [], requests = [];
        page.on('pageerror', error => errors.push(error.message));
        const source = fs.readFileSync(path.join(stage,'templates/equipment_ai_providers.html'),'utf8');
        const markup = source.slice(source.indexOf('<section id="ai-providers-admin"'),source.indexOf('{% endblock %}',source.indexOf('<section id="ai-providers-admin"')))
            .replace('{{ assistant_csrf }}','fixture-csrf');
        const script = fs.readFileSync(path.join(stage,'static/js/equipment_ai_providers.js'),'utf8');
        const cssPath = 'static/css/equipment_ai_providers.css';
        const css = fs.readFileSync(fs.existsSync(path.join(stage,cssPath)) ? path.join(stage,cssPath) : path.resolve(stage,'../..',cssPath),'utf8');
        const pid = '1'.repeat(32), mid = '2'.repeat(32), group = '3'.repeat(32), jid = '4'.repeat(32);
        const ca = 'fixture upload', fingerprint = 'a1'.repeat(32), base = 'https://gpu.fixture.test:8443';
        let provider;
        await page.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            assert.equal(url.origin,'https://ui.fixture.test');
            if (url.pathname === '/') return route.fulfill({contentType:'text/html; charset=utf-8',body:
                '<meta name="viewport" content="width=device-width"><style>'+css+'</style>'+markup+
                '<script>window.showGlobalLoading=window.hideGlobalLoading=()=>{};</script><script src="/providers.js"></script>'});
            if (url.pathname === '/providers.js') return route.fulfill({contentType:'text/javascript; charset=utf-8',body:script});
            const body = request.postDataJSON();
            const content = data => route.fulfill({json:{success:true,...data}});
            if (request.method()==='POST') {
                assert.equal(request.headers()['x-csrftoken'],'fixture-csrf');
                requests.push([url.pathname,body]);
                if (url.pathname==='/api/admin/ai/providers') {
                    provider={id:pid,name:body.name,revision:0,enabled:0,models:[],trust_history:[
                        {revision:1,origin:base,fingerprint,expires:'2030-01-01',revoked:null}],
                        candidate:{...body,revision:1,addresses:['192.168.0.51'],has_key:true,fingerprint,
                            expires:'2030-01-01',models:[],result:'주소 승인',discovered:0}};
                    delete provider.candidate.ca_pem; delete provider.candidate.api_key;
                    return content({id:pid});
                }
                if (url.pathname.endsWith('/discover')) {
                    provider.candidate.discovered=1;
                    provider.candidate.models=[{id:mid,label:'Fixture model',context_tokens:null,profile:{enabled_levels:[]}}];
                    return content({});
                }
                if (url.pathname.endsWith('/probe')) return content({job_id:jid});
                if (url.pathname.endsWith('/revoke-trust')) {
                    provider.candidate=null; provider.retired=1; provider.trust_history[0].revoked=1;
                    return content({});
                }
            }
            if (url.pathname==='/api/admin/ai/providers') return content({groups:[{id:group,name:'GPU group'}],
                providers:provider?[provider]:[],encryption_configured:true});
            if (url.pathname==='/api/ai/jobs/'+jid) return content({state:'queued',steps:0});
            throw new Error('Unexpected fixture request '+url.pathname);
        });
        await page.goto('https://ui.fixture.test');
        await page.locator('[name=name]').fill('Fixture GPU');
        await page.locator('[name=base_url]').fill('http://192.168.0.51:8080');
        assert.equal(await page.locator('#provider-http-note').isVisible(),true);
        assert.equal(await page.locator('#provider-tls-mode').isVisible(),false);
        if (process.env.EQ_PROVIDER_UI_EVIDENCE) await page.screenshot({path:path.join(process.env.EQ_PROVIDER_UI_EVIDENCE,'http-'+width+'.png'),fullPage:true});
        await page.locator('[name=base_url]').fill(base);
        assert.equal(await page.locator('#provider-http-note').isVisible(),false);
        assert.equal(await page.locator('[name=trust_mode]').inputValue(),'system');
        assert.equal(await page.locator('[name=ca_file]').isVisible(),false);
        await page.locator('[name=trust_mode]').selectOption('private');
        if (process.env.EQ_PROVIDER_UI_EVIDENCE) await page.screenshot({path:path.join(process.env.EQ_PROVIDER_UI_EVIDENCE,'private-ca-'+width+'.png'),fullPage:true});
        await page.locator('[name=ca_file]').setInputFiles({name:'fixture.pem',mimeType:'text/plain',buffer:Buffer.from(ca)});
        await page.locator('[name=api_key]').fill('fixture-secret');
        await page.click('#provider-save');
        await page.click('#provider-dialog-accept');
        assert.equal(requests[0][1].ca_pem,ca);
        assert.equal(requests[0][1].api_key,'fixture-secret');
        assert.equal(await page.locator('[name=api_key]').inputValue(),'');
        assert.match(await page.locator('#provider-candidate-trust').innerText(),new RegExp(fingerprint));
        assert.match(await page.locator('#provider-candidate-trust').innerText(),/192\.168\.0\.51/);
        assert.equal(await page.locator('#provider-models-panel').isVisible(),false);
        await page.click('#provider-candidate-discover');
        await page.click('#provider-dialog-accept');
        assert.equal(requests[1][1].candidate_revision,1);
        await page.locator('#provider-candidate-models input[type=number]').fill('32768');
        await page.locator('#provider-candidate-models button').click();
        await page.click('#provider-dialog-accept');
        await page.click('#provider-dialog-accept');
        const probe=requests.find(([url])=>url.endsWith('/probe'))[1];
        assert.deepEqual([probe.provider_id,probe.candidate_revision,probe.context_tokens],[pid,1,32768]);
        await page.click('#provider-revoke');
        await page.click('#provider-dialog-accept');
        await page.click('#provider-dialog-accept');
        assert.equal(requests.at(-1)[1].revision,1);
        assert.deepEqual(errors,[]);
        console.log('PASS: HTTP, default TLS, CA upload, fingerprint, discovery/probe and revocation ('+width+'px).');
    } finally {
        await browser.close();
    }
}

run().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{
    if (path.dirname(temp) === tempRoot && path.basename(temp).startsWith('eqca-')) {
        fs.rmSync(temp,{recursive:true,force:true,maxRetries:4,retryDelay:200});
    }
});
