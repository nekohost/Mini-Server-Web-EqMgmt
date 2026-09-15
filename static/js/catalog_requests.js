/* [역할] 공통 3종 신청서. [의존성 관계] 카탈로그·CSRF·접수 API. [변경 시 영향도] 결재함·내/공개 장비. */
(function (global) { // 전역 이름을 하나만 노출합니다.
    'use strict'; // 암묵적 전역 생성을 막습니다.
    const labels = {category: '카테고리', manufacturer: '제조사', node: '라인업 노드'}; // 서버 허용 종류입니다.
    let dialog, form, fields, title, hint, message, submit, close, active, generation = 0; // 공통 폼 상태입니다.
    /* [역할] 안전한 요소 생성. [의존성 관계] textContent. [변경 시 영향도] 이름/응답 XSS 차단. */
    function element(tag, text = '', className = '') { // HTML 문자열을 해석하지 않습니다.
        const node = document.createElement(tag); node.textContent = text; node.className = className; return node; // 텍스트만 표시합니다.
    } // 요소 생성 종료입니다.
    /* [역할] label과 필드 연결. [의존성 관계] fields. [변경 시 영향도] 접근성과 필수값 검사. */
    function field(key, label, tag = 'input') { // 세 폼에 동일 규격을 사용합니다.
        const wrapper = element('label', label), control = element(tag); control.id = 'catalog-' + key; control.name = key; // 고유 ID입니다.
        wrapper.htmlFor = control.id; wrapper.append(control); fields.append(wrapper); return control; // 명시적으로 연결합니다.
    } // 필드 생성 종료입니다.
    /* [역할] 선택지 생성. [의존성 관계] 서버 카탈로그. [변경 시 영향도] 이름을 텍스트로 보존. */
    function option(select, value, text) { const node = element('option', text); node.value = String(value); select.append(node); } // HTML을 삽입하지 않습니다.
    /* [역할] 결과 안내. [의존성 관계] aria-live. [변경 시 영향도] 오류/성공 구분. */
    function feedback(text, state = '') { message.textContent = text; message.dataset.state = state; } // 색과 문구를 함께 사용합니다.
    /* [역할] 입력 잠금. [의존성 관계] active. [변경 시 영향도] 중복 제출·취소 방어. */
    function lock() { fields.disabled = active.busy || active.loading || active.done; submit.disabled = fields.disabled; close.disabled = active.busy; } // 조회 중 취소는 허용합니다.
    /* [역할] 제한시간이 있는 JSON 통신. [의존성 관계] AbortController. [변경 시 영향도] 무한 잠금 방지; 서버 취소를 보장하지 않음. */
    async function requestJson(url, options = {}, milliseconds = 30000) { // 전체 응답 본문까지 제한합니다.
        const controller = new AbortController(), timer = global.setTimeout(() => controller.abort(), milliseconds); // 요청별 제한시간입니다.
        try { const response = await fetch(url, {...options, signal: controller.signal}); return {response, result: await response.json().catch(() => ({}))}; } // 응답 검증은 호출자가 수행합니다.
        finally { global.clearTimeout(timer); } // 정상·오류 모두 타이머를 정리합니다.
    } // 통신 헬퍼 종료입니다.
    /* [역할] 공통 dialog 생성. [의존성 관계] native dialog. [변경 시 영향도] 장비 form을 중첩하거나 초기화하지 않음. */
    function ensureDialog() { // 최초 한 번만 생성합니다.
        if (dialog) return; // 중복 ID를 만들지 않습니다.
        dialog = element('dialog', '', 'catalog-request-dialog'); dialog.id = 'catalog-request-dialog'; dialog.setAttribute('aria-labelledby', 'catalog-request-title'); // 접근성 제목입니다.
        title = element('h2'); title.id = 'catalog-request-title'; hint = element('p'); // 종류/정책 안내입니다.
        form = element('form'); fields = element('fieldset', '', 'catalog-request-fields'); // 네이티브 입력 검증입니다.
        message = element('p'); message.setAttribute('role', 'status'); message.setAttribute('aria-live', 'polite'); // 결과 읽기 영역입니다.
        const actions = element('div', '', 'catalog-request-actions'); close = element('button', '취소', 'app-button'); close.type = 'button'; // 부모 제출을 막습니다.
        submit = element('button', '등록 신청', 'app-button app-button-primary'); submit.type = 'submit'; actions.append(close, submit); // 명시적 제출입니다.
        form.append(fields, message, actions); dialog.append(title, hint, form); document.body.append(dialog); // 부모 장비 입력은 그대로 둡니다.
        close.addEventListener('click', () => { if (!active.busy) dialog.close(); }); // 처리 중 닫기는 막습니다.
        dialog.addEventListener('cancel', event => { if (active.busy) event.preventDefault(); }); // Escape도 동일 정책입니다.
        dialog.addEventListener('close', () => { if (dialog.open) return; generation++; fields.replaceChildren(); active.returnFocus?.focus(); }); // 늦은 close가 새 폼을 지우지 않게 합니다.
        form.addEventListener('submit', send); // 세 종류의 공통 전송입니다.
    } // dialog 생성 종료입니다.
    /* [역할] 부모 선택 필터. [의존성 관계] 승인된 동일 분류/제조사. [변경 시 영향도] 다른 계층 연결·순환 방어. */
    function parents() { // 분류가 바뀌면 이전 parent_id를 초기화합니다.
        const parent = form.elements.parent_id, category = form.elements.category_id.value, manufacturer = form.elements.manufacturer_id.value; // 현재 조합입니다.
        parent.replaceChildren(); option(parent, '', '최상위 노드로 신청'); // 루트 신청도 가능합니다.
        const eligible = active.nodes.filter(node => String(node.category_id) === category && String(node.manufacturer_id) === manufacturer && node.status === 'APPROVED'); // 승인 항목만 사용합니다.
        const byId = new Map(eligible.map(node => [String(node.id), node])); // 부모 경로 조회입니다.
        for (const node of eligible) { // 실제 연결에서 표시 경로를 만듭니다.
            const names = [], seen = new Set(); let current = node, valid = true; // 순환/깊이 검사 상태입니다.
            while (current) { // 유한 경로만 처리합니다.
                if (seen.has(String(current.id)) || names.length >= 50) { valid = false; break; } // 순환과 과도한 깊이를 거부합니다.
                seen.add(String(current.id)); names.unshift(current.name); // 표시값은 textContent로 들어갑니다.
                if (current.parent_id == null) break; current = byId.get(String(current.parent_id)); if (!current) valid = false; // 끊긴 경로는 제외합니다.
            } // 부모 검사가 끝났습니다.
            if (valid && names.length < 50) option(parent, node.id, names.join(' / ')); // 51번째 깊이를 만들지 않습니다.
        } // 선택지 구성 종료입니다.
        parent.disabled = !category || !manufacturer; // 두 마스터를 먼저 선택해야 합니다.
    } // 부모 필터 종료입니다.
    /* [역할] 승인 목록 조회. [의존성 관계] 기존 카탈로그 GET. [변경 시 영향도] 취소/재진입의 늦은 응답 방어. */
    async function loadCatalog(ticket, preset) { // 요청한 폼 세대를 고정합니다.
        try { // 실패하면 입력 가능한 것처럼 표시하지 않습니다.
            const {response, result: data} = await requestJson('/api/lineup_tree_all', {cache: 'no-store'}, 15000); // 목록은 15초 제한입니다.
            if (ticket !== generation || !dialog.open) return; // 이미 닫은 폼에는 적용하지 않습니다.
            if (!response.ok || !data.success || !['categories', 'manufacturers', 'nodes'].every(key => Array.isArray(data[key]))) throw new Error('승인된 목록을 불러오지 못했습니다. 닫은 뒤 다시 신청해 주세요.'); // 응답 구조를 확인합니다.
            for (const [key, rows] of [['category_id', data.categories], ['manufacturer_id', data.manufacturers]]) { // 마스터를 독립적으로 표시합니다.
                const select = form.elements[key]; select.replaceChildren(); option(select, '', '-- 선택 --'); rows.forEach(row => option(select, row.id, row.name)); // 안전한 선택지입니다.
            } // 마스터 조회 결과 반영입니다.
            active.nodes = data.nodes; form.elements.category_id.value = String(preset.categoryId || ''); form.elements.manufacturer_id.value = String(preset.manufacturerId || ''); // 승인된 기존 선택만 복원합니다.
            parents(); if (preset.parentId) form.elements.parent_id.value = String(preset.parentId); // 없는 부모는 선택되지 않습니다.
            active.loading = false; feedback('카테고리·제조사를 고른 뒤 상위 노드를 선택하세요. 아직 없는 분류는 별도 신청 후 승인을 기다려 주세요.'); lock(); // 유효한 목록일 때만 입력을 엽니다.
        } catch (error) { if (ticket === generation && dialog.open) feedback(error.name === 'AbortError' ? '목록 조회가 지연되었습니다. 닫은 뒤 다시 신청해 주세요.' : error.message || '목록을 불러오지 못했습니다.', 'error'); } // 재시도 방법을 안내합니다.
    } // 승인 목록 조회 종료입니다.
    /* [역할] 즉시 등록 후 장비 선택지 갱신. [의존성 관계] 실제 LineupApp.init. [변경 시 영향도] 장비 입력·선택·dirty 상태 보존. */
    async function refreshEquipmentCatalog(result, payload) { // 결재함에는 장비 선택기가 없으므로 적용하지 않습니다.
        const app = global.LineupApp, category = document.getElementById('CategorySelect'), manufacturer = document.getElementById('ManufacturerSelect'); // 현재 화면의 실제 요소입니다.
        if (!app?.init || !category || !manufacturer) return; // 다른 화면으로 확대하지 않습니다.
        const state = () => JSON.stringify([document.getElementById('EquipmentId')?.value, category.value, manufacturer.value, document.getElementById('OptionSelect')?.value, [...document.querySelectorAll('.lineup-select-row select')].map(select => select.value)]); // 갱신 중 화면 변경 감지입니다.
        const before = state(), selected = [category.value, manufacturer.value]; // 사용자가 고른 값입니다.
        const {response, result: data} = await requestJson('/api/lineup_tree_all', {cache: 'no-store'}, 15000); // 후속 갱신도 유한시간입니다.
        if (!response.ok || !data.success || !['categories', 'manufacturers', 'nodes', 'options'].every(key => Array.isArray(data[key])) || before !== state()) throw new Error('현재 장비 선택을 보존하기 위해 목록 갱신을 중단했습니다.'); // 상태가 바뀌면 적용하지 않습니다.
        for (const [index, key] of ['categories', 'manufacturers'].entries()) { // 현재 선택이 외부 변경으로 사라지지 않았는지 확인합니다.
            if (selected[index] && selected[index] !== '__custom__' && !data[key].some(item => String(item.id) === selected[index])) throw new Error('선택된 분류가 바뀌었습니다.'); // 조용히 선택을 지우지 않습니다.
        } // 참조 검사 종료입니다.
        const optionId = document.getElementById('OptionSelect')?.value; // 기존 옵션도 보존되어야 합니다.
        if (optionId && optionId !== '__new__' && !data.options.some(item => String(item.id) === optionId)) throw new Error('선택된 옵션이 바뀌었습니다.'); // 사라진 연결을 정상으로 보지 않습니다.
        await app.init(true, data); category.value = selected[0]; manufacturer.value = selected[1]; // 이미 확인한 응답으로 캐시를 갱신하고 루트 선택을 복원합니다.
        if (payload.kind === 'node' && selected[0] === String(payload.category_id) && selected[1] === String(payload.manufacturer_id)) { // 현재 조합에 해당하는 새 노드만 추가합니다.
            const node = data.nodes.find(item => String(item.id) === String(result.node_id) && item.status === 'APPROVED'); // 승인 목록에서 새 노드를 확인합니다.
            const row = [...document.querySelectorAll('.lineup-select-row')].find(item => item.dataset.parent === String(payload.parent_id || 'root')); // 현재 표시한 부모와 대조합니다.
            const select = row?.querySelector('select'); // 해당 부모의 기존 선택란입니다.
            if (node && select && ![...select.options].some(item => item.value === String(node.id))) { // 같은 항목을 중복 추가하지 않습니다.
                const value = select.value, added = element('option', node.name); added.value = String(node.id); // 명칭은 텍스트로 표시합니다.
                select.insertBefore(added, [...select.options].find(item => item.value === '__add_node__') || null); select.value = value; // 기존 선택값을 자동 변경하지 않습니다.
            } // 추가할 항목이 없으면 기존 DOM을 유지합니다.
        } // 특정 노드에서 시작한 기존 onApproved 경로와는 구분합니다.
        app.updateSubmitLockState(); // 복원한 선택값으로 저장 가능 여부를 다시 판단합니다.
    } // 갱신 함수 종료입니다.
    /* [역할] 신청서 열기. [의존성 관계] 공통 dialog. [변경 시 영향도] 세 종류·두 진입점의 동일 UX. */
    function open(kind, preset = {}) { // 요청한 종류만 표시합니다.
        if (!Object.hasOwn(labels, kind)) throw new Error('지원하지 않는 신청 종류입니다.'); // 알 수 없는 종류는 거부합니다.
        ensureDialog(); if (dialog.open) return; // 열린 입력을 덮어쓰지 않습니다.
        active = {kind, preset, nodes: [], busy: false, loading: kind === 'node', done: false, returnFocus: document.activeElement}; // 새 폼 상태입니다.
        const ticket = ++generation; fields.replaceChildren(); title.textContent = labels[kind] + ' 등록 신청'; close.textContent = '취소'; // 이전 폼 데이터는 제거합니다.
        hint.textContent = '일반 사용자는 관리자 승인 후 사용할 수 있습니다. 관리자는 기존 정책에 따라 즉시 등록됩니다. 장비 등록 내용은 그대로 유지됩니다.'; // 실제 승인 계약입니다.
        if (kind === 'node') { // 노드만 종속 필드를 가집니다.
            field('category_id', '카테고리 (필수)', 'select').required = true; field('manufacturer_id', '제조사 (필수)', 'select').required = true; field('parent_id', '상위 노드', 'select'); // 필수 두 마스터입니다.
            form.elements.category_id.addEventListener('change', parents); form.elements.manufacturer_id.addEventListener('change', parents); // 부모 선택을 동기화합니다.
        } // 마스터 신청서는 독립적입니다.
        const name = field('name', labels[kind] + ' 이름 (필수)'); name.type = 'text'; name.required = true; name.maxLength = 100; name.autocomplete = 'off'; // 서버와 동일 이름 계약입니다.
        feedback(active.loading ? '승인된 목록을 불러오는 중입니다.' : '장비를 등록하지 않아도 독립적으로 신청할 수 있습니다.'); lock(); dialog.showModal(); // 자동 제출하지 않습니다.
        if (kind === 'node') loadCatalog(ticket, preset); else name.focus(); // 승인된 목록부터 확인합니다.
    } // 폼 열기 종료입니다.
    /* [역할] 신청 전송. [의존성 관계] 기존 CSRF/API. [변경 시 영향도] 접수와 화면 갱신 실패를 구별. */
    async function send(event) { // 사용자의 명시적 제출만 처리합니다.
        event.preventDefault(); if (active.busy || active.loading || active.done || !form.reportValidity()) return; // 중복과 불완전 입력을 막습니다.
        const payload = {kind: active.kind, name: form.elements.name.value.trim()}; // 권한·신청자 필드를 보내지 않습니다.
        if (active.kind === 'node') Object.assign(payload, {category_id: form.elements.category_id.value, manufacturer_id: form.elements.manufacturer_id.value, parent_id: form.elements.parent_id.value || null}); // 서버가 관계를 다시 검증합니다.
        if (!payload.name) { feedback('이름을 입력해 주세요.', 'error'); form.elements.name.focus(); return; } // 공백만 있는 이름을 거부합니다.
        active.busy = true; lock(); feedback('신청을 전송하는 중입니다.'); // 요청 중 닫기/재제출을 막습니다.
        try { // 오류가 나더라도 입력은 보존합니다.
            active.preset.onBusy?.(true); // 기존 장비 저장과의 잠금 콜백입니다.
            const {response, result} = await requestJson('/api/catalog_requests', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': global.getCSRFToken()}, body: JSON.stringify(payload)}); // 30초 제한과 실제 CSRF helper입니다.
            if (!response.ok || !result.success) throw new Error(result.message || '신청을 접수하지 못했습니다. 나의 결재함에서 접수 여부를 확인한 뒤 다시 시도해 주세요.'); // 불확실한 접수를 자동 재전송하지 않습니다.
            active.done = true; close.textContent = '닫기'; feedback(result.message || '신청 처리가 완료되었습니다.', 'success'); // 서버 성공은 여기서 확정합니다.
            try { // 이후 조회 오류가 접수 실패를 의미하지는 않습니다.
                if (result.status === 'APPROVED') { global.LineupApp?.invalidateCache?.(); if (active.preset.onApproved) await active.preset.onApproved(result, payload); else await refreshEquipmentCatalog(result, payload); } // 문맥별 콜백 또는 선택 보존 갱신입니다.
                const filter = document.getElementById('my-approvals-filter'); // 개인 화면에서만 목록을 갱신합니다.
                if (filter) { if (result.status === 'PENDING') document.getElementById('my-approvals-status').value = 'PENDING'; filter.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})); } // 본인 조회 로직을 재사용합니다.
                document.dispatchEvent(new CustomEvent('catalog-request-created', {detail: {kind: active.kind, status: result.status}})); // 결과 종류만 전달합니다.
            } catch { feedback('접수는 완료되었습니다. 목록 갱신에 실패했으므로 입력을 보존한 채 신청창을 닫아 주세요. 같은 신청을 다시 제출하지 마세요.', 'success'); } // 중복 접수를 유도하지 않습니다.
        } catch (error) { feedback(error.name === 'AbortError' ? '응답이 지연되어 대기를 종료했습니다. 서버에서 접수되었을 수 있으므로 나의 결재함에서 확인한 뒤 다시 시도해 주세요.' : error.message || '통신 오류입니다. 접수 여부를 확인한 뒤 다시 시도해 주세요.', 'error'); } // timeout은 서버 취소가 아닙니다.
        finally { active.busy = false; lock(); try { active.preset.onBusy?.(false); } catch { feedback(active.done ? '접수는 완료되었습니다. 장비 화면의 저장 상태를 확인해 주세요.' : '신청 상태를 확인하고 창을 다시 열어 주세요.', active.done ? 'success' : 'error'); } } // 콜백 오류도 잠금을 남기지 않습니다.
    } // 제출 처리 종료입니다.
    /* [역할] 세 신청 진입점. [의존성 관계] open. [변경 시 영향도] 두 화면에서 동일 폼 재사용. */
    function mountToolbar(container, preset = () => ({})) { // 선택은 클릭 순간 읽습니다.
        if (container.querySelector('.catalog-request-toolbar')) return container.querySelector('.catalog-request-toolbar'); // 재초기화로 버튼을 복제하지 않습니다.
        const toolbar = element('div', '', 'catalog-request-toolbar'); // 제목과 분리된 조작 영역입니다.
        for (const kind of Object.keys(labels)) { const button = element('button', labels[kind] + ' 신청', 'app-button'); button.type = 'button'; button.dataset.catalogKind = kind; button.addEventListener('click', () => open(kind, preset())); toolbar.append(button); } // 부모 폼은 제출하지 않습니다.
        container.append(toolbar); return toolbar; // 생성한 영역을 반환합니다.
    } // 진입점 생성 종료입니다.
    global.CatalogRequests = {open, mountToolbar}; // 기존 노드 등록기와 공유합니다.
    document.addEventListener('DOMContentLoaded', () => { // 실제 화면 준비 후 연결합니다.
        document.querySelectorAll('[data-catalog-request-toolbar]').forEach(container => mountToolbar(container, () => ({categoryId: document.getElementById('CategorySelect')?.value, manufacturerId: document.getElementById('ManufacturerSelect')?.value}))); // 기존 선택값은 읽기만 합니다.
    }); // 대상 요소가 없는 페이지에는 버튼을 만들지 않습니다.
})(window); // 공통 모듈 종료입니다.
