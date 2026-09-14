/* [역할] 상태/검색/기한/첨부/CSV 화면. [의존성 관계] 기존 fetchEquipment/getEquipmentListScope. [변경 시 영향도] 카탈로그 선택기는 수정하지 않습니다. */
(function (global) {
    'use strict';
    const fields = ['keyword', 'category_id', 'manufacturer_id', 'status', 'purchase_from', 'purchase_to', 'due', 'sort', 'per_page'];
    let advancedSearch = false;
    let page = 1, current = null, detailGeneration = 0, previewToken = null, previewGeneration = 0, nextHistory = null;
    const byId = id => document.getElementById(id);
    // [역할] 모든 동적 HTML escape. [의존성 관계] 배지/미리보기. [변경 시 영향도] 사용자 이름/사유 XSS 방지.
    function escape(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }
    // [역할] 공통 CSRF/안전한 오류. [의존성 관계] Flask JSON. [변경 시 영향도] 429/409/413 안내.
    async function api(url, options = {}) {
        const response = await fetch(url, {...options, headers: {'X-CSRFToken': global.getCSRFToken(), ...options.headers}});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || data.message || `요청 실패 (${response.status})`);
        return data;
    }
    // [역할] 중복 클릭 차단/실패 복구. [의존성 관계] 폼/버튼. [변경 시 영향도] 결과 확정 전 재전송 제한.
    async function busy(element, messageId, action) {
        const controls = element.matches('button') ? [element] : [...element.querySelectorAll('button,input,select,textarea')];
        const disabled = controls.map(control => control.disabled);
        controls.forEach(control => { control.disabled = true; });
        byId(messageId).textContent = '처리 중입니다…';
        try { await action(); } catch (error) { byId(messageId).textContent = error.message; }
        finally { controls.forEach((control, index) => { control.disabled = disabled[index]; }); }
    }
    // [역할] 현재 필터/페이지를 기존 권한 범위에 합침. [의존성 관계] index getEquipmentListScope. [변경 시 영향도] 검색/export 일치.
    function parameters() {
        const result = global.getEquipmentListScope();
        const form = byId('roadmap-filter');
        for (const name of (advancedSearch ? fields : ['keyword'])) if (form.elements[name].value) result.set(name, form.elements[name].value);
        result.set('page', String(page)); result.set('paginated', '1');
        return result;
    }
    // [역할] 필터/페이지 URL 저장. [의존성 관계] history. [변경 시 영향도] 새로고침/URL 공유 재현.
    function persist() {
        const url = new URL(location.href);
        for (const name of [...fields, 'page']) url.searchParams.delete(name);
        const values = parameters();
        for (const name of [...fields, 'page']) if (values.has(name)) url.searchParams.set(name, values.get(name));
        if (advancedSearch) url.searchParams.set('search_mode', 'advanced');
        else url.searchParams.delete('search_mode');
        history.replaceState(null, '', url);
    }
    // Collapsing is a real keyword-only mode, not an invisible active-filter state.
    function setSearchMode(advanced, refresh = false) {
        advancedSearch = advanced;
        const details = byId('roadmap-advanced'), toggle = byId('roadmap-search-toggle');
        details.hidden = !advanced; details.disabled = !advanced;
        toggle.setAttribute('aria-expanded', String(advanced));
        toggle.textContent = advanced ? '일반검색' : '조건검색';
        if (refresh) { page = 1; persist(); global.fetchEquipment(); }
    }
    function restoreSearchMode(saved) {
        if (saved.get('search_mode') === 'simple') return false;
        if (saved.get('search_mode') === 'advanced') return true;
        return fields.filter(name => name !== 'keyword').some(name => {
            const value = saved.get(name);
            return !!value && !(name === 'sort' && value === 'newest') && !(name === 'per_page' && value === '25');
        });
    }
    // [역할] 페이지 상태·빈 결과. [의존성 관계] 서버 count. [변경 시 영향도] 전체 행 수 표시.
    function received(data) {
        byId('roadmap-page').textContent = `${data.total}건 · ${data.page}/${Math.max(1, data.pages)} 페이지`;
        byId('roadmap-prev').disabled = data.page <= 1;
        byId('roadmap-next').disabled = data.page >= data.pages;
        byId('roadmap-message').textContent = data.total ? '' : '조건에 맞는 장비가 없습니다.';
        persist();
    }
    // [역할] 상태와 서울 날짜 배지. [의존성 관계] 서버 due_badge. [변경 시 영향도] 브라우저 TZ 차이 제거.
    function badges(item) {
        const state = `<span class="roadmap-badge">${escape(item.StatusLabel || item.Status || '정상')}</span>`;
        return state + [['보증', item.WarrantyBadge], ['교체', item.ReplacementBadge]].filter(([, value]) => value && value.state !== 'unset').map(([label, value]) => `<span class="roadmap-badge" data-state="${escape(value.state)}">${label} ${escape(value.label)}</span>`).join('');
    }
    // [역할] HTTP 성공한 바이너리만 파일 저장. [의존성 관계] CSV export. [변경 시 영향도] 오류 JSON을 CSV로 저장하지 않음.
    async function exportCurrent() {
        const response = await fetch('/api/equipment/csv/export?' + parameters());
        if (!response.ok) { const data = await response.json(); throw new Error(data.error || data.message); }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a'); link.href = url; link.download = 'equipment.csv';
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        byId('roadmap-message').textContent = '현재 검색 범위의 CSV를 내려받았습니다.';
    }
    // [역할] 이력 텍스트 렌더링. [의존성 관계] owner-only API. [변경 시 영향도] 감사 사유 HTML 실행 방지.
    function renderHistory(historyRows, append = false) {
        const list = byId('roadmap-history');
        if (!append) list.replaceChildren();
        for (const row of historyRows) {
            const entry = document.createElement('li');
            entry.textContent = `${row.changed_at} · ${current.states[row.before.status] || row.before.status} → ${current.states[row.after.status] || row.after.status} · ${row.after.reason || ''} · 사용자 #${row.changed_by ?? '-'}`;
            list.appendChild(entry);
        }
        if (!list.children.length) list.textContent = current.writable ? '상태 변경 이력이 없습니다.' : '소유자/관리자만 이력을 볼 수 있습니다.';
    }
    // [역할] 닫거나 다른 장비로 옮긴 상세창을 재개방하지 않음. [의존성 관계] 변경 요청 완료. [변경 시 영향도] 늦은 UI 응답 격리.
    async function refreshDetails(id) {
        if (byId('roadmap-detail').open && current?.equipment.id === id) await openDetails(id);
    }
    // [역할] 상세+첨부를 같은 장비로 연결. [의존성 관계] generation check. [변경 시 영향도] 늦은 응답이 다른 모달을 덮지 않음.
    async function openDetails(id) {
        const generation = ++detailGeneration;
        current = null;
        const dialog = byId('roadmap-detail');
        if (!dialog.open) dialog.showModal();
        byId('roadmap-status-form').hidden = true; byId('roadmap-upload-form').hidden = true;
        byId('roadmap-files').replaceChildren(); byId('roadmap-history').replaceChildren();
        byId('roadmap-detail-summary').textContent = ''; byId('roadmap-more-history').hidden = true;
        byId('roadmap-detail-message').textContent = '불러오는 중입니다…';
        try {
            const [data, attachments] = await Promise.all([api(`/api/equipment/${id}/lifecycle`), api(`/api/equipment/${id}/files`)]);
            if (generation !== detailGeneration || !dialog.open) return;
            current = data;
            byId('roadmap-detail-title').textContent = data.equipment.name + ' · 상태/첨부';
            byId('roadmap-detail-summary').textContent = `현재: ${data.states[data.equipment.status] || data.equipment.status} · 보증: ${data.equipment.warranty_end_date || '미설정'} · 교체: ${data.equipment.replacement_due_date || '미설정'} · 옵션 ID: ${data.equipment.option_id}`;
            const form = byId('roadmap-status-form'); form.reset();
            form.hidden = !data.transitions.length;
            form.elements.status.replaceChildren(...data.transitions.map(code => new Option(data.states[code], code)));
            renderHistory(data.history); nextHistory = data.next_before_id; byId('roadmap-more-history').hidden = !nextHistory;
            byId('roadmap-upload-form').hidden = !data.writable;
            for (const file of attachments.files) {
                const li = document.createElement('li'), link = document.createElement('a');
                link.href = `/api/equipment/${id}/files/${file.id}/download`; link.textContent = `${file.original_name} (${file.size_bytes.toLocaleString()} B)`;
                li.appendChild(link);
                if (data.writable) {
                    const button = document.createElement('button'); button.type = 'button'; button.textContent = '첨부 삭제';
                    button.addEventListener('click', () => busy(button, 'roadmap-detail-message', async () => {
                        if (!confirm('첨부를 목록에서 삭제합니까? 원본은 복구용으로 보관됩니다.')) return;
                        await api(`/api/equipment/${id}/files/${file.id}`, {method: 'DELETE'}); await refreshDetails(id);
                    }));
                    li.appendChild(button);
                }
                byId('roadmap-files').appendChild(li);
            }
            byId('roadmap-detail-message').textContent = '';
        } catch (error) { if (generation === detailGeneration) byId('roadmap-detail-message').textContent = error.message; }
    }
    // [역할] URL 복원과 UI 이벤트 1회 바인딩. [의존성 관계] template 뒤 스크립트. [변경 시 영향도] 중복 listener 없음.
    function init() {
        const form = byId('roadmap-filter'), saved = new URLSearchParams(location.search);
        page = Math.max(1, Number.parseInt(saved.get('page') || '1', 10) || 1);
        for (const name of fields) if (saved.has(name) && !['category_id', 'manufacturer_id'].includes(name)) form.elements[name].value = saved.get(name);
        setSearchMode(restoreSearchMode(saved));
        byId('roadmap-search-toggle').addEventListener('click', () => setSearchMode(!advancedSearch, true));
        // Disclosure only: opening CSV must not search, download or reset an import preview.
        byId('roadmap-csv-toggle').addEventListener('click', event => {
            const panel = byId('roadmap-csv-actions');
            panel.hidden = !panel.hidden;
            event.currentTarget.setAttribute('aria-expanded', String(!panel.hidden));
            event.currentTarget.textContent = panel.hidden ? 'CSV 기능' : 'CSV 닫기';
        });
        form.addEventListener('submit', event => { event.preventDefault(); page = 1; global.fetchEquipment(); });
        form.addEventListener('reset', () => { page = 1; setTimeout(() => global.fetchEquipment(), 0); });
        byId('roadmap-prev').addEventListener('click', () => { page = Math.max(1, page - 1); global.fetchEquipment(); });
        byId('roadmap-next').addEventListener('click', () => { page++; global.fetchEquipment(); });
        byId('roadmap-export').addEventListener('click', event => busy(event.currentTarget, 'roadmap-message', exportCurrent));
        byId('roadmap-import').addEventListener('click', () => { byId('roadmap-csv-dialog').showModal(); });
        document.querySelectorAll('[data-roadmap-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
        byId('roadmap-detail').addEventListener('close', () => { current = null; ++detailGeneration; });
        byId('roadmap-status-form').addEventListener('submit', event => {
            event.preventDefault(); if (!current) return;
            const id = current.equipment.id, revision = current.equipment.revision, values = event.currentTarget.elements;
            const data = {status: values.status.value, reason: values.reason.value, revision};
            busy(event.currentTarget, 'roadmap-detail-message', async () => { await api(`/api/equipment/${id}/status`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)}); await refreshDetails(id); await global.fetchEquipment(); });
        });
        byId('roadmap-upload-form').addEventListener('submit', event => {
            event.preventDefault(); if (!current) return;
            const id = current.equipment.id, body = new FormData(event.currentTarget);
            busy(event.currentTarget, 'roadmap-detail-message', async () => { await api(`/api/equipment/${id}/files`, {method: 'POST', body}); byId('roadmap-upload-form').reset(); await refreshDetails(id); });
        });
        byId('roadmap-more-history').addEventListener('click', event => {
            if (!current || !nextHistory) return;
            const id = current.equipment.id, generation = detailGeneration;
            busy(event.currentTarget, 'roadmap-detail-message', async () => { const data = await api(`/api/equipment/${id}/lifecycle?before_id=${nextHistory}`); if (generation !== detailGeneration) return; renderHistory(data.history, true); nextHistory = data.next_before_id; byId('roadmap-more-history').hidden = !nextHistory; byId('roadmap-detail-message').textContent = ''; });
        });
        byId('roadmap-csv-form').elements.file.addEventListener('change', () => { ++previewGeneration; previewToken = null; byId('roadmap-csv-confirm').disabled = true; byId('roadmap-csv-preview').replaceChildren(); });
        byId('roadmap-csv-form').addEventListener('submit', event => {
            event.preventDefault(); previewToken = null; byId('roadmap-csv-confirm').disabled = true;
            const generation = ++previewGeneration;
            const body = new FormData(event.currentTarget);
            busy(event.currentTarget, 'roadmap-csv-message', async () => {
                const data = await api('/api/equipment/csv/preview', {method: 'POST', body});
                if (generation !== previewGeneration) return;  // 파일 변경 이후의 늦은 검증 응답은 버립니다.
                previewToken = data.token;
                byId('roadmap-csv-message').textContent = `정상 ${data.count}행 / 오류 ${data.errors.length}행. 확정 전에는 장비가 등록되지 않습니다.`;
                byId('roadmap-csv-preview').innerHTML = data.errors.length ? '<ul>' + data.errors.map(row => `<li>${row.row}행: ${escape(row.message)}</li>`).join('') + '</ul>' : '<table><thead><tr><th>장비명</th><th>옵션 ID</th><th>시리얼</th><th>공개</th></tr></thead><tbody>' + data.rows.map(row => `<tr><td>${escape(row.Name)}</td><td>${escape(row.OptionId)}</td><td>${escape(row.SerialNumber)}</td><td>${row.IsPublic ? '공개' : '비공개'}</td></tr>`).join('') + '</tbody></table>';
                byId('roadmap-csv-confirm').disabled = !previewToken;
            });
        });
        byId('roadmap-csv-confirm').addEventListener('click', async event => {
            if (!previewToken) return;
            const button = event.currentTarget;
            byId('roadmap-csv-form').elements.file.disabled = true;
            await busy(button, 'roadmap-csv-message', async () => {
                const result = await api('/api/equipment/csv/commit', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({token: previewToken})});
                previewToken = null; byId('roadmap-csv-message').textContent = `${result.count}건 등록 ${result.replayed ? '(이미 완료된 요청)' : '완료'}`; await global.fetchEquipment();
            });
            button.disabled = !previewToken;
            byId('roadmap-csv-form').elements.file.disabled = false;
        });
        return api('/api/master_data').then(data => {
            for (const [name, rows, key] of [['category_id', data.categories, 'CategoryId'], ['manufacturer_id', data.manufacturers, 'ManufacturerId']]) {
                for (const row of rows) form.elements[name].add(new Option(row.NameKo || row.NameEn || row.Name, String(row[key])));
                if (saved.has(name)) form.elements[name].value = saved.get(name);
            }
        }).catch(error => { byId('roadmap-message').textContent = error.message; });
    }
    global.Roadmap = {parameters, received, badges, openDetails, init, escape, resetPage() { page = 1; }};
})(window);
