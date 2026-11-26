(() => {
    'use strict';
    const panel = document.getElementById('access-ip-review');
    if (!panel) return;

    const base = '/api/admin/ai/access-ip-reviews';
    const history = document.getElementById('access-ip-history');
    const form = panel.querySelector('[data-analysis-form]');
    const model = form.elements.model;
    const level = form.elements.level;
    const submit = form.querySelector('button');
    const status = panel.querySelector('[data-status]');
    const download = panel.querySelector('[data-download]');
    const results = panel.querySelector('[data-results]');
    const list = results.querySelector('ul');
    let pending;
    let flow;
    let choices = [];
    let cursor;

    async function request(url, body) {
        const response = await fetch(url, body ? {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken()},
            body: JSON.stringify(body),
            cache: 'no-store',
        } : {cache: 'no-store'});
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) throw new Error(data.message || 'AI 분석 요청을 확인할 수 없습니다.');
        return data;
    }

    function showRows(container, rows) {
        container.replaceChildren();
        const labels = {
            system_file: '운영체제 파일 접근', injection_pattern: '인젝션 패턴',
            exchange_proxy_powershell: 'Exchange 프록시 악용 패턴', gateway_config_traversal: '게이트웨이 설정파일 탐색',
            php_eval_endpoint: 'PHP 실행 경로 접근', webshell_write: '웹셸 경로 쓰기',
        };
        for (const row of rows) {
            const item = document.createElement('li');
            const reasons = Object.entries(row.signals).map(([signal, count]) => `${labels[signal]} ${count}건`);
            if (row.secret_paths >= 2) reasons.push(`비밀 경로 ${row.secret_paths}개`);
            if (row.php_paths >= 8 && row.shell_names >= 2) {
                reasons.push(`PHP 경로 ${row.php_paths}개 중 웹셸 이름 ${row.shell_names}종`);
            }
            item.textContent = `${row.ip} · ${reasons.join(' · ')}`;
            container.append(item);
        }
    }

    function updateLevels() {
        const choice = choices.find(option => option.id === model.value);
        level.replaceChildren();
        if (!choice) return;
        const levels = choice.levels.length ? choice.levels : ['default'];
        for (const value of levels) level.add(new Option(value === 'default' ? '모델 기본값' : value, value));
        level.value = levels.includes(choice.default_level) ? choice.default_level : levels[0];
    }

    function show(data, id) {
        const {state, evidence} = data;
        const selected = data.verified || [];
        const detail = `오류 ${evidence.errors.toLocaleString()}건 · Nginx 대조 ${evidence.corroborated.toLocaleString()}건`;
        const label = data.model ? `${data.model} · ${data.level === 'default' ? '모델 기본값' : data.level} · ` : '';
        download.hidden = true;
        download.removeAttribute('href');
        results.hidden = true;
        list.replaceChildren();
        if (state === 'done' || state === 'empty') {
            status.textContent = `${label}${detail} · TXT 후보 ${selected.length}개`;
            if (!selected.length) return;
            showRows(list, selected);
            download.href = `${base}/${id}/blocklist.txt`;
            download.hidden = false;
            results.hidden = false;
        } else if (state === 'queued' || state === 'running' || state === 'draining') {
            const phase = {queued: '대기 중', running: '검토 중', draining: '종료 확인 중'}[state];
            status.textContent = `${label}${detail} · 후보 ${data.candidate_count}개 ${phase}`;
        } else {
            status.textContent = data.error || 'AI 판정을 끝내지 못했습니다.';
        }
    }

    async function follow(id) {
        if (!/^[0-9a-f]{32}$/.test(id)) throw new Error('분석 작업 식별자가 올바르지 않습니다.');
        while (panel.open) {
            const data = await request(`${base}/${id}`);
            show(data, id);
            if (!['queued', 'running', 'draining'].includes(data.state)) return;
            await new Promise(resolve => window.setTimeout(resolve, 2500));
        }
    }

    function run(action) {
        if (flow) return;
        submit.disabled = true;
        flow = action().catch(error => {
            status.textContent = error.message;
        }).finally(() => {
            flow = null;
            submit.disabled = !model.value;
        });
    }

    model.addEventListener('change', updateLevels);
    document.getElementById('open-access-ip-review').addEventListener('click', () => {
        panel.showModal();
        run(async () => {
            status.textContent = '사용 가능한 모델을 불러오는 중입니다.';
            const data = await request(base);
            const previousModel = model.value;
            const previousLevel = level.value;
            choices = data.models;
            model.replaceChildren(...choices.map(choice => new Option(`${choice.label} · ${choice.provider}`, choice.id)));
            model.value = choices.some(choice => choice.id === previousModel) ? previousModel : data.default_model || '';
            updateLevels();
            if (model.value === previousModel && Array.from(level.options).some(option => option.value === previousLevel)) {
                level.value = previousLevel;
            }
            status.textContent = model.value ? '' : '현재 사용 가능한 AI 모델이 없습니다.';
            if (data.job_id) await follow(data.job_id);
        });
    });

    form.addEventListener('submit', event => {
        event.preventDefault();
        if (flow) return;
        download.hidden = true;
        results.hidden = true;
        status.textContent = '접근 로그와 Nginx 기록을 대조 중입니다.';
        const hours = Number(form.elements.hours.value);
        if (!pending || pending.hours !== hours || pending.selection_id !== model.value || pending.level !== level.value) {
            const bytes = crypto.getRandomValues(new Uint8Array(16));
            const client_key = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
            pending = {hours, selection_id: model.value, level: level.value, client_key};
        }
        run(async () => {
            const data = await request(base, pending);
            pending = null;
            if (data.job_id) await follow(data.job_id);
            else show(data);
        });
    });

    const historyStatus = history.querySelector('[data-status]');
    const historyList = history.querySelector('[data-history]');
    const more = history.querySelector('[data-more]');
    let loadingHistory = false;

    async function loadHistory() {
        if (loadingHistory) return;
        loadingHistory = true;
        more.disabled = true;
        historyStatus.textContent = '추출 이력을 불러오는 중입니다.';
        try {
            const data = await request(`${base}/history${cursor ? '?before=' + encodeURIComponent(cursor) : ''}`);
            for (const item of data.items) {
                const row = document.createElement('li');
                row.className = 'py-3 space-y-2 text-xs';
                const detail = document.createElement('p');
                const effort = item.level === 'default' ? '모델 기본값' : item.level;
                detail.textContent = `${item.end} KST · ${item.model} · ${effort} · ${item.count}개`;
                row.append(detail);
                if (item.count) {
                    const link = document.createElement('a');
                    link.href = `${base}/${item.job_id}/blocklist.txt`;
                    link.textContent = 'TXT 다운로드';
                    link.className = 'underline text-brand-600 dark:text-brand-400';
                    const addresses = document.createElement('details');
                    const summary = document.createElement('summary');
                    summary.textContent = '판정 주소 보기';
                    const items = document.createElement('ul');
                    items.className = 'mt-2 space-y-1';
                    addresses.append(summary, items);
                    addresses.addEventListener('toggle', async () => {
                        if (!addresses.open || items.childElementCount) return;
                        items.textContent = '불러오는 중입니다.';
                        try {
                            const data = await request(`${base}/${item.job_id}`);
                            showRows(items, data.verified);
                        } catch (error) {
                            items.textContent = error.message;
                        }
                    });
                    row.append(link, addresses);
                }
                historyList.append(row);
            }
            cursor = data.next_before;
            more.hidden = !cursor;
            historyStatus.textContent = historyList.childElementCount ? '' : '완료된 분석이 없습니다.';
        } catch (error) {
            historyStatus.textContent = error.message;
        } finally {
            loadingHistory = false;
            more.disabled = false;
        }
    }
    document.getElementById('open-access-ip-history').addEventListener('click', () => {
        history.showModal();
        if (loadingHistory) return;
        historyList.replaceChildren();
        more.hidden = true;
        cursor = null;
        loadHistory();
    });
    more.addEventListener('click', loadHistory);
})();
