"""[MINI-COMMENT: ASSISTANT.PROVIDERS.REDESIGN.BROWSER.FIXTURE]
[EN rev.1]
[Role] Renders the redesigned AI connection screens with three synthetic connections and captures example screenshots
(desktop 1440px and Fold7 cover 384px): Overview with a pending address change, a legacy name-only wait, Connection
settings, Served models, an immediate rename, the stored-record archive and the user model choice list.
[Dependencies] Real candidate templates/CSS/JS, the real Store/Registry projections over a temporary synthetic AI DB,
the reviewed stream-polish transport prefix for the user page and a private Linux Chromium CDP pipe (stdlib only).
[Impact] Only RFC 5737 documentation addresses and fake credentials are stored; no production DB, model, Strata or
network call is made.
"""
import base64
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import threading
import time

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.serving import make_server

from utils.ai_assistant.policy import canonical
from utils.ai_assistant.providers import Registry
from utils.ai_assistant.reasoning import normalize_profile
from utils.ai_assistant.store import Store

A, B, C = 'a' * 32, 'b' * 32, 'c' * 32
G1, G2 = '1' * 32, '2' * 32

SHOTS = (
    ('providers', 'overview-pending', '개요 · 주소 변경 적용 대기와 진행 단계'),
    ('providers', 'overview-legacy', '개요 · 이전 방식(이름만 변경)으로 생긴 대기'),
    ('providers', 'settings', '연결 설정 · 표시 정보(즉시)와 연결 경로·보안(시험 후 적용)'),
    ('providers', 'models', '서빙 모델 · 요약 행과 펼친 설정'),
    ('providers', 'new-connection', '연결 추가 · 새 연결 입력'),
    ('archive', 'archive', '저장된 모델 기록 · 전체 연결'),
    ('assistant', 'user-models', '사용자 AI 도우미 · 모델 선택 목록'),
    ('providers', 'display-saved', '표시 정보 저장 · 이름이 즉시 반영된 결과'),
)


def seed(store):
    """[Role] Inserts three synthetic connections covering every state shown by the redesigned screens."""
    now = time.time()

    def profile(upstream, adapter, tools, levels):
        return canonical(normalize_profile(upstream, adapter, {'chat': True, 'tools': tools, 'levels': levels, 'evidence': 'synthetic fixture'}))

    with store.db(True) as db:
        db.execute('INSERT INTO ai_resource_groups(id,name) VALUES(?,?),(?,?)', (G1, '연구실 GPU 서버', G2, '사무실 PC'))
        providers = ((A, '연구실 GPU A', 3, 1, 0, now - 95, None), (B, '사무실 PC B', 2, 1, 1, now - 300, None), (C, '예비 노트북 C', 1, 0, 2, now - 86400, None))
        for pid, name, revision, enabled, order, checked, error in providers:
            db.execute('INSERT INTO ai_providers(id,name,revision,enabled,retired,manual,sort_order,last_checked,last_error) VALUES(?,?,?,?,0,0,?,?,?)',
                       (pid, name, revision, enabled, order, checked, error))
        revisions = ((A, 2, 'https://192.0.2.10:8443', 'strata', G1, 'AA11'), (A, 3, 'https://192.0.2.10:8443', 'strata', G1, 'BB22'),
                     (A, 4, 'https://192.0.2.20:8443', 'strata', G1, 'CC33'), (B, 2, 'http://198.51.100.7:8080', 'openai', G2, None),
                     (B, 3, 'http://198.51.100.7:8080', 'openai', G2, None), (C, 1, 'http://198.51.100.9:8080', 'openai', G2, None))
        for pid, revision, url, adapter, group, fingerprint in revisions:
            db.execute('INSERT INTO ai_provider_revisions VALUES(?,?,?,?,?,?,?)', (pid, revision, url, adapter, group, 'fernet:synthetic-not-a-key', now))
            db.execute('INSERT INTO ai_provider_trust(provider,revision,origin,addresses,ca_pem,fingerprint,expires) VALUES(?,?,?,?,?,?,?)',
                       (pid, revision, url, json.dumps([url.split('//')[1].rsplit(':', 1)[0]]), '', (fingerprint * 16)[:64] if fingerprint else None,
                        '2027-06-30T00:00:00+00:00' if fingerprint else None))
        models = (
            # id, provider, upstream, label, published, present, verified, tools, levels, order, context
            ('d1' + '0' * 30, A, 'qwen3.8-flash-next-iq3_s', 'Qwen3.8 Flash Next', 1, 1, 3, True, ['low', 'medium', 'high'], 0, 65536),
            ('d2' + '0' * 30, A, 'gemma-4-26b-a4b-qat-ud-q4_k_xl', 'Gemma 4 26B QAT', 1, 1, 3, False, [], 1, 32768),
            ('d3' + '0' * 30, A, 'qwen3.6-35b-a3b-ud-q5_k_xl', 'Qwen3.6 35B', 1, 1, None, True, [], 2, 32768),
            ('d4' + '0' * 30, A, 'qwen3.8-flash-next-iq2_xs', 'qwen3.8-flash-next-iq2_xs', 0, 1, None, False, [], 3, 4096),
            ('d5' + '0' * 30, A, 'gemma-4-26b-a4b-ud-q4_k_m', 'Gemma 4 26B Q4_K_M', 1, 0, 3, False, [], 4, 32768),
            ('d6' + '0' * 30, A, 'gemma-4-26b-a4b-ud-q3_k_m', 'gemma-4-26b-a4b-ud-q3_k_m', 0, 0, 3, False, [], 5, 4096),
            ('e1' + '0' * 30, B, 'llama-3.3-70b-instruct', 'Llama 3.3 70B', 1, 1, 2, True, [], 0, 65536),
            ('e2' + '0' * 30, B, 'mistral-small-3.1', 'Mistral Small 3.1', 1, 0, 2, False, [], 1, 32768),
            ('f1' + '0' * 30, C, 'phi-4-mini', 'Phi-4 mini', 1, 1, 1, False, [], 0, 16384),
            ('f2' + '0' * 30, C, 'phi-3.5-mini', 'phi-3.5-mini', 0, 0, None, False, [], 1, 4096),
        )
        adapters = {A: 'strata', B: 'openai', C: 'openai'}
        for mid, pid, upstream, label, published, present, verified, tools, levels, order, context in models:
            db.execute('''INSERT INTO ai_provider_models(id,provider,upstream,label,published,present,manual,sort_order,context_tokens,profile,verified_revision,checked)
                VALUES(?,?,?,?,?,?,0,?,?,?,?,?)''', (mid, pid, upstream, label, published, present, order, context,
                                                    profile(upstream, adapters[pid], tools, levels), verified, now - (95 if present else 3 * 86400)))
        db.execute('UPDATE ai_provider_settings SET default_model=?', ('d1' + '0' * 30,))
        # A: real route change (new address + new CA) waiting for probes; one of two published models already passed.
        db.execute('''INSERT INTO ai_provider_candidates(provider,revision,parent,name,enabled,manual,sort_order,generation,discovered,result)
            VALUES(?,4,3,?,1,0,0,1,1,?)''', (A, '연구실 GPU A', '기존 공개 모델의 기능 시험 대기'))
        # A real passing probe records every level it verified; cutover requires the published levels to be covered.
        passed = json.loads(db.execute("SELECT profile FROM ai_provider_models WHERE id=?", ('d1' + '0' * 30,)).fetchone()[0])
        passed = canonical({**passed, 'verified_levels': passed['levels']})
        for mid, upstream, label, proof in (('d1' + '0' * 30, 'qwen3.8-flash-next-iq3_s', 'Qwen3.8 Flash Next', passed),
                                            ('d2' + '0' * 30, 'gemma-4-26b-a4b-qat-ud-q4_k_xl', 'Gemma 4 26B QAT', None),
                                            ('d3' + '0' * 30, 'qwen3.6-35b-a3b-ud-q5_k_xl', 'Qwen3.6 35B', None)):
            db.execute('INSERT INTO ai_candidate_models(provider,id,upstream,label,proof,tested_profile,tested_context) VALUES(?,?,?,?,?,?,?)',
                       (A, mid, upstream, label, proof, 1 if proof else None, 65536 if proof else None))
        # B: what the previous editor left behind after a name-only save: same route, waiting for every published model.
        db.execute('''INSERT INTO ai_provider_candidates(provider,revision,parent,name,enabled,manual,sort_order,generation,discovered,result)
            VALUES(?,3,2,?,1,0,1,1,1,?)''', (B, '사무실 PC B (새 이름)', '기존 공개 모델의 기능 시험 대기'))
        db.execute('INSERT INTO ai_candidate_models(provider,id,upstream,label) VALUES(?,?,?,?)', (B, 'e1' + '0' * 30, 'llama-3.3-70b-instruct', 'Llama 3.3 70B'))


DRIVER = r'''
(function(){
  const shot=window.__shotName, checks=[];
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const wait=async(test,label)=>{for(let i=0;i<800;i++){if(test())return;await sleep(10);}throw Error(label+' timed out');};
  const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
  const $=id=>document.getElementById(id);
  const finish=(status,error)=>{window.__shot=JSON.stringify({status,view:shot,width:innerWidth,theme:'light',checks,error:error||undefined,production_data_used:false});};
  const open=async name=>{const button=[...document.querySelectorAll('#provider-list button')].find(b=>b.querySelector('strong').textContent===name);button.click();await wait(()=>$('provider-heading').textContent.startsWith(name),'open '+name);};
  const tab=async name=>{$('provider-tab-'+name).click();await wait(()=>!$('provider-panel-'+name).hidden,'tab '+name);};
  addEventListener('load',async()=>{
    try{
      if(location.pathname==='/providers'){
        await wait(()=>document.querySelectorAll('#provider-list button').length===3,'connection list');
        assert(document.querySelector('#provider-list').textContent.includes('변경 적용 대기'),'list-shows-pending-badge');
        if(shot==='overview-pending'){await open('연구실 GPU A');
          assert($('provider-steps').children.length===4,'four-steps');
          assert($('provider-steps').textContent.includes('1 / 2 통과'),'probe-progress-1-of-2');
          assert([...$('provider-changes').tBodies[0].rows].some(r=>r.textContent.includes('API 기본 주소')&&r.textContent.includes('192.0.2.20')),'address-change-row');
          assert(!$('provider-candidate').hidden&&$('provider-pending-cancel'),'cancel-button-visible');}
        if(shot==='overview-legacy'){await open('사무실 PC B');
          assert($('provider-candidate-models').textContent.includes('다른 연결 경로·키·인증서가 없습니다'),'legacy-name-only-note');}
        if(shot==='settings'){await open('연구실 GPU A');await tab('settings');
          assert($('provider-display-form').elements.name.value==='연구실 GPU A','display-name-from-active-row');
          assert($('provider-form').elements.base_url.value==='https://192.0.2.20:8443','route-form-shows-pending-address');}
        if(shot==='models'){await open('연구실 GPU A');await tab('models');
          const rows=[...document.querySelectorAll('.provider-model-row')];
          assert(rows.length===4,'four-served-rows-archived-excluded');
          assert(!$('provider-models').textContent.includes('Gemma 4 26B Q4_K_M'),'absent-record-not-in-served-list');
          assert($('provider-archive-note').textContent.includes('2건'),'archive-link-count');
          rows.find(r=>r.textContent.includes('Qwen3.6 35B')).open=true;}
        if(shot==='new-connection'){$('provider-new').click();await wait(()=>$('provider-heading').textContent==='연결 추가','new');
          assert(!$('provider-panel-settings').hidden&&$('provider-tab-overview').disabled,'new-connection-settings-only');}
        if(shot==='display-saved'){await open('사무실 PC B');await tab('settings');
          const input=$('provider-display-form').elements.name;input.value='사무실 PC B · 2층';input.dispatchEvent(new Event('input',{bubbles:true}));
          $('provider-display-save').click();
          await wait(()=>$('provider-dialog').open&&$('provider-dialog-title').textContent.includes('표시 정보 저장 완료'),'saved dialog');
          assert([...document.querySelectorAll('#provider-list strong')].some(n=>n.textContent==='사무실 PC B · 2층'),'list-renamed-immediately');
          assert($('provider-heading').textContent.startsWith('사무실 PC B · 2층'),'heading-renamed-immediately');}
      }
      if(location.pathname==='/archive'){
        await wait(()=>$('archive-table').tBodies[0].rows.length>0,'archive rows');
        assert($('archive-table').tBodies[0].rows.length===4,'four-archived-records');
        assert($('archive-table').textContent.includes('사용자에게 자동 재공개'),'republish-state-shown');
      }
      await sleep(250);finish('pass');
    }catch(error){finish('fail',error.message);}
  });
})();
'''

USER_DRIVER = r'''
    const shotChoices = window.__shotChoices;
    conversations.get(cid).selection_id = shotChoices.default_model;
    const choicesFetch = server.fetch.bind(server);
    server.fetch = async (path, options = {}) => {
        const url = new URL(path, location.origin);
        if (url.pathname === '/api/ai/models') return server.respond({ success: true, ...shotChoices });
        if (url.pathname === '/api/ai/conversations' && (options.method || 'GET') === 'GET')
            return server.respond({ success: true, resume_conversation: url.searchParams.get('view') !== 'trash' ? { ...conversations.get(cid) } : null,
                conversations: [...conversations.values()], next_cursor: null });
        return choicesFetch(path, options);
    };
    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], $ = id => document.getElementById(id);
        const wait = async (test, label) => { for (let i = 0; i < 1500; i++) { if (test()) return; await sleep(10); } throw Error(label + ' timed out'); };
        try {
            await wait(() => $('ai-model').options.length >= 5 && !$('ai-send').disabled, 'model list');
            const texts = [...$('ai-model').options].map(option => option.textContent);
            if (texts.some(text => text.includes('Q4_K_M') || text.includes('Mistral'))) throw Error('absent record offered to users');
            checks.push('absent-records-not-offered');
            const notice = $('ai-unavailable-models');
            if (notice.hidden || !$('ai-model-panel').contains(notice) || notice.getClientRects().length) throw Error('unavailable notice must exist inside the closed model panel');
            checks.push('unavailable-notice-hidden-while-model-panel-closed');
            $('ai-model-settings').open = true;
            await sleep(150);
            if (!notice.getClientRects().length || !notice.textContent.includes('Qwen3.6 35B')) throw Error('unavailable notice must show when the model panel opens');
            checks.push('unavailable-notice-shown-in-open-model-panel');
            // Fixture-only presentation: render the native select as an open list so the screenshot shows every choice.
            $('ai-model').size = $('ai-model').options.length;
            Object.assign($('ai-model').style, { height: 'auto', minHeight: '0', maxHeight: 'none', width: innerWidth > 760 ? '460px' : '100%', overflow: 'hidden' });
            for (let node = $('ai-model').parentElement; node && node.id !== 'ai-model-settings'; node = node.parentElement)
                Object.assign(node.style, { flex: '1 1 100%', maxWidth: 'none', width: '100%', height: 'auto', minWidth: '0' });
            $('ai-model').style.width = '100%'; $('ai-model').style.maxWidth = innerWidth > 760 ? '520px' : '100%';
            await sleep(400);
            window.__shot = JSON.stringify({ status: 'pass', view: 'user-models', width: innerWidth, theme, checks, options: texts, production_data_used: false });
        } catch (error) { window.__shot = JSON.stringify({ status: 'fail', view: 'user-models', width: innerWidth, theme, checks, error: error.message }); }
    });
})();
'''


def capture(url, width):
    """[Role] Opens one page in isolated Chromium over a private CDP pipe and returns (result JSON, PNG bytes).
    Admin pages are captured at full content height; the assistant page is captured at its fitted viewport."""
    incoming, send = os.pipe()
    receive, outgoing = os.pipe()
    child_in = fcntl.fcntl(incoming, fcntl.F_DUPFD_CLOEXEC, 10)
    child_out = fcntl.fcntl(outgoing, fcntl.F_DUPFD_CLOEXEC, 10)
    quiet = os.open(os.devnull, os.O_WRONLY)
    profile = tempfile.TemporaryDirectory(prefix='eq-connection-shot-')
    args = ['/usr/bin/chromium', '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-proxy-server',
            '--disable-background-networking', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', '--user-data-dir=' + profile.name,
            '--remote-debugging-pipe', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', 'about:blank']
    pid = None
    try:
        pid = os.posix_spawn(args[0], args, os.environ, file_actions=[(os.POSIX_SPAWN_DUP2, child_in, 3), (os.POSIX_SPAWN_DUP2, child_out, 4),
                                                                    (os.POSIX_SPAWN_DUP2, quiet, 1), (os.POSIX_SPAWN_DUP2, quiet, 2)], setpgroup=0)
        os.close(incoming); incoming = None
        os.close(outgoing); outgoing = None
        serial, pending = 0, b''

        def call(method, params=None, session=None):
            nonlocal serial, pending
            serial += 1
            message = {'id': serial, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            os.write(send, json.dumps(message).encode() + b'\0')
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if b'\0' not in pending:
                    if not select.select([receive], [], [], max(0, deadline - time.monotonic()))[0]:
                        break
                    chunk = os.read(receive, 1 << 20)
                    if not chunk:
                        raise RuntimeError('isolated Chromium CDP pipe closed')
                    pending += chunk
                    continue
                raw, pending = pending.split(b'\0', 1)
                value = json.loads(raw)
                if value.get('id') == serial:
                    if 'error' in value:
                        raise RuntimeError(str(value['error']))
                    return value.get('result', {})
            raise TimeoutError('CDP reply timed out: ' + method)

        target = call('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        call('Page.enable', session=session)
        mobile = width <= 760
        metrics = {'width': width, 'height': 860 if mobile else 1000, 'deviceScaleFactor': 2 if mobile else 1, 'mobile': mobile}
        call('Emulation.setDeviceMetricsOverride', metrics, session)
        if mobile:
            call('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5}, session)
        call('Page.navigate', {'url': url}, session)
        deadline = time.monotonic() + 40
        result = None
        while time.monotonic() < deadline:
            value = call('Runtime.evaluate', {'expression': 'window.__shot||""', 'returnByValue': True}, session)['result'].get('value')
            if value:
                result = json.loads(value)
                break
            time.sleep(.05)
        if result is None:
            result = {'status': 'fail', 'error': 'screen did not finish'}
        if '/assistant' not in url:
            height = call('Runtime.evaluate', {'expression': 'Math.ceil(document.documentElement.scrollHeight)', 'returnByValue': True}, session)['result']['value']
            call('Emulation.setDeviceMetricsOverride', {**metrics, 'height': min(max(height, metrics['height']), 6000)}, session)
            time.sleep(.4)
        shot = call('Page.captureScreenshot', {'format': 'png'}, session)
        return result, base64.b64decode(shot['data'])
    finally:
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        for descriptor in (incoming, send, receive, outgoing, child_in, child_out, quiet):
            if descriptor is not None:
                os.close(descriptor)
        profile.cleanup()


def run_browser(project, assets):
    """[Role] Serves the candidate screens over loopback from a seeded temporary AI DB and captures every example."""
    directory = tempfile.TemporaryDirectory(prefix='eq-connection-redesign-')
    store = Store(Path(directory.name) / 'assistant.sqlite3')
    seed(store)
    registry = Registry(store, {'USER_AI_STRATA_URL': 'http://192.0.2.1:8080', 'USER_AI_ALLOWED_ENDPOINTS': '[]', 'USER_AI_MODEL': 'unused'})
    transport = assets.get('tests/test_stream_polish_browser.js') or (Path(project) / 'tests/test_stream_polish_browser.js').read_text(encoding='utf-8-sig')
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if transport.count(anchor) != 1:
        raise ValueError('reviewed stream transport bootstrap changed')
    app = Flask('connection_redesign_fixture', static_folder=None)
    app.secret_key = 'synthetic-connection-redesign-fixture-only'
    app.jinja_loader = ChoiceLoader([DictLoader({k.removeprefix('templates/'): v for k, v in assets.items() if k.startswith('templates/')}),
                                     FileSystemLoader(Path(project) / 'templates')])

    def page(template, script_anchor, script, user):
        document = render_template(template, user=user, assistant_csrf='fixture-csrf', csrf_token='fixture-csrf')
        document = document.replace('src="https://cdn.tailwindcss.com"', 'src="/static/js/tailwindcss.js"')
        document = document.replace('<head>', '<head><script>localStorage.theme="light";</script>', 1)
        if script_anchor not in document:
            raise ValueError('fixture script anchor missing: ' + script_anchor)
        document = document.replace(script_anchor, '<script>' + script.replace('</script', '<\\/script') + '</script>' + script_anchor)
        response = Response(document, content_type='text/html; charset=utf-8')
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'none'; img-src 'self' data:"
        return response

    @app.get('/static/<path:filename>', endpoint='static')
    def static_file(filename):
        key = 'static/' + filename
        if key in assets:
            return Response(assets[key], content_type='text/css' if filename.endswith('.css') else 'application/javascript')
        return send_from_directory(Path(project) / 'static', filename)

    admin = {'NickName': '격리 관리자', 'Role': 'admin'}

    @app.get('/providers')
    def providers_page():
        return page('equipment_ai_providers.html', '<script src="/static/js/equipment_ai_providers.js"',
                    'window.__shotName=' + json.dumps(request.args.get('shot', '')) + ';' + DRIVER, admin)

    @app.get('/archive')
    def archive_page():
        return page('equipment_ai_model_archive.html', '<script src="/static/js/equipment_ai_model_archive.js"', 'window.__shotName="archive";' + DRIVER, admin)

    @app.get('/assistant')
    def assistant_page():
        script = 'window.__shotChoices=' + json.dumps(registry.choices()) + ';\n' + transport.split(anchor, 1)[0] + USER_DRIVER
        return page('equipment_ai.html', '<script src="/static/js/equipment_ai.js"', script, {'NickName': '격리 사용자', 'Role': 'user'})

    @app.get('/api/admin/ai/providers')
    def admin_list():
        return jsonify(success=True, **registry.admin_list())

    @app.post('/api/admin/ai/providers/<pid>/display')
    def admin_display(pid):
        return jsonify(success=True, id=registry.display(pid, request.get_json()), applied='immediate')

    @app.get('/api/admin/ai/models/archive')
    def admin_archive():
        return jsonify(success=True, **registry.archive(request.args.get('provider') or None))

    @app.get('/api/check_session')
    def session_status():
        return jsonify(valid=True)

    @app.get('/api/user_settings')
    def preferences():
        return jsonify(success=True, settings={'theme': 'light'})

    @app.post('/logout')
    def logout():
        return Response('', status=204)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for width in (1440, 384):
            for route, name, caption in SHOTS:
                url = 'http://127.0.0.1:' + str(server.server_port) + '/' + route + ('?shot=' + name if route == 'providers' else '')
                result, png = capture(url, width)
                result.update(view='connection-' + name, caption=caption, width=width, screenshot=base64.b64encode(png).decode())
                results.append(result)
            # Restore the renamed connection so the next width starts from identical synthetic data.
            registry.display(B, {'name': '사무실 PC B', 'sort_order': 1, 'manual': False, 'revision': 2})
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        directory.cleanup()
    return results
