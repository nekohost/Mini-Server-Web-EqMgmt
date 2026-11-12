import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {setImmediate as settle} from 'node:timers/promises';
import vm from 'node:vm';

const read = file => readFileSync(new URL('../' + file, import.meta.url), 'utf8');
const timer = read('static/js/session_timer.js');
const template = read('templates/access_logs.html');
const logs = template.match(/<script>([\s\S]*?)<\/script>/)[1];
const logPoll = {'X-Access-Log-Poll': '1'};
const aiPoll = {'X-Assistant-Poll': '1'};

async function openPage({assistant = false} = {}) {
    let now = 0;
    let reloads = 0;
    const requests = [];
    const replies = new Map();
    const alerts = [];
    const ready = [];
    const events = new EventTarget();
    const intervals = new Map();
    let nextId = 0;
    const elements = new Map();
    const address = new URL(assistant ? 'https://fixture.test/assistant' : 'https://fixture.test/access_logs');
    const location = {
        get href() { return address.href; },
        set href(value) { address.href = new URL(value, address).href; },
        get origin() { return address.origin; },
        get search() { return address.search; },
        reload() { reloads++; },
    };
    function element(id) {
        if (!elements.has(id)) {
            elements.set(id, Object.assign(new EventTarget(), {
                value: '', dataset: {}, style: {}, classList: {add() {}, remove() {}},
                isConnected: true, querySelector: () => null,
                setAttribute(name, value) { this[name] = value; },
            }));
        }
        return elements.get(id);
    }
    const document = {
        baseURI: location.href,
        readyState: 'loading',
        documentElement: element('html'),
        getElementById: id => id === 'equipment-ai' && !assistant ? null : element(id),
        querySelectorAll: () => [],
        addEventListener(name, fn) { if (name === 'DOMContentLoaded') ready.push(fn); },
    };
    const page = vm.createContext({
        document, location, URL, URLSearchParams, Headers, Request, AbortController, console,
        addEventListener: events.addEventListener.bind(events), dispatchEvent: events.dispatchEvent.bind(events),
        alert: message => alerts.push(message),
        Date: {now: () => now}, localStorage: {theme: 'light'},
        matchMedia: () => ({addEventListener() {}}), getCSRFToken: () => 'fixture-csrf',
        setTimeout() {}, clearTimeout() {},
        setInterval(fn, delay) { intervals.set(++nextId, {fn, delay}); return nextId; },
        clearInterval(id) { intervals.delete(id); },
        async fetch(input, init) {
            const request = new Request(input instanceof Request ? input : new URL(input, document.baseURI), init);
            const url = new URL(request.url);
            const call = {url, method: request.method, headers: request.headers, body: init?.body};
            requests.push(call);
            const reply = replies.get(url.pathname) ?? [200, {}];
            const [status, body] = typeof reply === 'function' ? reply(call) : reply;
            return {ok: status >= 200 && status < 300, status, json: async () => body};
        },
    });
    page.window = page;
    vm.runInContext(timer, page);
    vm.runInContext(assistant ? read('static/js/equipment_ai_polish.js') : logs, page);
    for (const fn of ready) await fn();
    await settle();
    return {
        page, element, location, requests, replies, alerts, badge: element('session-timer-badge'),
        get reloads() { return reloads; },
        async advance(seconds) {
            for (let second = 0; second < seconds; second++) {
                now += 1000;
                for (const {fn, delay} of intervals.values()) {
                    if (now % delay === 0) fn();
                }
                await settle();
            }
        },
    };
}

test('initial and five-second list, stats and session reads leave the original deadline intact', async () => {
    const view = await openPage();
    await view.advance(1800);
    assert.equal(view.badge.dataset.sessionState, 'expired');
    for (const path of ['/api/access_logs', '/api/access_logs/stats']) {
        const reads = view.requests.filter(r => r.url.pathname === path);
        assert.equal(reads.length, 361, path);
        assert.ok(reads.every(r => r.method === 'GET' && r.headers.get('X-Access-Log-Poll') === '1'));
    }
    const checks = view.requests.filter(r => r.url.pathname === '/api/check_session');
    assert.equal(checks.length, 360);
    assert.ok(checks.every(r => r.method === 'GET'));
    // The cookie may outlive the local clock by a tick. Reloading the authenticated page would renew it.
    assert.equal(view.reloads, 0);
    view.replies.set('/api/check_session', [401, {reason: 'session_expired'}]);
    await view.advance(5);
    assert.equal(view.location.href, 'https://fixture.test/login?error=session_expired');
});

test('manual search, pagination, statistics period and the extend button renew activity', async () => {
    const view = await openPage();
    const {page, badge} = view;
    view.element('filterIp').value = '192.0.2.18';
    for (const [action, path, key, value] of [
        [() => page.handleSearch({preventDefault() {}}), '/api/access_logs', 'ip', '192.0.2.18'],
        [() => page.goToPage(3), '/api/access_logs', 'page', '3'],
        [() => page.setStatsPeriod('all'), '/api/access_logs/stats', 'period', 'all'],
    ]) {
        await view.advance(2);
        assert.match(badge.innerHTML, /29분/);
        action();
        await settle();
        const request = view.requests.at(-1);
        assert.equal(request.url.pathname, path);
        assert.equal(request.url.searchParams.get(key), value);
        assert.equal(request.headers.has('X-Access-Log-Poll'), false);
        assert.match(badge.innerHTML, /30분/);
    }
    await view.advance(2);
    view.replies.set('/api/extend_session', [200, {success: false}]);
    badge.dispatchEvent(new Event('click'));
    await settle();
    assert.match(badge.innerHTML, /29분/);
    view.replies.set('/api/extend_session', [200, {success: true}]);
    badge.dispatchEvent(new Event('click'));
    await settle();
    const extension = view.requests.at(-1);
    assert.equal(extension.url.pathname, '/api/extend_session');
    assert.equal(extension.method, 'POST');
    assert.equal(extension.headers.get('X-CSRFToken'), 'fixture-csrf');
    assert.equal(extension.headers.has('X-Access-Log-Poll'), false);
    assert.match(badge.innerHTML, /30분/);
});

test('poll markers apply to the effective GET and its own route only', async () => {
    const view = await openPage({assistant: true});
    await view.advance(60);
    view.replies.set('/api/ai/status', [200, {success: true, state: 'ready', scope: 'job', checked_at: 60, expires_at: 90}]);
    view.page.dispatchEvent(Object.assign(new Event('assistant-status-context'), {detail: {jobId: 'fixture'}}));
    await settle();
    const poll = view.requests.at(-1);
    assert.equal(poll.url.pathname + poll.url.search, '/api/ai/status?job_id=fixture');
    assert.equal(poll.headers.get('X-Assistant-Poll'), '1');
    assert.equal(view.element('ai-header-status').dataset.state, 'ready');
    assert.match(view.badge.innerHTML, /29분/);
    const job = new Request(new URL('/api/ai/jobs/fixture', view.location.href), {headers: aiPoll});
    await view.page.fetch(job);
    await view.page.fetch('/api/check_session');
    const status = view.requests.filter(r => r.url.pathname === '/api/check_session');
    assert.ok(status.some(r => r.headers.get('X-Assistant-Poll') === '1'));
    assert.match(view.badge.innerHTML, /29분/);
    const list = new Request(new URL('/api/access_logs?page=2', view.location.href), {headers: logPoll});
    await view.page.fetch(list);
    await view.page.fetch('/api/access_logs/stats', {headers: Object.entries(logPoll).values()});
    assert.equal(view.requests.at(-1).headers.get('X-Access-Log-Poll'), '1');
    await view.page.fetch('https://other.test/api/me');
    assert.match(view.badge.innerHTML, /29분/);
    for (const [input, init] of [
        [list, {headers: {}}],
        [list, {method: 'POST'}],
        ['/api/access_logs/cleanup', {method: 'POST', headers: logPoll}],
        ['/api/access_logs/123/payload', {headers: logPoll}],
        ['/api/access_logs/stats', {headers: aiPoll}],
        ['/api/access_logs/stats', {headers: {'X-Access-Log-Poll': '0'}}],
        ['/api/me?next=/api/check_session', {headers: logPoll}],
        ['/api/ai/jobs/fixture/cancel', {method: 'POST', headers: aiPoll}],
    ]) {
        await view.advance(1);
        await view.page.fetch(input, init);
        assert.match(view.badge.innerHTML, /30분/);
    }
});

test('cleanup sends authenticated count, chunk and finish POSTs followed by ordinary reads', async () => {
    const view = await openPage();
    view.replies.set('/api/access_logs/cleanup', call => {
        const result = {
            count: {operation_id: 'fixture-op', total_count: 1},
            delete_chunk: {deleted_count: 1},
            finish: {deleted_count: 1, remaining_count: 0},
        }[JSON.parse(call.body).step];
        return [200, {status: 'success', ...result}];
    });
    await view.advance(1);
    const start = view.requests.length;
    await view.page.executeCleanup('all');
    await settle();
    const calls = view.requests.slice(start);
    assert.deepEqual(calls.map(r => [r.method, r.url.pathname]), [
        ['POST', '/api/access_logs/cleanup'], ['POST', '/api/access_logs/cleanup'], ['POST', '/api/access_logs/cleanup'],
        ['GET', '/api/access_logs/stats'], ['GET', '/api/access_logs'],
    ]);
    const steps = calls.slice(0, 3);
    assert.deepEqual(steps.map(r => JSON.parse(r.body)), [
        {action: 'all', step: 'count'}, {action: 'all', step: 'delete_chunk', operation_id: 'fixture-op'},
        {action: 'all', step: 'finish', operation_id: 'fixture-op'},
    ]);
    assert.ok(steps.every(r => r.headers.get('X-CSRFToken') === 'fixture-csrf' && r.headers.get('Content-Type') === 'application/json'));
    assert.ok(calls.every(r => !r.headers.has('X-Access-Log-Poll')));
    assert.match(view.alerts.at(-1), /1건을 삭제/);
    assert.match(view.badge.innerHTML, /30분/);
});

test('a 401 from an automatic log read still reloads the page', async () => {
    const view = await openPage();
    view.replies.set('/api/access_logs', [401, {}]);
    await view.advance(5);
    assert.equal(view.reloads, 1);
    assert.match(view.badge.innerHTML, /29분/);
});

for (const [status, reason] of [[401, 'session_expired'], [401, 'concurrent_login'], [503, 'maintenance']]) {
    test(`periodic session check redirects on ${reason}`, async () => {
        const view = await openPage();
        view.replies.set('/api/check_session', [status, {reason}]);
        await view.advance(5);
        assert.equal(view.location.href, 'https://fixture.test/login?error=' + reason);
        assert.match(view.badge.innerHTML, /29분/);
    });
}
