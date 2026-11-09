"""Capture actual candidate HTML, Flask first-turn API and temporary SQLite across held first paints."""
import argparse
import base64
import json
import logging
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import uuid

import requests
from flask import jsonify, request
from werkzeug.serving import make_server

from test_ai_conversation_entry import EntryTests


class Browser:
    """Private ChromeDriver session with a fresh profile; all browser traffic stays on loopback."""
    def __init__(self, tmp, width, height):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:' + str(port)
        self.http = requests.Session()
        self.http.trust_env = False
        self.proc = subprocess.Popen(['/usr/bin/chromedriver', '--port=' + str(port)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.sid = ''
        try:
            for _ in range(100):
                try:
                    if self.http.get(self.base + '/status', timeout=1).ok:
                        break
                except requests.ConnectionError:
                    time.sleep(.05)
            args = ['--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--no-proxy-server',
                    '--disable-background-networking', '--disable-renderer-backgrounding', '--lang=ko-KR',
                    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', '--user-data-dir=' + tmp]
            result = self.call('POST', '/session', {'capabilities': {'alwaysMatch': {'browserName':'chrome',
                'pageLoadStrategy':'eager', 'goog:chromeOptions': {'binary':'/usr/bin/chromium','args':args}}}})
            self.sid = '/session/' + result['sessionId']
            self.cdp('Emulation.setDeviceMetricsOverride', dict(width=width, height=height, deviceScaleFactor=1, mobile=width < 600))
            if width < 600:
                self.cdp('Emulation.setTouchEmulationEnabled', dict(enabled=True, maxTouchPoints=5))
        except BaseException:
            self.close()
            raise

    def call(self, method, path, data=None):
        """Execute WebDriver commands and surface their actual failure reason."""
        response = self.http.request(method, self.base + path, json=data, timeout=40)
        result = response.json()['value']
        if not response.ok:
            raise RuntimeError(result.get('message', str(result))[:900])
        return result

    def cdp(self, method, params):
        return self.call('POST', self.sid + '/goog/cdp/execute', dict(cmd=method, params=params))

    def js(self, body):
        return self.call('POST', self.sid + '/execute/sync', dict(script=body, args=[]))

    def until(self, expr):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.js('return Boolean(' + expr + ')'):
                return
            time.sleep(.05)
        raise AssertionError((expr, self.js("return [location.pathname,document.body.innerText.slice(0,850),window.entryProbe?.errors]")))

    def snap(self, folder, name):
        png = self.cdp('Page.captureScreenshot', {'format':'png','captureBeyondViewport':False})['data']
        (folder/(name + '.png')).write_bytes(base64.b64decode(png))

    def close(self):
        try:
            if self.sid:
                self.call('DELETE', self.sid)
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.http.close()


MONITOR = """
window.byId = id => document.getElementById(id);
window.shown = node => Boolean(node && !node.hidden && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
window.entryProbe = { frames: 0, loadingFrames: 0, welcomeFrames: 0, newTitleFrames: 0, falseEmptyFrames: 0, detailsReturned: 0, observe: true, errors: [] };
const originalFetch = window.fetch.bind(window);
window.fetch = async (path, options) => {
    const response = await originalFetch(path, options);
    if (new URL(response.url).pathname.endsWith('/messages')) entryProbe.detailsReturned++;
    return response;
};
addEventListener('error', e => { if (e.message) entryProbe.errors.push(e.message); });
function sample() {
    const p=entryProbe, root=byId('equipment-ai');
    if (root && byId('ai-welcome') && p.observe) {
        p.frames++; if (root.dataset.entry === 'loading') p.loadingFrames++;
        if (shown(byId('ai-welcome'))) p.welcomeFrames++;
        if (shown(byId('ai-title')) && /새로운 대화|새 대화/.test(byId('ai-title').textContent)) p.newTitleFrames++;
        if (shown(byId('ai-list-empty'))) p.falseEmptyFrames++;
    }
    requestAnimationFrame(sample);
}
requestAnimationFrame(sample);
"""


def run(width, height, theme, output):
    """Hold authenticated GETs separately, capture each visible phase, then lose an actual committed response."""
    case = EntryTests()
    case.setUp()
    fx = case.fx
    folder = output / f'{width}-{theme}'
    folder.mkdir(parents=True, exist_ok=True)
    gate = {'list':threading.Event(), 'body':threading.Event()}
    reached = {name:threading.Event() for name in gate}
    writes = []
    flags = dict(block=True, lose=False, reject_list=False, reject_models=False, reject_one_detail=False)
    server = browser = thread = None
    try:
        @fx.app.get('/api/user_settings')
        def prefs():
            return jsonify(success=True, settings={'theme':theme, 'layout_skin':'standard', 'ai_enter_action':'send'})

        @fx.app.before_request
        def delays():
            path = request.path
            if request.method == 'POST' and path.startswith('/api/ai/'):
                writes.append(path)
            if path == '/api/ai/models' and flags['reject_models']:
                return jsonify(success=False, message='모델 목록 시험 오류'), 503
            if request.method == 'GET' and path == '/api/ai/conversations' and request.args.get('resume') == '1':
                if flags['reject_list']:
                    return jsonify(success=False, message='대화 목록 시험 오류'), 503
                phase = 'list'
            elif request.method == 'GET' and path.endswith('/messages'):
                if flags['reject_one_detail']:
                    flags['reject_one_detail'] = False
                    return jsonify(success=False, message='본문 조회 시험 오류'), 503
                phase = 'body'
            else:
                return None
            if flags['block']:
                reached[phase].set()
                if not gate[phase].wait(30):
                    raise TimeoutError(phase)
            return None

        @fx.app.after_request
        def local_assets_and_lost_ack(response):
            if request.path == '/assistant' and response.mimetype == 'text/html':
                response.set_data(response.get_data().replace(b'https://cdn.tailwindcss.com', b'/static/js/tailwindcss.js'))
            if request.path.endswith('/first-turn') and response.status_code == 202 and flags['lose']:
                flags['lose'] = False
                response.status_code = 502
                response.set_data('')  # The app committed. The gateway lost the JSON acknowledgement.
            return response

        seed = case.send(content='보유 장비 점검 내역').get_json()
        assert seed['conversation_id']
        fx.finish(fx.claim(), content='노트북과 모니터의 점검 내역을 확인했습니다.')
        before = case.counts()
        assert before == (1, 1, 1, 1)
        writes.clear()
        server = make_server('127.0.0.1', 0, fx.app, threaded=True)
        base = 'http://127.0.0.1:' + str(server.server_port)
        fx.app.config.update(USER_AI_PUBLIC_ORIGIN=base, SESSION_COOKIE_SECURE=False)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        with tempfile.TemporaryDirectory(prefix='eq-entry-browser-') as tmp:
            browser = Browser(tmp, width, height)
            try:
                browser.cdp('Network.setCookie', dict(name='session', value=case.client.get_cookie('session').value, url=base, path='/'))
                browser.cdp('Page.addScriptToEvaluateOnNewDocument', {'source':MONITOR})
                url_cmd = browser.sid + '/url'
                browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                assert reached['list'].wait(10)
                browser.until("entryProbe.loadingFrames >= 3 && window.userSettings?.theme === '" + theme + "'")
                browser.snap(folder,'01-list-pending')
                gate['list'].set()
                assert reached['body'].wait(10)
                browser.until("shown(byId('ai-entry')) && !shown(byId('ai-welcome'))")
                browser.snap(folder,'02-body-pending')
                gate['body'].set()
                browser.until("byId('equipment-ai').dataset.entry === 'ready' && byId('ai-messages').innerText.includes('점검 내역을 확인') && !byId('ai-send').disabled")
                browser.snap(folder,'03-existing')
                metrics = browser.js("entryProbe.observe=false;return {...entryProbe,width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth-innerWidth,dark:document.documentElement.classList.contains('dark')}")
                assert metrics['width'] == width and metrics['height'] == height and metrics['overflow'] <= 1 and metrics['dark'] == (theme == 'dark'), metrics
                assert metrics['frames'] >= 3 and metrics['loadingFrames'] >= 3 and all(metrics[k] == 0 for k in ['welcomeFrames','newTitleFrames','falseEmptyFrames']), metrics
                assert not metrics['errors'], metrics
                flags['block'] = False
                if width < 600:
                    browser.js("byId('ai-menu-toggle').click()")
                browser.js("byId('ai-new').click();byId('ai-new').click();")
                browser.until("shown(byId('ai-welcome')) && !byId('ai-send').disabled")
                browser.snap(folder,'04-unsaved')
                browser.js("document.querySelector('[data-prompt]').click(); byId('ai-level').dispatchEvent(new Event('change'));")
                assert case.counts() == before and writes == [], (case.counts(), writes)
                browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                browser.until("byId('equipment-ai').dataset.entry === 'ready' && !byId('ai-send').disabled")
                assert case.counts() == before and writes == []
                browser.js("byId('ai-new').click();byId('ai-input').value=' ';byId('ai-form').requestSubmit()")
                assert case.counts() == before and writes == []
                flags['lose'] = True
                browser.js("byId('ai-input').value='첫 전송 점검';byId('ai-form').requestSubmit();byId('ai-form').requestSubmit();byId('ai-send').click()")
                browser.until("shown(byId('ai-first-uncertain')) && !byId('ai-first-retry').disabled")
                assert len(writes) == 1 and case.counts() == (2, 2, 2, 2), (writes, case.counts())
                flags['reject_one_detail'] = True
                browser.js("byId('ai-input').value='다음에 보낼 초안';byId('ai-input').dispatchEvent(new Event('input'));byId('ai-first-retry').click();byId('ai-first-retry').click()")
                browser.until("byId('equipment-ai').dataset.entry === 'error' && shown(byId('ai-entry-retry')) && byId('ai-send').disabled")
                browser.js("byId('ai-entry-retry').click()")
                browser.until("byId('equipment-ai').dataset.entry === 'ready' && byId('ai-title').textContent === '첫 전송 점검' && byId('ai-input').value === '다음에 보낼 초안'")
                browser.snap(folder,'05-first-accepted')
                assert writes == [case.url, case.url] and case.counts() == (2, 2, 2, 2)
                browser.js("byId('ai-new').click()")
                with case.store.db() as db:
                    assert db.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0] == 1
                flags['reject_list'] = True
                browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                browser.until("byId('equipment-ai').dataset.entry==='error' && shown(byId('ai-entry-retry')) && !shown(byId('ai-welcome'))")
                flags['reject_list'] = False
                browser.js("byId('ai-entry-retry').click()")
                browser.until("byId('equipment-ai').dataset.entry==='ready' && byId('ai-title').textContent==='첫 전송 점검'")
                flags['reject_models'] = True
                browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                browser.until("byId('equipment-ai').dataset.entry==='ready' && byId('ai-notice').textContent.includes('모델 목록 시험 오류') && byId('ai-send').disabled")
                assert writes == [case.url, case.url] and case.counts() == (2, 2, 2, 2)
                result = dict(status='pass', width=width, height=height, theme=theme, frames=metrics,
                    before_send=dict(new_conversations=0, new_user_messages=0, new_jobs=0, writes=0),
                    after_duplicate_and_lost_ack=dict(new_conversations=1, new_user_messages=1, new_assistant_placeholders=1, new_jobs=1, first_requests=len(writes)),
                    list_retry=True, detail_retry_without_resend=True, history_with_failed_inventory=True, next_draft_preserved=True, queued_work_survived_navigation=True)
                if theme == 'light':
                    flags.update(reject_models=False, block=True)
                    gate['body'].clear()
                    reached['body'].clear()
                    browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                    assert reached['body'].wait(10)
                    browser.js("byId('ai-new').click();byId('ai-input').value='다른 대화를 선택한 뒤의 초안'")
                    gate['body'].set()
                    browser.until("entryProbe.detailsReturned && byId('equipment-ai').dataset.entry==='draft' && !byId('ai-send').disabled")
                    assert browser.js("return byId('ai-input').value==='다른 대화를 선택한 뒤의 초안' && shown(byId('ai-welcome')) && !byId('ai-messages').childElementCount")
                    gate['body'].clear()
                    reached['body'].clear()
                    browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                    assert reached['body'].wait(10)
                    with case.store.db() as db:
                        latest = db.execute("SELECT id,lifecycle_revision FROM conversations WHERE title='첫 전송 점검'").fetchone()
                    fx.headers['Origin'] = base
                    moved = case.client.post('/api/ai/conversations/'+latest['id']+'/trash', headers=fx.headers,
                        json=dict(lifecycle_revision=latest['lifecycle_revision'], operation_id=uuid.uuid4().hex))
                    assert moved.status_code == 200, moved.get_json()
                    gate['body'].set()
                    browser.until("byId('equipment-ai').dataset.entry==='ready' && byId('ai-title').textContent==='보유 장비 점검 내역'")
                    assert browser.js("return entryProbe.welcomeFrames===0 && entryProbe.detailsReturned>=2")
                    flags['block'] = False
                    fx.login(3)
                    browser.cdp('Network.setCookie', dict(name='session', value=case.client.get_cookie('session').value, url=base, path='/'))
                    browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                    browser.until("byId('equipment-ai').dataset.entry==='draft' && shown(byId('ai-welcome'))")
                    if width < 600:
                        browser.js("byId('ai-menu-toggle').click()")
                    browser.until("shown(byId('ai-list-empty'))")
                    assert not browser.js("return document.querySelector('#ai-conversations .ai-conversation') || byId('ai-messages').childElementCount")
                    legacy = fx.conversation()
                    rows = case.counts()
                    browser.call('POST', url_cmd, dict(url=base + '/assistant'))
                    browser.until("byId('equipment-ai').dataset.entry==='draft' && byId('ai-conversations').childElementCount===1")
                    if width < 600:
                        browser.js("byId('ai-menu-toggle').click()")
                    browser.js("document.querySelector('#ai-conversations .ai-conversation').click()")
                    browser.until("byId('equipment-ai').dataset.entry==='ready' && !byId('ai-send').disabled")
                    browser.js("byId('ai-input').value='기존 빈 대화에 쓰기';byId('ai-form').requestSubmit()")
                    browser.until("byId('ai-title').textContent==='기존 빈 대화에 쓰기'")
                    assert writes[-1] == '/api/ai/conversations/' + legacy + '/turns'
                    assert case.counts() == (rows[0], rows[1]+1, rows[2]+1, rows[3]+1)
                    result.update(explicit_draft_wins_delayed_detail=True, recover_if_trashed_during_load=True,
                        empty_owner_isolation=True, legacy_empty_reused=True)
                return result
            finally:
                browser.close()
    finally:
        for event in gate.values():
            event.set()
        if server:
            server.shutdown()
            thread.join(timeout=4)
            server.server_close()
        fx.doCleanups()


if __name__ == '__main__':
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--width', type=int, required=True, choices=[384,1440])
    parser.add_argument('--theme', choices=['light','dark'], required=True)
    args = parser.parse_args()
    result = run(args.width, 860 if args.width == 384 else 900, args.theme, args.directory)
    path = args.directory/f'{args.width}-{args.theme}'/'results.json'
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
