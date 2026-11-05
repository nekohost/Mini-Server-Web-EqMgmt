/* [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT]
 * [EN rev.4]
 * [Role] Uses one locked operation flow and native result dialogs for provider administration.
 * [Dependencies] Same-origin CSRF/revision APIs, existing global loading, owner-bound probe reads and safe DOM.
 * [Impact] Separates ACK/refresh/unknown outcomes, never resends a POST, and never cancels shared generation.
 */
(function () {
    'use strict';
    const root = document.getElementById('ai-providers-admin');
    if (!root) return;
    const $ = id => document.getElementById(id), form = $('provider-form');
    const reasoningLevels = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];
    const controls = $('provider-controls'), dialog = $('provider-dialog');
    const disabledBefore = new Map();
    const probeStorage = 'eqmgmt.ai.admin.probe.v1';
    let state = null, current = null, selectedId = null, disposed = false, probeTimer = null;
    let busy = false, dirty = false, pending = null, probeJob = null, probeClientKey = null;
    let dialogTail = Promise.resolve();
    const notice = text => { $('provider-notice').textContent = text || ''; };

    /** [Role] Reports transport uncertainty separately from a definite validation/permission rejection. */
    async function api(path, data) {
        let response, value;
        const controller = new AbortController(), requestTimer = setTimeout(() => controller.abort(), 30000);
        try {
            response = await fetch(path, { method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
                signal: controller.signal,
                headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRFToken': root.dataset.csrf },
                body: data === undefined ? undefined : JSON.stringify(data) });
            value = await response.json();
        } catch (_) {
            const error = Error(data === undefined ? '상태를 조회하지 못했습니다. 연결을 확인해 주세요.' : '요청 응답을 확인하지 못했습니다. 서버에 반영되었을 수 있습니다.');
            error.uncertain = data !== undefined; throw error;
        } finally {
            clearTimeout(requestTimer);
        }
        if (!response.ok || value.success !== true) {
            const error = Error(value.message || '연결 관리 요청을 완료하지 못했습니다.');
            error.status = response.status; error.uncertain = data !== undefined && response.status >= 500; throw error;
        }
        return value;
    }

    /** [Role] Captures stable IDs so focus can return even after the affected form was rendered again. */
    function focusTarget(element = document.activeElement) {
        return element && { id: element.id, key: element.dataset && element.dataset.focusKey,
            form: element.form && element.form.id, name: element.name };
    }

    /** [Role] Restores focus to a surviving equivalent control or the current connection heading. */
    function restoreFocus(target) {
        if (disposed || dialog.open) return;
        const candidate = target && (target.id && $(target.id) || target.key && [...root.querySelectorAll('[data-focus-key]')].find(node => node.dataset.focusKey === target.key) ||
            target.form && target.name && $(target.form) && $(target.form).elements.namedItem(target.name));
        const element = candidate && !candidate.disabled && !candidate.closest('[hidden],[inert]') ? candidate : $('provider-heading');
        if (element) element.focus({ preventScroll: true });
    }

    /** [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT.DIALOG]
     * [EN rev.3]
     * [Role] Serializes text-only native dialogs and restores stable focus atomically with submit/Escape closure.
     * [Dependencies] A labeled dialog outside the locked controls and the browser top layer.
     * [Impact] Closure restores focus once; a prior queued close event cannot resolve the next still-open dialog.
     */
    function resultDialog(title, message, options = {}) {
        const next = dialogTail.then(() => new Promise(resolve => {
            if (disposed) { resolve(false); return; }
            const returnTo = options.focus || focusTarget();
            $('provider-dialog-title').textContent = title; $('provider-dialog-message').textContent = message;
            const accept = $('provider-dialog-accept'), cancel = $('provider-dialog-cancel');
            accept.textContent = options.accept || '확인'; cancel.textContent = options.cancel || '취소'; cancel.hidden = !options.confirm;
            dialog.returnValue = '';
            let finished = false;
            const closed = () => {
                if (finished || dialog.open) return;
                finished = true;
                dialog.removeEventListener('close', closed);
                dialog.removeEventListener('submit', submitted);
                dialog.removeEventListener('cancel', cancelled);
                restoreFocus(returnTo);
                resolve(dialog.returnValue === 'accept');
            };
            // Native method=dialog clears open before its queued close event. Close in the
            // initiating event so focus is restored before another handler observes closure.
            const closeWithValue = value => { dialog.close(value); closed(); };
            const submitted = event => { event.preventDefault(); closeWithValue(event.submitter ? event.submitter.value : 'cancel'); };
            const cancelled = event => { event.preventDefault(); closeWithValue('cancel'); };
            dialog.addEventListener('close', closed);
            dialog.addEventListener('submit', submitted);
            dialog.addEventListener('cancel', cancelled);
            dialog.showModal();
            (options.danger ? cancel : accept).focus();
        }));
        dialogTail = next.catch(() => false);
        return next;
    }

    /** [Role] Locks all form/selection actions during a short request while preserving intrinsic disabled states. */
    function setBusy(value, message = '') {
        busy = value; root.setAttribute('aria-busy', String(value));
        if (value) {
            controls.querySelectorAll('input,select,textarea,button').forEach(node => {
                if (!disabledBefore.has(node)) disabledBefore.set(node, node.disabled);
                node.disabled = true;
            });
            controls.inert = true;
            $('provider-busy-status').textContent = message;
            window.showGlobalLoading(message);
        } else {
            controls.inert = false;
            for (const [node, disabled] of disabledBefore) if (node.isConnected) node.disabled = disabled;
            disabledBefore.clear(); $('provider-busy-status').textContent = '';
            window.hideGlobalLoading(); applyRestrictions();
        }
    }

    /** [Role] Keeps unresolved writes from being accidentally repeated and prevents a second tracked probe. */
    function applyRestrictions() {
        $('provider-reconcile').hidden = !pending; $('provider-dismiss-pending').hidden = !pending;
        $('provider-reconcile').disabled = busy; $('provider-dismiss-pending').disabled = busy;
        controls.querySelectorAll('[data-mutation]').forEach(node => {
            if (!busy) node.disabled = !state || Boolean(pending) || node.dataset.intrinsicDisabled === 'true' || node.dataset.probe === 'true' && Boolean(probeJob || probeClientKey);
        });
        $('provider-reload').disabled = busy || Boolean(pending);
        $('provider-new').disabled = busy || !state || Boolean(pending);
        $('provider-list').querySelectorAll('button').forEach(node => { node.disabled = busy || Boolean(pending); });
    }

    /** [Role] Marks fixed controls for request locking without overriding known unsupported settings. */
    function mutationControl(node, disabled = false) {
        node.dataset.mutation = 'true'; node.dataset.intrinsicDisabled = String(disabled); node.disabled = disabled; return node;
    }

    /** [Role] Creates bounded labeled controls using text nodes, never model-provided HTML. */
    function field(container, label, type, value) {
        const wrapper = document.createElement('label'); wrapper.append(document.createTextNode(label));
        const input = document.createElement('input'); input.type = type;
        if (type === 'checkbox') { input.checked = Boolean(value); wrapper.className = 'provider-check'; } else input.value = value;
        wrapper.append(input); container.append(wrapper); return input;
    }

    /** [Role] Loads a safe snapshot only after a read succeeds; failed reads preserve all displayed lists and inputs. */
    async function load() {
        const fresh = await api('/api/admin/ai/providers');
        state = fresh; render(); return fresh;
    }

    /** [Role] Displays safe registry metadata and preserves the selected opaque provider ID. */
    function render() {
        $('provider-encryption').textContent = state.encryption_configured ? '독립 암호화 키 설정됨' : 'API 키 저장 전 서버의 독립 암호화 키 설정 필요';
        $('provider-list').replaceChildren();
        for (const provider of state.providers) {
            const button = document.createElement('button'); button.type = 'button'; button.textContent = provider.name + (provider.retired ? ' · 폐기' : provider.enabled ? '' : ' · 중지');
            button.dataset.providerId = provider.id; button.dataset.focusKey = 'connection:' + provider.id;
            button.setAttribute('aria-current', String(provider.id === selectedId));
            button.addEventListener('click', () => switchEditor(provider)); $('provider-list').append(button);
        }
        edit(selectedId ? state.providers.find(provider => provider.id === selectedId) : null);
        if (busy) setBusy(true, $('provider-busy-status').textContent); else applyRestrictions();
    }

    /** [Role] Confirms before discarding unsaved settings; a modal or active request blocks selection races. */
    async function switchEditor(provider) {
        if (busy || pending || dialog.open) return;
        if (dirty && !await resultDialog('입력 변경 폐기', '저장하지 않은 입력을 폐기하고 다른 연결을 열까요?', { confirm: true, danger: true, accept: '입력 폐기' })) return;
        edit(provider); applyRestrictions();
    }

    /** [Role] Opens one revision without reading credentials; switching explicitly clears a previous key input. */
    function edit(provider) {
        current = provider || null; selectedId = current && current.id; form.reset(); dirty = false;
        $('provider-list').querySelectorAll('button').forEach(button => button.setAttribute('aria-current', String(button.dataset.providerId === selectedId)));
        $('provider-heading').textContent = current ? current.name + ' · 설정 ' + current.revision : '연결 추가';
        const groups = document.createDocumentFragment();
        for (const group of state.groups) { const option = document.createElement('option'); option.value = group.id; option.textContent = group.name; groups.append(option); }
        $('provider-group').replaceChildren(groups);
        for (const name of ['name','base_url','adapter','resource_group','sort_order','enabled','manual']) if (current) {
            const input = form.elements.namedItem(name); if (input.type === 'checkbox') input.checked = Boolean(current[name]); else input.value = current[name];
        }
        form.elements.api_key.placeholder = current && current.has_key ? '키 저장됨 · 변경할 때만 입력' : '인증이 필요하면 API 키 입력';
        $('provider-retire').hidden = !current || Boolean(current.retired);
        mutationControl($('provider-save'), Boolean(current && current.retired));
        mutationControl($('provider-retire'), !current || Boolean(current.retired));
        mutationControl($('provider-discover'), !current || Boolean(current.retired));
        $('provider-models-panel').hidden = !current;
        $('provider-manual').hidden = !current || !current.manual || Boolean(current.retired);
        $('provider-models').replaceChildren(); $('provider-status').textContent = '';
        if (!current) return;
        $('provider-status').textContent = current.last_error || '마지막 목록 확인: ' + (current.last_checked ? new Date(current.last_checked * 1000).toLocaleString() : '아직 없음') + ' · 목록은 60초 캐시';
        for (const model of current.models) renderModel(model, current);
    }

    /** [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT.OPERATION]
     * [EN rev.1]
     * [Role] Separates committed writes, failed refreshes and unknown POST outcomes without automatic replay.
     * [Dependencies] An operation-specific read-only verifier and optimistic provider/profile revisions.
     * [Impact] 409/input failures preserve inputs; only acknowledged saves clear key fields or reset forms.
     */
    async function mutate(options) {
        if (busy || pending || dialog.open) return;
        const focus = focusTarget();
        if (options.confirm && !await resultDialog(options.confirm.title, options.confirm.message, { confirm: true, danger: true, accept: options.confirm.accept, focus })) return;
        if (busy || pending || disposed) return;
        setBusy(true, options.loading);
        let title, message;
        try {
            const value = await options.send();
            if (options.ack) options.ack(value);
            try {
                await load(); title = options.title; message = options.success;
            } catch (_) {
                pending = { acknowledged: true, verify: options.verify, title: options.title };
                title = options.title + ' · 목록 갱신 실패';
                message = '서버의 완료 응답을 받았습니다. 작업은 완료되었으나 목록을 다시 읽지 못했습니다. 결과 확인으로 목록만 갱신해 주세요. 저장 요청은 다시 보내지 않습니다.';
            }
        } catch (error) {
            if (error.uncertain) {
                pending = { acknowledged: false, verify: options.verify, title: options.title };
                title = '결과 확인 필요';
                message = '요청 응답이 유실되어 반영 여부를 확정할 수 없습니다. 자동 재전송하지 않습니다. ';
                try { const result = await options.verify(); message += result.message; } catch (_) { message += '상태 조회도 실패했습니다. 연결이 복구되면 결과 확인을 눌러 주세요.'; }
            } else {
                title = error.status === 409 ? '다른 변경과 충돌했습니다' : '요청을 완료하지 못했습니다';
                message = error.message + (error.status === 409 ? ' 입력은 유지했습니다. 현재 설정을 새로고침한 뒤 변경 내용을 다시 확인해 주세요.' : ' 입력과 기존 목록은 유지했습니다.');
            }
        } finally {
            setBusy(false);
        }
        notice(title + ' · ' + message); await resultDialog(title, message, { focus });
    }

    /** [Role] Verifies current public settings after response loss without claiming secret equality or resending writes. */
    function providerVerification(id, priorIds, expected) {
        return async () => {
            const fresh = await api('/api/admin/ai/providers');
            const rows = id ? fresh.providers.filter(provider => provider.id === id) : fresh.providers.filter(provider => !priorIds.includes(provider.id) && provider.name === expected.name && provider.base_url === expected.base_url);
            const row = rows.length === 1 ? rows[0] : null;
            return { fresh, selected: row && row.id,
                message: row ? '현재 목록에서 연결 “' + row.name + '”의 설정 ' + row.revision + (row.retired ? ' · 폐기 상태' : '') + '를 확인했습니다. 비밀 키의 내용이나 이 요청의 처리 여부는 목록 정보만으로 확정할 수 없습니다. 확인한 설정을 불러와 검토해 주세요.' :
                    '현재 목록에서 요청 대상을 확정하지 못했습니다. 아직 처리 중일 수 있습니다. 잠시 후 다시 확인해 주세요.' };
        };
    }

    /** [Role] Reads the affected model inventory after an unknown save/add/discovery, preserving the unsaved form. */
    function modelVerification(providerId, modelId, upstream) {
        return async () => {
            const fresh = await api('/api/admin/ai/providers'), provider = fresh.providers.find(value => value.id === providerId);
            const model = provider && provider.models.find(value => modelId ? value.id === modelId : value.upstream === upstream);
            return { fresh, selected: providerId, message: model ? '현재 목록에서 모델 “' + model.label + '”을 확인했습니다. 설정과 시험 상태를 다시 검토해 주세요.' :
                '현재 모델 목록을 읽었습니다. 요청한 변경의 반영 여부는 현재 설정에서 직접 확인해 주세요.' };
        };
    }

    /** [Role] Fetches unresolved results and requires an explicit choice before replacing preserved user input. */
    async function reconcile() {
        if (busy || !pending || dialog.open) return;
        const item = pending, focus = focusTarget(); setBusy(true, '처리 결과 확인 중입니다...');
        let result;
        try { result = await item.verify(); }
        catch (error) { setBusy(false); await resultDialog('결과 조회 실패', error.message + ' 이전 요청은 다시 보내지 않았습니다.', { focus }); return; }
        setBusy(false);
        if (result.probe) {
            if (result.job_id) {
                pending = null; probeJob = result.job_id; saveProbe(); applyRestrictions(); watchProbe();
                await resultDialog('기능 시험 접수 확인', '저장된 접수 키로 기존 시험을 찾았습니다. 새 시험을 만들지 않고 이 요청의 상태 조회를 계속합니다.', { focus });
            } else await resultDialog('접수 결과 확인 필요', result.message, { focus });
            return;
        }
        const accepted = await resultDialog(item.acknowledged ? '완료 결과 확인' : '현재 설정 확인', result.message + '\n확인한 목록을 불러오면 저장하지 않은 입력은 지워집니다. 이전 요청을 다시 전송하지 않습니다.',
            { confirm: true, accept: '확인한 설정 불러오기', cancel: '입력 유지', focus });
        if (accepted) {
            pending = null; if (result.selected) selectedId = result.selected; state = result.fresh; render(); applyRestrictions();
            restoreFocus(focus);
            notice('현재 설정을 불러왔습니다. 필요한 변경은 내용을 확인한 뒤 직접 저장해 주세요.');
        }
    }

    /** [Role] Allows an explicit manual exit from an unknown state without replaying a request or asserting failure. */
    async function dismissPending() {
        if (busy || !pending || dialog.open) return;
        if (!await resultDialog('확인 상태 해제', '이전 요청은 이미 반영되었거나 아직 처리 중일 수 있습니다. 현재 목록을 다시 읽고 입력을 지운 뒤 검토를 계속할까요? 같은 연결을 다시 추가하기 전에 기존 목록을 확인하세요. 요청은 자동 재전송하지 않습니다.',
            { confirm: true, danger: true, accept: '현재 목록에서 계속' })) return;
        setBusy(true, '현재 목록 확인 중입니다...');
        let failure;
        try { const fresh = await api('/api/admin/ai/providers'); pending = null; if (!probeJob) { probeClientKey = null; clearSavedProbe(); } state = fresh; render(); notice('현재 목록을 불러왔습니다. 이전 요청을 재전송하지 않았습니다.'); }
        catch (error) { failure = error; }
        finally { setBusy(false); }
        if (failure) await resultDialog('목록 조회 실패', failure.message);
    }

    /** [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT.REASONING]
     * [EN rev.2]
     * [Role] Edits the complete allowed effort/default policy inside the shared operation-lock and model-save flow.
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


    /** [Role] Offers saved model settings and one tracked inert probe with stable keyboard-focus targets. */
    function renderModel(model, provider) {
        const card = document.createElement('form'); card.className = 'provider-model-card'; card.dataset.modelId = model.id;
        const heading = document.createElement('h3'); heading.textContent = model.label; card.append(heading);
        const status = document.createElement('p'); const profile = JSON.parse(model.profile);
        status.textContent = !model.present ? '현재 목록에서 사라짐' : model.verified_revision === provider.revision ? '시험 통과 · ' + (profile.tools ? '장비 업무 가능' : '대화 전용') : '현재 연결 설정에서 기능 시험 필요'; card.append(status);
        const fields = document.createElement('div'); fields.className = 'provider-fields'; card.append(fields);
        const label = field(fields, '표시 이름', 'text', model.label); label.required = true; label.maxLength = 80;
        const published = field(fields, '사용자에게 공개', 'checkbox', model.published);
        const order = field(fields, '공개 순서', 'number', model.sort_order); order.min = 0; order.max = 10000; order.required = true;
        const context = field(fields, '검증한 컨텍스트 token 한도', 'number', model.context_tokens); context.min = 2048; context.max = 1048576; context.required = true;
        const defaultModel = field(fields, '새 대화 기본 모델', 'checkbox', state.default_model === model.id);
        const tools = field(fields, '장비 도구 호출도 시험', 'checkbox', Boolean(profile.tools));
        const reasoning = field(fields, '허용한 추론 수준도 시험', 'checkbox', Boolean(profile.enabled_levels && profile.enabled_levels.length)); reasoning.disabled = !profile.enabled_levels || !profile.enabled_levels.length;
        const effort = reasoningFields(card, model, profile);
        const actions = document.createElement('div'); actions.className = 'provider-actions'; card.append(actions);
        const save = mutationControl(document.createElement('button'), Boolean(provider.retired)); save.type = 'submit'; save.textContent = '모델 설정 저장'; actions.append(save);
        const probe = mutationControl(document.createElement('button'), !provider.enabled || Boolean(provider.retired) || !model.present); probe.type = 'button'; probe.dataset.probe = 'true'; probe.textContent = '저장된 설정으로 기능 시험'; actions.append(probe);
        card.querySelectorAll('input,select,button').forEach((element, index) => { element.dataset.focusKey = 'model:' + model.id + ':' + index; });
        card.addEventListener('input', () => { dirty = true; });
        card.addEventListener('submit', event => {
            event.preventDefault(); if (busy || pending || dialog.open || !card.reportValidity()) return;
            const payload = { id: model.id, label: label.value.trim(), published: published.checked, sort_order: Number(order.value), context_tokens: Number(context.value), revision: provider.revision, default: defaultModel.checked,
                reasoning_levels: [...effort.inputs].filter(([, input]) => input.checked).map(([level]) => level), reasoning_default: effort.defaultSelect.value, profile_revision: model.profile_revision };
            mutate({ loading: '모델 설정 저장 중입니다...', title: '모델 설정 저장 완료', success: '모델 “' + payload.label + '” 설정을 저장했습니다. 기능 계약이 바뀌었다면 현재 설정으로 다시 시험해 주세요.',
                send: () => api('/api/admin/ai/providers/' + provider.id + '/models', payload), verify: modelVerification(provider.id, model.id) });
        });
        probe.addEventListener('click', () => startProbe(model, tools.checked, reasoning.checked));
        $('provider-models').append(card);
    }

    /** [Role] Saves only opaque probe identifiers for same-session status recovery; no prompt/key is stored. */
    function saveProbe() {
        try { sessionStorage.setItem(probeStorage, JSON.stringify({ job_id: probeJob, client_key: probeClientKey })); } catch (_) { /* Status can still be resumed in this page. */ }
    }

    /** [Role] Reads an idempotency key to recover an existing accepted probe, never repeating the POST. */
    function probeVerification(clientKey) {
        return async () => {
            const value = await api('/api/admin/ai/probes?client_key=' + encodeURIComponent(clientKey));
            return { probe: true, job_id: value.found ? value.job_id : null, message: '접수 키로 시험을 아직 찾지 못했습니다. 처리 중일 수 있으므로 잠시 후 결과 확인을 다시 눌러 주세요. 새 시험은 자동 접수하지 않습니다.' };
        };
    }

    /** [MINI-COMMENT: ASSISTANT.PROVIDERS.CLIENT.PROBE]
     * [EN rev.1]
     * [Role] Ends the global overlay after queue ACK, then polls one owner-bound job with no total-time cancellation.
     * [Dependencies] A stable client key, job read API and session-scoped opaque identifiers.
     * [Impact] Lost status responses are never reported as model failure; leaving the page never controls shared Strata.
     */
    async function startProbe(model, tools, reasoning) {
        if (busy || pending || probeJob || probeClientKey || dialog.open) return;
        const focus = focusTarget();
        if (dirty && !await resultDialog('저장된 설정으로 시험', '저장하지 않은 입력은 이번 기능 시험에 반영되지 않습니다. 현재 서버에 저장된 설정으로 시험할까요?', { confirm: true, accept: '저장된 설정 시험', focus })) return;
        probeClientKey = crypto.randomUUID().replaceAll('-', ''); saveProbe(); setBusy(true, '기능 시험 접수 중입니다...');
        let title, message;
        try {
            const value = await api('/api/admin/ai/models/' + model.id + '/probe', { tools, reasoning, client_key: probeClientKey });
            probeJob = value.job_id; saveProbe(); title = '기능 시험 접수 완료';
            message = '내부 자원 그룹 큐에 접수했습니다. 접수는 시험 성공을 뜻하지 않습니다. 대기·진행·최종 결과는 상태 영역에서 확인할 수 있습니다. 긴 생성 중에도 화면을 사용할 수 있습니다.';
        } catch (error) {
            if (error.uncertain) {
                pending = { acknowledged: false, verify: probeVerification(probeClientKey), title: '기능 시험 접수' };
                title = '기능 시험 접수 결과 확인 필요'; message = error.message + ' 결과 확인에서 같은 접수 키를 조회해 주세요. 새 시험은 자동 접수하지 않습니다.';
                try { const found = await pending.verify(); if (found.job_id) { probeJob = found.job_id; pending = null; saveProbe(); title = '기능 시험 접수 확인'; message = '기존 접수 키로 시험을 찾았습니다. 새 요청 없이 상태 조회를 계속합니다.'; } } catch (_) { /* The key remains available for a read-only retry. */ }
            } else {
                title = '기능 시험 접수 실패'; message = error.message; probeClientKey = null; clearSavedProbe();
            }
        } finally { setBusy(false); }
        notice(title + ' · ' + message); if (probeJob) watchProbe();
        await resultDialog(title, message, { focus });
    }

    /** [Role] Clears only this screen's opaque resume token after a terminal result, never browser conversations. */
    function clearSavedProbe() {
        try { sessionStorage.removeItem(probeStorage); } catch (_) { /* No model control is performed. */ }
    }

    /** [Role] Displays accepted, draining and paused-read states independently from final model success. */
    async function watchProbe() {
        clearTimeout(probeTimer); if (disposed || !probeJob) return;
        const jid = probeJob; $('provider-probe').hidden = false; $('provider-probe-resume').hidden = true;
        try {
            const value = await api('/api/ai/jobs/' + jid);
            if (disposed || probeJob !== jid) return;
            if (['done','failed','cancelled','recovery_required'].includes(value.state)) {
                const messages = { done: ['기능 시험 성공', '저장된 모델의 기능 시험이 정상 완료되었습니다.'],
                    failed: ['기능 시험 실패', value.error || '모델 기능 시험이 실패했습니다. 연결과 저장된 설정을 확인해 주세요.'],
                    cancelled: ['기능 시험 취소됨', '기능 시험이 취소되었습니다. 새 시험을 자동 접수하지 않습니다.'],
                    recovery_required: ['기능 시험 종료 확인 필요', 'upstream 종료가 확인되지 않았습니다. 현재 실행 점유를 보존하며 관리자 확인이 필요합니다. 새 시험이나 공유 모델 초기화를 자동 실행하지 않습니다.'] };
                const result = messages[value.state]; $('provider-probe-status').textContent = result[0] + ' · ' + (value.steps || 0) + '단계 완료';
                probeJob = null; probeClientKey = null; clearSavedProbe(); applyRestrictions();
                notice(result[0] + ' · 설정 목록은 새로고침으로 확인해 주세요.');
                await resultDialog(result[0], result[1] + ' 편집 중인 입력은 유지했습니다. 최신 시험 결과를 모델 목록에 반영하려면 새로고침해 주세요.');
                return;
            }
            const labels = { queued: '큐 대기 중', running: '진행 중', draining: '자기 요청 종료 확인 중' };
            $('provider-probe-status').textContent = '기능 시험 · ' + (labels[value.state] || '처리 상태 확인 중') + ' · ' + (value.steps || 0) + '단계 완료';
            probeTimer = setTimeout(watchProbe, 2000);
        } catch (error) {
            if (disposed || probeJob !== jid) return;
            $('provider-probe-status').textContent = '상태 조회 중단 · 시험 결과는 아직 확인되지 않았습니다.';
            $('provider-probe-resume').hidden = false;
            await resultDialog('시험 상태 조회 실패', error.message + ' 시험 자체의 실패로 처리하지 않았습니다. 저장된 job ID로 조회 재개를 눌러 주세요. 새 시험을 접수하거나 공유 모델을 취소하지 않습니다.');
        }
    }

    /** [Role] Validates and saves connection input through the single request flow. */
    form.addEventListener('submit', event => {
        event.preventDefault(); if (busy || pending || dialog.open || !state || !form.reportValidity()) return;
        const data = Object.fromEntries(new FormData(form)), original = current;
        const payload = { name: data.name.trim(), base_url: data.base_url.trim(), adapter: data.adapter, resource_group: data.resource_group,
            new_group: data.new_group.trim(), enabled: form.elements.enabled.checked, manual: form.elements.manual.checked, sort_order: Number(data.sort_order), revision: original ? original.revision : 0 };
        if (data.api_key || form.elements.clear_key.checked) payload.api_key = form.elements.clear_key.checked ? '' : data.api_key;
        const verify = providerVerification(original && original.id, state.providers.map(provider => provider.id), { name: payload.name, base_url: payload.base_url });
        mutate({ loading: '연결 저장 중입니다...', title: '연결 저장 완료', success: '연결 “' + payload.name + '”을 저장했습니다. 모델 목록을 확인하고 현재 설정으로 기능 시험을 진행해 주세요.',
            send: () => api('/api/admin/ai/providers' + (original ? '/' + original.id : ''), payload),
            ack: value => { form.elements.api_key.value = ''; form.elements.clear_key.checked = false; selectedId = value.id; }, verify });
    });

    /** [Role] Requires named retirement confirmation while preserving all historic and shared model state. */
    $('provider-retire').addEventListener('click', () => {
        const provider = current; if (!provider) return;
        const payload = { name: provider.name, base_url: provider.base_url, adapter: provider.adapter, resource_group: provider.resource_group, enabled: false, retired: true, manual: Boolean(provider.manual), sort_order: provider.sort_order, revision: provider.revision };
        mutate({ loading: '연결 폐기 중입니다...', title: '연결 폐기 완료', success: '연결 “' + provider.name + '”을 폐기했습니다. 기존 기록과 실행 중 요청의 종료 보고는 보존되며 공유 모델 프로세스는 중단하지 않습니다.',
            confirm: { title: '연결 폐기', message: '“' + provider.name + '” 연결의 신규 요청을 중지하고 폐기할까요? 폐기한 연결은 다시 활성화할 수 없습니다. 기존 기록은 보존하며 공유 모델 프로세스는 중단하지 않습니다.', accept: '연결 폐기' },
            send: () => api('/api/admin/ai/providers/' + provider.id, payload), verify: providerVerification(provider.id, [], { name: provider.name, base_url: provider.base_url }) });
    });

    /** [Role] Explicit inventory refresh uses a loading/result flow and never erases prior data on failure. */
    $('provider-discover').addEventListener('click', () => {
        const provider = current; if (!provider) return;
        mutate({ loading: '모델 목록 조회 중입니다...', title: '모델 목록 조회 완료', success: '연결 “' + provider.name + '”의 모델 목록을 갱신했습니다. 목록 조회는 기능 시험을 대신하지 않습니다.',
            send: () => api('/api/admin/ai/providers/' + provider.id + '/discover', {}), verify: modelVerification(provider.id) });
    });

    /** [Role] Registers a manually opted-in model without retrying an unknown creation. */
    $('provider-manual').addEventListener('submit', event => {
        event.preventDefault(); const manualForm = event.currentTarget, provider = current; if (busy || pending || dialog.open || !provider || !manualForm.reportValidity()) return;
        const data = Object.fromEntries(new FormData(manualForm)), upstream = data.upstream.trim(), label = data.label.trim();
        mutate({ loading: '수동 모델 등록 중입니다...', title: '수동 모델 등록 완료', success: '모델 “' + label + '”을 등록했습니다. 설정을 확인하고 기능 시험을 진행해 주세요.',
            send: () => api('/api/admin/ai/providers/' + provider.id + '/models', { upstream, label, published: true, sort_order: 0, context_tokens: 4096, revision: provider.revision }),
            ack: () => manualForm.reset(), verify: modelVerification(provider.id, null, upstream) });
    });

    /** [Role] Reads fresh metadata explicitly, confirms input loss and reports a read error without replaying writes. */
    async function reload() {
        if (busy || pending || dialog.open) return;
        const focus = focusTarget();
        if (dirty && !await resultDialog('현재 설정 새로고침', '저장하지 않은 입력을 폐기하고 서버의 현재 설정을 불러올까요?', { confirm: true, danger: true, accept: '입력 폐기 후 조회', focus })) return;
        setBusy(true, '연결 목록 조회 중입니다...');
        let error;
        try { await load(); notice('현재 연결 목록을 불러왔습니다.'); } catch (value) { error = value; }
        finally { setBusy(false); }
        await resultDialog(error ? '목록 조회 실패' : '목록 조회 완료', error ? error.message + ' 기존 목록과 입력은 유지했습니다.' : '현재 연결과 모델 설정을 불러왔습니다.', { focus });
    }
    controls.addEventListener('input', () => { dirty = true; });
    controls.addEventListener('change', () => { dirty = true; });
    $('provider-new').addEventListener('click', () => switchEditor(null));
    $('provider-reload').addEventListener('click', reload);
    $('provider-reconcile').addEventListener('click', reconcile);
    $('provider-dismiss-pending').addEventListener('click', dismissPending);
    $('provider-probe-resume').addEventListener('click', () => {
        if (busy || dialog.open) return;
        if (probeJob) watchProbe(); else if (pending) reconcile();
    });
    $('provider-probe-forget').addEventListener('click', async () => {
        if (busy || dialog.open || !await resultDialog('화면 상태 추적 종료', '이 화면의 상태 조회만 종료할까요? 접수된 시험은 계속 처리될 수 있습니다. 모델 요청 취소나 공유 모델 초기화는 수행하지 않습니다.', { confirm: true, accept: '상태 추적 종료' })) return;
        clearTimeout(probeTimer); probeJob = null; probeClientKey = null; clearSavedProbe(); $('provider-probe').hidden = true; applyRestrictions();
    });
    window.addEventListener('pagehide', () => {
        disposed = true; clearTimeout(probeTimer); form.elements.api_key.value = '';
        if (busy) window.hideGlobalLoading();
    }, { once: true });

    /** [Role] Initializes via safe reads and resumes a stored probe without sending any new model request. */
    async function initialize() {
        setBusy(true, 'AI 연결 목록 조회 중입니다...');
        let error;
        try { await load(); } catch (value) { error = value; } finally { setBusy(false); }
        if (error) { await resultDialog('연결 목록 조회 실패', error.message + ' 새로고침으로 다시 조회해 주세요.'); return; }
        try {
            const saved = JSON.parse(sessionStorage.getItem(probeStorage) || 'null');
            if (saved && /^[0-9a-f]{32}$/.test(saved.client_key || '')) {
                probeClientKey = saved.client_key;
                if (/^[0-9a-f]{32}$/.test(saved.job_id || '')) { probeJob = saved.job_id; watchProbe(); }
                else { pending = { acknowledged: false, verify: probeVerification(probeClientKey), title: '기능 시험 접수' }; notice('이전 기능 시험의 접수 결과를 확인해 주세요. 새 시험은 자동 접수하지 않습니다.'); }
                applyRestrictions();
            }
        } catch (_) { clearSavedProbe(); }
    }
    initialize();
})();
