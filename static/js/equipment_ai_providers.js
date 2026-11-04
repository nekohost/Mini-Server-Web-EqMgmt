/* [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT]
 * [EN rev.2]
 * [Role] Edits basic provider settings and tracks inert capability probes through the internal queue.
 * [Dependencies] Same-origin admin APIs, server CSRF/revisions and text-only DOM rendering.
 * [Impact] Keys are write-only, conflicts are shown, and no browser request reaches a model server.
 */
(function () {
    'use strict';
    const root = document.getElementById('ai-providers-admin');
    if (!root) return;
    const $ = id => document.getElementById(id), form = $('provider-form');
    const reasoningLevels = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];
    let state = null, current = null, selectedId = null, disposed = false, probeTimer = null;
    const notice = text => { $('provider-notice').textContent = text || ''; };

    /** [Role] Sends only fixed same-origin admin paths with CSRF; failures never print credentials. */
    async function api(path, data) {
        const response = await fetch(path, { method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
            headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf }, body: data === undefined ? undefined : JSON.stringify(data) });
        const value = await response.json();
        if (!response.ok || value.success !== true) throw Error(value.message || '연결 관리 요청을 완료하지 못했습니다.');
        return value;
    }

    /** [Role] Creates bounded labeled controls without inserting provider/model strings as HTML. */
    function field(container, label, type, value) {
        const wrapper = document.createElement('label'); wrapper.append(document.createTextNode(label));
        const input = document.createElement('input'); input.type = type;
        if (type === 'checkbox') { input.checked = Boolean(value); wrapper.className = 'provider-check'; } else input.value = value;
        wrapper.append(input); container.append(wrapper); return input;
    }

    /** [Role] Displays current registry data, credential-presence and optimistic revisions. */
    function render() {
        $('provider-encryption').textContent = state.encryption_configured ? '독립 암호화 키 설정됨' : 'API 키 저장 전 서버의 독립 암호화 키 설정 필요';
        $('provider-list').replaceChildren();
        for (const p of state.providers) {
            const button = document.createElement('button'); button.type = 'button'; button.textContent = `${p.name}${p.retired ? ' · 폐기' : p.enabled ? '' : ' · 중지'}`;
            button.dataset.providerId = p.id; button.setAttribute('aria-current', String(p.id === selectedId)); button.addEventListener('click', () => edit(p)); $('provider-list').append(button);
        }
        if (selectedId) edit(state.providers.find(p => p.id === selectedId)); else edit(null);
    }

    /** [Role] Opens one revision in the form without reading back an original/encrypted API key. */
    function edit(provider) {
        current = provider || null; selectedId = current && current.id; form.reset();
        $('provider-list').querySelectorAll('button').forEach(button => button.setAttribute('aria-current', String(button.dataset.providerId === selectedId)));
        $('provider-heading').textContent = current ? `${current.name} · 설정 ${current.revision}` : '연결 추가';
        const groups = document.createDocumentFragment();
        for (const group of state.groups) { const option = document.createElement('option'); option.value = group.id; option.textContent = group.name; groups.append(option); }
        $('provider-group').replaceChildren(groups);
        for (const name of ['name','base_url','adapter','resource_group','sort_order','enabled','manual']) if (current) {
            const input = form.elements.namedItem(name); if (input.type === 'checkbox') input.checked = Boolean(current[name]); else input.value = current[name];
        }
        form.elements.api_key.placeholder = current && current.has_key ? '키 저장됨 · 변경할 때만 입력' : '인증이 필요하면 API 키 입력';
        $('provider-retire').hidden = !current || Boolean(current.retired);
        $('provider-save').disabled = Boolean(current && current.retired);
        $('provider-models-panel').hidden = !current;
        $('provider-manual').hidden = !current || !current.manual || Boolean(current.retired);
        $('provider-models').replaceChildren();
        if (!current) return;
        $('provider-status').textContent = current.last_error || `마지막 목록 확인: ${current.last_checked ? new Date(current.last_checked * 1000).toLocaleString() : '아직 없음'} · 목록은 60초 캐시`;
        for (const model of current.models) renderModel(model, current);
    }

    /** [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT.REASONING]
     * [EN rev.1]
     * [Role] Edits the complete allowed effort/default policy while keeping unsupported choices visible and disabled.
     * [Dependencies] Server-projected model ceiling, versioned profile and native checkbox/select controls.
     * [Impact] Only stored settings reach a probe; a known unsupported value cannot be selected here or at the server.
     */
    function reasoningFields(card, model, profile) {
        const section = document.createElement('fieldset'); section.className = 'provider-reasoning';
        const legend = document.createElement('legend'); legend.textContent = '사용자에게 허용할 추론 수준'; section.append(legend);
        const options = document.createElement('div'); options.className = 'provider-reasoning-options'; section.append(options);
        const inputs = new Map(), enabled = model.enabled_levels || profile.enabled_levels || [];
        const supported = model.supported_levels || reasoningLevels;
        const defaultLabel = document.createElement('label'); defaultLabel.append(document.createTextNode('새 선택의 기본 추론 수준'));
        const defaultSelect = document.createElement('select'); defaultSelect.dataset.reasoningDefault = model.id; defaultLabel.append(defaultSelect);
        /** [Role] Keeps the unsaved default inside the unsaved allowed set; an empty set explicitly means model-default behavior. */
        const renderDefaults = () => {
            const prior = defaultSelect.value || model.default_level || profile.default_level;
            const allowed = [...inputs].filter(([, input]) => input.checked).map(([level]) => level);
            defaultSelect.replaceChildren();
            for (const level of allowed.length ? allowed : ['default']) { const option = document.createElement('option'); option.value = level; option.textContent = level === 'default' ? '모델 기본값 · 수준 지정 안 함' : level; defaultSelect.append(option); }
            defaultSelect.value = allowed.includes(prior) ? prior : allowed.includes('medium') ? 'medium' : allowed[0] || 'default';
        };
        for (const level of reasoningLevels) {
            const input = field(options, level + (supported.includes(level) ? '' : ' · 모델 미지원'), 'checkbox', enabled.includes(level));
            input.dataset.reasoningLevel = level; input.disabled = !supported.includes(level); inputs.set(level, input);
            input.addEventListener('change', renderDefaults);
        }
        section.append(defaultLabel);
        const note = document.createElement('p'); note.textContent = (model.known_reasoning ? 'Qwen3.8 Flash Next 지원 사전 설정: off / low / medium / xhigh. ' : '이 모델의 지원 단계는 저장 후 기능 시험으로 확인합니다. ') + '허용 단계를 바꾸면 다시 시험해야 합니다. 모두 해제하면 추론 값을 보내지 않고 모델 기본 동작을 사용합니다. 기존 대화의 선택이나 접수된 요청은 바뀌지 않습니다.';
        section.append(note); card.append(section); renderDefaults(); return { inputs, defaultSelect };
    }

    /** [Role] Offers publication, versioned effort policy, verified context and inert capability tests for one model. */
    function renderModel(model, provider) {
        const card = document.createElement('form'); card.className = 'provider-model-card';
        const heading = document.createElement('h3'); heading.textContent = model.label; card.append(heading);
        const status = document.createElement('p'); const profile = JSON.parse(model.profile);
        status.textContent = !model.present ? '현재 목록에서 사라짐' : model.verified_revision === provider.revision ? `시험 통과 · ${profile.tools ? '장비 업무 가능' : '대화 전용'} · ${profile.levels && profile.levels.length ? '추론 단계 확인됨' : '추론 설정 미지원'}` : '현재 연결 설정에서 기능 시험 필요'; card.append(status);
        const fields = document.createElement('div'); fields.className = 'provider-fields'; card.append(fields);
        const label = field(fields, '표시 이름', 'text', model.label); label.required = true; label.maxLength = 80;
        const published = field(fields, '사용자에게 공개', 'checkbox', model.published);
        const order = field(fields, '공개 순서', 'number', model.sort_order); order.min = 0; order.max = 10000; order.required = true;
        const context = field(fields, '검증한 컨텍스트 token 한도', 'number', model.context_tokens); context.min = 2048; context.max = 1048576; context.required = true;
        const defaultModel = field(fields, '새 대화 기본 모델', 'checkbox', state.default_model === model.id);
        const tools = field(fields, '장비 도구 호출도 시험', 'checkbox', Boolean(profile.tools));
        const reasoning = field(fields, '허용한 추론 수준도 시험', 'checkbox', Boolean(profile.enabled_levels && profile.enabled_levels.length)); reasoning.disabled = !profile.enabled_levels || !profile.enabled_levels.length;
        const effort = reasoningFields(card, model, profile);
        const save = document.createElement('button'); save.type = 'submit'; save.textContent = '모델 설정 저장'; card.append(save);
        const probe = document.createElement('button'); probe.type = 'button'; probe.textContent = '저장된 설정으로 기능 시험'; probe.disabled = !provider.enabled || Boolean(provider.retired) || !model.present; card.append(probe);
        card.addEventListener('submit', async event => {
            event.preventDefault(); save.disabled = true;
            try { await api(`/api/admin/ai/providers/${provider.id}/models`, { id: model.id, label: label.value.trim(), published: published.checked, sort_order: Number(order.value), context_tokens: Number(context.value), revision: provider.revision, default: defaultModel.checked,
                reasoning_levels: [...effort.inputs].filter(([, input]) => input.checked).map(([level]) => level), reasoning_default: effort.defaultSelect.value, profile_revision: model.profile_revision }); await load(); notice('모델 설정을 저장했습니다. 기능 계약을 바꿨다면 시험을 다시 실행하세요.'); }
            catch (error) { notice(error.message); } finally { save.disabled = false; }
        });
        probe.addEventListener('click', async () => {
            probe.disabled = true;
            try { const value = await api(`/api/admin/ai/models/${model.id}/probe`, { tools: tools.checked, reasoning: reasoning.checked, client_key: crypto.randomUUID().replaceAll('-', '') }); notice('기능 시험을 내부 자원 그룹 큐에 접수했습니다.'); watchProbe(value.job_id); }
            catch (error) { notice(error.message); } finally { probe.disabled = false; }
        });
        $('provider-models').append(card);
    }

    /** [Role] Polls one accepted probe without restarting or replaying its model requests. */
    async function watchProbe(jid) {
        clearTimeout(probeTimer); if (disposed) return;
        try {
            const value = await api(`/api/ai/jobs/${jid}`);
            if (['done','failed','cancelled','recovery_required'].includes(value.state)) { await load(); notice(value.error || '모델 기능 시험을 완료했습니다.'); return; }
            notice(`모델 기능 시험: ${value.state === 'queued' ? '대기 중' : '진행 중'} · ${value.steps}단계 완료`);
            probeTimer = setTimeout(() => watchProbe(jid), 2000);
        } catch (error) { notice(error.message); }
    }

    /** [Role] Reloads safe state and preserves the selected connection. */
    async function load() { state = await api('/api/admin/ai/providers'); render(); }
    form.addEventListener('submit', async event => {
        event.preventDefault(); const data = Object.fromEntries(new FormData(form));
        const payload = { name: data.name.trim(), base_url: data.base_url.trim(), adapter: data.adapter, resource_group: data.resource_group,
            new_group: data.new_group.trim(), enabled: form.elements.enabled.checked, manual: form.elements.manual.checked, sort_order: Number(data.sort_order), revision: current ? current.revision : 0 };
        if (data.api_key || form.elements.clear_key.checked) payload.api_key = form.elements.clear_key.checked ? '' : data.api_key;
        $('provider-save').disabled = true;
        try { const value = await api('/api/admin/ai/providers' + (current ? '/' + current.id : ''), payload); form.elements.api_key.value = ''; selectedId = value.id; await load(); notice('연결을 저장했습니다. 모델 자동 조회와 기능 시험을 진행해 주세요.'); }
        catch (error) { notice(error.message); } finally { $('provider-save').disabled = Boolean(current && current.retired); }
    });
    $('provider-retire').addEventListener('click', async () => {
        if (!current || !window.confirm('이 연결의 신규 요청을 중지하고 폐기하시겠습니까? 기존 기록과 실행 중 요청의 종료 보고는 보존됩니다.')) return;
        try { await api(`/api/admin/ai/providers/${current.id}`, { name: current.name, base_url: current.base_url, adapter: current.adapter, resource_group: current.resource_group, enabled: false, retired: true, manual: Boolean(current.manual), sort_order: current.sort_order, revision: current.revision }); await load(); notice('연결을 폐기했습니다. 기존 기록은 보존됩니다.'); }
        catch (error) { notice(error.message); }
    });
    $('provider-discover').addEventListener('click', async () => { if (!current) return; try { await api(`/api/admin/ai/providers/${current.id}/discover`, {}); await load(); notice('모델 목록을 갱신했습니다.'); } catch (error) { notice(error.message); await load(); } });
    $('provider-manual').addEventListener('submit', async event => {
        event.preventDefault(); if (!current) return; const data = Object.fromEntries(new FormData(event.currentTarget));
        try { await api(`/api/admin/ai/providers/${current.id}/models`, { upstream: data.upstream.trim(), label: data.label.trim(), published: true, sort_order: 0, context_tokens: 4096, revision: current.revision }); event.currentTarget.reset(); await load(); }
        catch (error) { notice(error.message); }
    });
    $('provider-new').addEventListener('click', () => { selectedId = null; edit(null); });
    $('provider-reload').addEventListener('click', () => load().catch(error => notice(error.message)));
    window.addEventListener('pagehide', () => { disposed = true; clearTimeout(probeTimer); form.elements.api_key.value = ''; }, { once: true });
    load().catch(error => notice(error.message));
})();
