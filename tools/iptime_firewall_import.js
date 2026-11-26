/* ipTIME 방화벽 페이지의 로그인 세션에서 실행하는 Chrome/Edge DevTools Snippet. */
(() => {
    'use strict';

    const endpoint = '/cgi/service.cgi';
    const maxFileBytes = 16 * 1024;

    function ipNumber(ip) {
        if (typeof ip !== 'string' || !/^(0|[1-9]\d{0,2})(\.(0|[1-9]\d{0,2})){3}$/.test(ip)) return null;
        const bytes = ip.split('.').map(Number);
        if (bytes.some(byte => byte > 255)) return null;
        return bytes.reduce((value, byte) => value * 256 + byte, 0);
    }

    const excluded = [
        ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8], ['169.254.0.0', 16],
        ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24], ['192.88.99.0', 24], ['192.168.0.0', 16],
        ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24], ['224.0.0.0', 3],
    ].map(([ip, prefix]) => {
        const start = ipNumber(ip);
        return [start, start + 2 ** (32 - prefix)];
    });

    function parseBlocklist(text) {
        if (typeof text !== 'string' || text.length > maxFileBytes) throw new Error('TXT 파일 크기를 확인해 주세요.');
        const addresses = new Set();
        for (const [index, line] of text.split(/\r?\n/).entries()) {
            const ip = line.trim();
            if (!ip) continue;
            const number = ipNumber(ip);
            if (number === null || excluded.some(([start, end]) => number >= start && number < end)) {
                throw new Error(`${index + 1}번째 줄에 공인 IPv4 주소 하나를 입력해 주세요.`);
            }
            addresses.add(ip);
        }
        if (!addresses.size || addresses.size > 500) throw new Error('TXT의 주소 수는 1~500개여야 합니다.');
        return [...addresses];
    }

    function blockPayload(ip, priority) {
        return {method: 'firewall/add', params: {
            name: `차단 ${ip}`, type: 'net', active: true, priority, policy: 'drop',
            filter: {protocol: {}, internal: {}, external: {ip: {start: ip}}},
            direction: {inbound: true, outbound: false},
            timer: {wday: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], hours: {start: '00:00', end: '00:00'}},
        }};
    }

    function covers(rule, ip) {
        const range = rule.filter?.external?.ip;
        if (rule.type !== 'net' || rule.direction?.inbound !== true || !range) return false;
        const start = ipNumber(range.start);
        const end = range.end ? ipNumber(range.end) : start;
        const address = ipNumber(ip);
        return start !== null && end !== null && address >= start && address <= end;
    }

    function allValues(filter, address = false) {
        const keys = Object.keys(filter || {});
        return address ? keys.length === 1 && keys[0] === 'ip' : !keys.length;
    }

    function alwaysBlocked(rule, ip) {
        return covers(rule, ip) && rule.active === true && rule.running === true
            && rule.policy === 'drop' && !rule.timer
            && allValues(rule.filter.internal) && allValues(rule.filter.protocol) && allValues(rule.filter.external, true);
    }

    function plan(rules, addresses) {
        const result = {waiting: [], existing: [], conflicts: []};
        for (const ip of addresses) {
            const prior = rules.filter(rule => covers(rule, ip)).sort((a, b) => a.priority - b.priority)[0];
            if (!prior) result.waiting.push(ip);
            else if (alwaysBlocked(prior, ip)) result.existing.push(ip);
            else result.conflicts.push(ip);
        }
        return result;
    }

    async function call(method, fetcher, params) {
        const response = await fetcher(endpoint, {
            method: 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store',
            headers: {'Content-Type': 'application/json; charset=utf-8'},
            body: JSON.stringify(params ? {method, params} : {method}),
            signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error(`공유기가 HTTP ${response.status}으로 응답했습니다.`);
        const data = await response.json().catch(() => null);
        if (!data || data.error || !Object.hasOwn(data, 'result')) {
            throw new Error('ipTIME 응답을 확인할 수 없습니다. 방화벽 화면의 로그인 상태를 확인해 주세요.');
        }
        return data.result;
    }

    function checkedRules(rows) {
        if (!Array.isArray(rows) || rows.some(rule => !Number.isSafeInteger(rule?.priority) || rule.priority < 1)
            || new Set(rows.map(rule => rule.priority)).size !== rows.length) {
            throw new Error('공유기 규칙 목록 형식을 확인해 주세요.');
        }
        return rows;
    }

    const readRules = async fetcher => checkedRules(await call('firewall/get', fetcher));
    const stable = object => JSON.stringify(object, (key, value) => (
        value && typeof value === 'object' && !Array.isArray(value)
            ? Object.fromEntries(Object.keys(value).sort().map(name => [name, value[name]])) : value
    ));
    const snapshot = rows => stable([...rows].sort((a, b) => a.priority - b.priority));

    async function register(fetcher, expected, addresses, onProgress = () => {}) {
        let rows = await readRules(fetcher);
        if (snapshot(expected) !== snapshot(rows)) {
            throw new Error('미리보기 이후 규칙이 바뀌었습니다. TXT를 다시 선택해 주세요.');
        }
        const added = [];
        for (const ip of addresses) {
            const priority = 1 + Math.max(0, ...rows.map(row => row.priority));
            const request = blockPayload(ip, priority);
            const updated = checkedRules(await call(request.method, fetcher, request.params));
            const saved = updated.find(row => row.priority === priority);
            const oldRows = updated.filter(row => row.priority !== priority);
            if (updated.length !== rows.length + 1 || !saved || !alwaysBlocked(saved, ip)
                || saved.direction.outbound !== false || saved.filter.external.ip.start !== ip
                || (saved.filter.external.ip.end && saved.filter.external.ip.end !== ip) || saved.name !== request.params.name
                || snapshot(oldRows) !== snapshot(rows)) {
                throw new Error(`${ip} 등록 결과가 예상과 다릅니다. 현재 규칙을 다시 조회합니다.`);
            }
            added.push(ip);
            rows = updated;
            onProgress(added.length);
        }
        if (snapshot(await readRules(fetcher)) !== snapshot(rows)) {
            throw new Error('마지막 재조회 결과가 등록 응답과 다릅니다.');
        }
        return added;
    }

    // 합성 검증에서는 공유기 대신 주입된 HTTP 응답을 사용합니다.
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {parseBlocklist, blockPayload, plan, register};
        return;
    }
    const host = ipNumber(location.hostname);
    const privateIp = [['10.0.0.0', '10.255.255.255'], ['172.16.0.0', '172.31.255.255'], ['192.168.0.0', '192.168.255.255']]
        .some(([start, end]) => host !== null && host >= ipNumber(start) && host <= ipNumber(end));
    if (!privateIp || !['http:', 'https:'].includes(location.protocol) || !/^\/ui\/firewall\/?$/.test(location.pathname)) {
        alert('로그인한 ipTIME의 인터넷/WiFi 사용 제한 화면에서 실행해 주세요.');
        return;
    }

    const previous = document.getElementById('equip-iptime-import');
    if (previous) {
        if (!previous.open) previous.showModal();
        return;
    }
    const dialog = document.createElement('dialog');
    dialog.id = 'equip-iptime-import';
    dialog.setAttribute('aria-labelledby', 'equip-iptime-import-title');
    dialog.style.cssText = 'position:fixed;margin:auto;width:min(90vw,34rem);max-height:90vh;overflow:auto;box-sizing:border-box;padding:20px;border:1px solid #64748b;border-radius:12px;background:#0f172a;color:#f8fafc;font:14px/1.5 system-ui';
    const title = document.createElement('h2');
    title.id = 'equip-iptime-import-title';
    title.textContent = 'ipTIME 차단 IP 가져오기';
    const file = document.createElement('input');
    file.type = 'file';
    file.accept = '.txt,text/plain';
    file.setAttribute('aria-label', '공인 IPv4 목록 TXT');
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    status.textContent = 'TXT를 선택하면 기존 규칙과 대조합니다.';
    const preview = document.createElement('pre');
    preview.style.cssText = 'max-height:45vh;overflow:auto;white-space:pre-wrap';
    const apply = document.createElement('button');
    apply.type = 'button';
    apply.textContent = '미리본 주소 차단 등록';
    apply.disabled = true;
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '닫기';
    close.style.marginInlineStart = '8px';
    for (const button of [apply, close]) button.style.cssText += ';padding:7px 12px;border-radius:6px';
    dialog.append(title, file, status, preview, apply, close);
    document.body.append(dialog);
    dialog.showModal();

    const fetcher = window.fetch.bind(window);
    let review;
    let writing = false;
    let previewVersion = 0;
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('cancel', event => { if (writing) event.preventDefault(); });

    file.addEventListener('change', async () => {
        const version = ++previewVersion;
        review = null;
        apply.disabled = true;
        preview.textContent = '';
        const chosen = file.files[0];
        if (!chosen) return;
        status.textContent = '공유기 규칙을 조회하는 중입니다.';
        try {
            if (chosen.size > maxFileBytes) throw new Error('TXT 파일 크기는 16 KiB 이하여야 합니다.');
            const addresses = parseBlocklist(new TextDecoder('utf-8', {fatal: true}).decode(await chosen.arrayBuffer()));
            const rows = await readRules(fetcher);
            const limit = await call('firewall/max', fetcher);
            const added = plan(rows, addresses);
            if (version !== previewVersion) return;
            preview.textContent = [
                ['신규 등록', added.waiting], ['기존 차단', added.existing], ['기존 규칙 확인 필요', added.conflicts],
            ].map(([label, entries]) => [`${label} ${entries.length}개`, ...entries].join('\n')).join('\n\n');
            if (!Number.isSafeInteger(limit?.internet) || rows.length + added.waiting.length > limit.internet) {
                throw new Error('공유기에서 확인한 인터넷 규칙 한도를 초과합니다.');
            }
            status.textContent = `${rows.length}/${limit.internet}개 사용 중 · 신규 규칙은 외부에서 들어오는 해당 주소를 매일 24시간 차단합니다.`;
            review = {rows, addresses: added.waiting};
            apply.disabled = !added.waiting.length;
        } catch (error) {
            if (version === previewVersion) status.textContent = error.message;
        } finally {
            if (version === previewVersion) file.value = '';
        }
    });

    apply.addEventListener('click', async () => {
        if (!review || writing) return;
        const {rows, addresses} = review;
        writing = true;
        file.disabled = apply.disabled = close.disabled = true;
        status.textContent = `등록 중 0/${addresses.length}`;
        try {
            const added = await register(fetcher, rows, addresses,
                count => { status.textContent = `등록 중 ${count}/${addresses.length}`; });
            status.textContent = `${added.length}개 등록 및 동작 상태 확인 완료. 방화벽 목록은 새로고침하면 갱신됩니다.`;
        } catch (error) {
            status.textContent = error.message;
            try {
                const current = plan(await readRules(fetcher), addresses);
                preview.textContent = [
                    `동작 확인 ${current.existing.length}개`, ...current.existing,
                    `\n미등록 ${current.waiting.length}개`, ...current.waiting,
                    `\n기존 규칙 확인 필요 ${current.conflicts.length}개`, ...current.conflicts,
                ].join('\n');
            } catch {
                status.textContent += ' 현재 규칙 재조회에 실패했습니다.';
            }
        } finally {
            writing = false;
            review = null;
            file.disabled = close.disabled = false;
        }
    });
})();
