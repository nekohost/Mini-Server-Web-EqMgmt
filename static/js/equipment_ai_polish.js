/* [MINI-COMMENT: ASSISTANT.POLISH] [EN rev.2]
 * [Role] Measures native disclosure space and synchronizes header/input status from the same server-confirmed connection/own-queue evidence.
 * [Dependencies] Existing assistant DOM, authenticated passive status API and assistant-status-context events from the chat controller.
 * [Impact] No chat/model/draft/scroll state or provider request is changed; late responses are discarded and all local observers/timers are disposed.
 */
(function (global) {
    'use strict';
    global.EquipmentAiPolish?.destroy();
    let disposed = false;
    const cleanups = [];

    /* [MINI-COMMENT: ASSISTANT.POLISH.DISCLOSURES] [EN rev.1]
     * [Role] Uses the real control/summary dimensions to choose two inline lines or a narrow/zoom fallback.
     * [Dependencies] Native details retain their original controls; open panels are positioned below the action row and reserve an equal-height spacer.
     * [Impact] Independent open states and focus survive resize; full-width bodies cannot cover the reasoning/send controls or following errors.
     */
    function disclosures(root) {
        const actions = root.querySelector('.ai-composer-actions');
        const group = root.querySelector('.ai-inline-disclosures');
        const level = root.querySelector('.ai-level-control');
        const send = root.querySelector('#ai-send');
        const details = group ? Array.from(group.querySelectorAll('details')) : [];
        if (!actions || !group || !level || !send || !details.length) return () => {};
        let frame = null, stopped = false;
        const assign = (node, name, value) => {
            if (node.style.getPropertyValue(name) !== value) node.style.setProperty(name, value);
        };
        const measure = () => {
            frame = null;
            if (stopped || !root.isConnected) return;
            const visible = details.filter(item => !item.hidden);
            const summaries = visible.map(item => item.querySelector('summary'));
            const gap = parseFloat(getComputedStyle(actions).columnGap) || 0;
            const width = Math.max(0, ...summaries.map(summary => (summary.querySelector('span')?.scrollWidth || 0) + 13));
            const height = summaries.reduce((sum, summary) => sum + summary.getBoundingClientRect().height, 0);
            const controlHeight = Math.max(level.getBoundingClientRect().height, send.getBoundingClientRect().height);
            const requiredWidth = level.getBoundingClientRect().width + send.getBoundingClientRect().width + width + gap * 2;
            const layout = height <= controlHeight + .5 && requiredWidth <= actions.clientWidth + .5 ? 'stacked' : 'flow';
            if (root.dataset.disclosureLayout !== layout) root.dataset.disclosureLayout = layout;
            root.classList.add('ai-controls-measured');
            const actionHeight = actions.getBoundingClientRect().height;
            let offset = actionHeight + 8, openCount = 0;
            for (const item of visible) {
                const panel = item.querySelector('.ai-control-panel');
                if (!item.open || !panel) continue;
                assign(panel, '--ai-panel-top', Math.ceil(offset) + 'px');
                offset += Math.ceil(panel.getBoundingClientRect().height) + 8;
                openCount++;
            }
            assign(root, '--ai-disclosure-height', (openCount ? Math.ceil(offset - actionHeight) : 0) + 'px');
        };
        const queue = () => { if (!stopped && frame === null) frame = requestAnimationFrame(measure); };
        const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(queue) : null;
        for (const node of [actions, level, send, ...group.querySelectorAll('summary, .ai-control-panel')]) observer?.observe(node);
        const mutations = new MutationObserver(queue);
        mutations.observe(group, {attributes:true, subtree:true, attributeFilter:['hidden']});
        for (const item of details) item.addEventListener('toggle', queue);
        global.addEventListener('resize', queue);
        global.visualViewport?.addEventListener('resize', queue);
        document.fonts?.addEventListener('loadingdone', queue);
        document.fonts?.ready.then(queue);
        measure();
        return () => {
            stopped = true;
            if (frame !== null) cancelAnimationFrame(frame);
            observer?.disconnect(); mutations.disconnect();
            for (const item of details) item.removeEventListener('toggle', queue);
            global.removeEventListener('resize', queue);
            global.visualViewport?.removeEventListener('resize', queue);
            document.fonts?.removeEventListener('loadingdone', queue);
        };
    }

    /* [MINI-COMMENT: ASSISTANT.POLISH.STATUS] [EN rev.2]
     * [Role] Atomically colors the header/input stars and displays input-adjacent warnings only from fresh server evidence, with active-job connection precedence.
     * [Dependencies] GET /api/ai/status accepts opaque selection_id/job_id and returns state/scope/checked_at/expires_at/message; passive headers preserve session policy.
     * [Impact] One polling/TTL path owns both views: yellow/red explanations remain safe text, repeated identical live text is not rewritten, and checking/stale/errors/context changes immediately remove old warnings without clearing unrelated notices or cancelling work.
     */
    function headerStatus(root) {
        const star = document.getElementById('ai-header-status');
        if (!star) return () => {};
        const banner = root.querySelector('#ai-connection-status');
        const bannerMark = root.querySelector('#ai-connection-status-mark');
        const bannerSummary = root.querySelector('#ai-connection-status-summary');
        const bannerReason = root.querySelector('#ai-connection-status-reason');
        const states = new Set(['ready','waiting_other','unavailable','checking','stale']);
        const descriptions = {
            ready:'AI 연결 정상', waiting_other:'다른 요청의 처리를 기다리고 있습니다.',
            unavailable:'선택한 AI 연결의 응답 불가가 확인되었습니다.',
            checking:'AI 연결 상태 확인 중', stale:'AI 연결 상태의 최근 확인이 필요합니다.'
        };
        let context = null, timer = null, expiryTimer = null, requestTimeout = null, controller = null;
        let sequence = 0, stopped = false;
        const opaque = value => typeof value === 'string' && value.length > 0 && value.length <= 512 && !/[\u0000-\u001f\u007f]/u.test(value) ? value : null;
        const render = (state, message, scope) => {
            const scopeText = scope === 'job' ? '진행 중인 요청' : scope === 'selection' ? '다음 요청 연결' : 'AI 연결';
            const reason = message || descriptions[state];
            const text = `${scopeText} · ${reason}`;
            star.dataset.state = state;
            star.dataset.scope = scope || '';
            star.title = text; star.setAttribute('aria-label', text);
            if (banner && bannerMark && bannerSummary && bannerReason) {
                const visible = state === 'waiting_other' || state === 'unavailable';
                const summary = !visible ? '' : state === 'waiting_other' ? '다른 세션/사용자의 요청 처리 중' : 'AI 서버의 응답을 받지 못하고 있습니다.';
                const detail = visible ? `${scopeText} · 서버 확인: ${reason}` : '';
                banner.dataset.state = bannerMark.dataset.state = state;
                banner.dataset.scope = scope || '';
                for (const name of ['checkedAt','expiresAt']) {
                    if (star.dataset[name]) banner.dataset[name] = star.dataset[name];
                    else delete banner.dataset[name];
                }
                if (bannerSummary.textContent !== summary) bannerSummary.textContent = summary;
                if (bannerReason.textContent !== detail) bannerReason.textContent = detail;
                banner.hidden = !visible;
            }
        };
        const clearPoll = () => { if (timer !== null) clearTimeout(timer); timer = null; };
        const clearExpiry = () => { if (expiryTimer !== null) clearTimeout(expiryTimer); expiryTimer = null; };
        const abort = () => { sequence++; if (requestTimeout !== null) clearTimeout(requestTimeout); requestTimeout = null; controller?.abort(); controller = null; };
        const schedule = delay => {
            clearPoll();
            if (!stopped && context && (context.selectionId || context.jobId)) timer = setTimeout(poll, delay);
        };
        async function poll() {
            clearPoll();
            if (stopped || !root.isConnected || !context || !(context.selectionId || context.jobId)) return;
            abort();
            const current = sequence, request = new AbortController();
            controller = request;
            const timeout = setTimeout(() => request.abort(), 8000);
            requestTimeout = timeout;
            const query = new URLSearchParams();
            if (context.selectionId) query.set('selection_id', context.selectionId);
            if (context.jobId) query.set('job_id', context.jobId);
            try {
                const response = await fetch('/api/ai/status?' + query.toString(), {
                    credentials:'same-origin', cache:'no-store', signal:request.signal,
                    headers:{'Accept':'application/json','X-Assistant-Poll':'1'}
                });
                if (!response.ok) throw new Error('status unavailable');
                const result = await response.json();
                if (stopped || current !== sequence) return;
                const now = Date.now() / 1000;
                if (!result || result.success !== true || !states.has(result.state) || !['job','selection'].includes(result.scope) ||
                    !Number.isFinite(result.checked_at) || !Number.isFinite(result.expires_at) || result.checked_at > now + 5 || result.expires_at < result.checked_at) throw new Error('invalid status');
                clearExpiry();
                const expires = Math.min(result.expires_at, result.checked_at + 60);
                star.dataset.checkedAt = String(result.checked_at); star.dataset.expiresAt = String(expires);
                if (expires <= now) render('stale', descriptions.stale, result.scope);
                else {
                    const message = typeof result.message === 'string' ? result.message.slice(0,500) : descriptions[result.state];
                    render(result.state, message, result.scope);
                    expiryTimer = setTimeout(() => {
                        expiryTimer = null;
                        if (!stopped && star.dataset.expiresAt === String(expires)) render('stale', descriptions.stale, result.scope);
                    }, Math.max(0, expires * 1000 - Date.now()));
                }
            } catch (_) {
                if (!stopped && current === sequence) { clearExpiry(); render('checking', '연결 상태를 확인하지 못했습니다. 잠시 후 다시 확인합니다.'); }
            } finally {
                clearTimeout(timeout);
                if (requestTimeout === timeout) requestTimeout = null;
                if (!stopped && current === sequence) {
                    controller = null;
                    schedule(document.hidden ? 15000 : 2500);
                }
            }
        }
        const change = event => {
            if (stopped) return;
            const detail = event.detail;
            if (!detail || typeof detail !== 'object') return;
            const next = {selectionId:opaque(detail.selectionId), jobId:opaque(detail.jobId)};
            if (context && next.selectionId === context.selectionId && next.jobId === context.jobId) return;
            clearPoll(); clearExpiry(); abort(); context = next;
            delete star.dataset.checkedAt; delete star.dataset.expiresAt;
            render('checking', next.selectionId || next.jobId ? descriptions.checking : '사용할 AI 연결을 선택해 주세요.', next.jobId ? 'job' : 'selection');
            if (next.selectionId || next.jobId) poll();
        };
        const visibility = () => {
            clearPoll();
            if (document.hidden) { abort(); schedule(15000); }
            else poll();
        };
        global.addEventListener('assistant-status-context', change, true);
        document.addEventListener('visibilitychange', visibility);
        render('checking', descriptions.checking);
        return () => {
            stopped = true; clearPoll(); clearExpiry(); abort();
            global.removeEventListener('assistant-status-context', change, true);
            document.removeEventListener('visibilitychange', visibility);
        };
    }

    function init() {
        if (disposed) return;
        const root = document.getElementById('equipment-ai');
        if (root) cleanups.push(disclosures(root), headerStatus(root));
    }
    function destroy() {
        if (disposed) return;
        disposed = true;
        document.removeEventListener('DOMContentLoaded', init);
        global.removeEventListener('pagehide', destroy);
        for (const cleanup of cleanups.splice(0)) cleanup();
    }
    global.EquipmentAiPolish = {destroy};
    global.addEventListener('pagehide', destroy, {once:true});
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
    else init();
})(window);
