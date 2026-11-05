/* [MINI-COMMENT: ASSISTANT.STREAM.POLISH.BROWSER.DRIVER]
 * [EN rev.2]
 * [Role] Drives real integrated chat output through chunk, reconnect, failure, cancellation and conversation transitions.
 * [Dependencies] Candidate main JavaScript/presenter/Markdown, real RAF and synthetic owner-only fetch responses; all instrumentation is confined to this browser fixture.
 * [Impact] Records timed positive prefixes including genuinely large table prefixes and actual renderer cost; persistent fixture-only table width makes scroll retention measurable across Markdown rebuilds, alongside exact snapshots and request teardown.
 */
(function () {
    'use strict';
    const theme = new URLSearchParams(location.search).get('theme') || 'light';
    localStorage.theme = theme; document.documentElement.classList.toggle('dark', theme === 'dark');
    window.module = { exports: {} };
    const cid = 'a'.repeat(32), otherCid = 'd'.repeat(32), modelId = 'e'.repeat(32);
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    const pointLength = value => Array.from(value).length;
    const pointSlice = (value, start, end) => Array.from(value).slice(start, end).join('');
    const source = { provider_name: '격리 출력 연결', model_label: '표시 검사 모델', reasoning_effort: 'medium', revision: 1 };
    const storage = { base_chars: 32000000, extension_chars: 32000000, total_chars: 64000000, used_chars: 1234, reserved_chars: 0, above_base: false };
    const historyText = Array(70).fill('이전 대화의 읽는 위치를 보존합니다. 장비 정보와 업무 기록은 그대로 확인할 수 있습니다.').join('\n\n');
    const reasoningA = '장비🙂와 권한을 확인합니다. 👩🏽‍💻 e\u0301 한 🇰🇷\n'.repeat(80);
    const reasoningB = reasoningA + '\n추가 범위를 검토했고 답변을 정리합니다.\n'.repeat(25);
    const table = '| 장비 | 수량 | 메모 |\n| :--- | ---: | :---: |\n'
        + Array.from({ length: 120 }, (_, index) => `| 시험 장비 ${index + 1}🙂 | ${index + 1} | **확인** e\u0301 👩🏽‍💻 |`).join('\n');
    const finalAnswer = '# 장비 확인🙂\n**확인했습니다.**\n' + table
        + '\n\n```text\n안전한 코드 <script>window.__streamPwned=1</script>\n```\n'
        + '<img src=x onerror="window.__streamPwned=1">\n[내 장비](/my_equipment)\n마지막 문장까지 정확하게 표시했습니다. 🇰🇷';
    const firstAnswer = finalAnswer.slice(0, finalAnswer.indexOf('\n| 시험 장비 18'));

    const runs = [];
    /** [Role] Installs after deferred assets load and before the first user turn, preserving production script ordering. */
    function instrumentPresenter() {
        const originalCreate = window.EquipmentAIStreamPresenter?.create;
        if (!originalCreate) return false;
        window.EquipmentAIStreamPresenter.create = options => {
        const record = { created: performance.now(), renders: [], updates: [], raf: [], frames: new Set(), page: new Set(), motion: new Set(), instance: null };
        runs.push(record);
        const page = options.document === undefined ? document : options.document;
        const motion = options.motionQuery === undefined ? matchMedia('(prefers-reduced-motion: reduce)') : options.motionQuery;
        let activeRaf = null;
        const pageAdapter = page && {
            get hidden() { return page.hidden; },
            addEventListener(type, listener) { record.page.add(listener); page.addEventListener(type, listener); },
            removeEventListener(type, listener) { record.page.delete(listener); page.removeEventListener(type, listener); },
        };
        const motionAdapter = motion && {
            get matches() { return motion.matches; },
            addEventListener(type, listener) { record.motion.add(listener); motion.addEventListener(type, listener); },
            removeEventListener(type, listener) { record.motion.delete(listener); motion.removeEventListener(type, listener); },
        };
        const instance = originalCreate({ ...options, document: pageAdapter, motionQuery: motionAdapter,
            requestFrame(callback) {
                const id = requestAnimationFrame(stamp => {
                    record.frames.delete(id); record.raf.push(stamp); activeRaf = stamp;
                    try { callback(stamp); } finally { activeRaf = null; }
                });
                record.frames.add(id); return id;
            },
            cancelFrame(id) { record.frames.delete(id); cancelAnimationFrame(id); },
            render(frame) {
                const started = performance.now(); options.render(frame);
                const cost = performance.now() - started;
                const article = [...document.querySelectorAll('.ai-message[data-role="assistant"]')].at(-1);
                const region = article?.querySelector('.ai-table-scroll');
                record.renders.push({ time: started, raf: activeRaf, cost,
                    reasoning: frame.reasoning, content: frame.content, streaming: frame.streaming, pending: frame.pending,
                    paneTop: document.getElementById('ai-scroll')?.scrollTop, tableLeft: region?.scrollLeft ?? null,
                    tableClientWidth: region?.clientWidth ?? null, tableScrollWidth: region?.scrollWidth ?? null });
            },
        });
        const update = instance.update;
        instance.update = (snapshot, config) => {
            record.updates.push({ time: performance.now(), reasoning: snapshot.reasoning, content: snapshot.content,
                generation: snapshot.generation, streaming: snapshot.streaming });
            return update(snapshot, config);
        };
            record.instance = instance; return instance;
        };
        return true;
    }

    /** [Role] Holds cumulative authoritative snapshots and implements the server's code-point cursor contract. */
    const conversations = new Map([
        [cid, { id: cid, title: '부드러운 출력 확인 대화', updated: 3, is_deleted: 0, lifecycle_revision: 0, selection_id: modelId, selection_revision: 1, next_level: 'medium' }],
        [otherCid, { id: otherCid, title: '전환 확인 대화', updated: 1, is_deleted: 0, lifecycle_revision: 0, selection_id: modelId, selection_revision: 1, next_level: 'medium' }],
    ]);
    const server = { jobs: [], requests: [], nextScenario: 'normal', failNextJobRead: false, disconnects: 0, jobSerial: 0,
        respond(value, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json', 'X-Assistant-Account': 'synthetic-stream-account' } }); },
        current(job) {
            const age = performance.now() - job.started;
            if (job.cancelled) return { reasoning: job.frozen.reasoning, content: job.frozen.content, state: age - job.cancelledAt < 350 ? 'draining' : 'cancelled' };
            if (job.scenario === 'failure') return { reasoning: age >= 80 ? reasoningA : '', content: age >= 350 ? '중단 전에 받은 답변🙂 '.repeat(50) : '', state: age >= 850 ? 'failed' : 'running' };
            if (job.scenario === 'performance') return { reasoning: age >= 80 ? reasoningB : '',
                content: age >= 2600 ? finalAnswer : age >= 900 ? pointSlice(finalAnswer, 0, pointLength(finalAnswer) - 70) : '',
                state: age >= 2600 ? 'done' : 'running' };
            return { reasoning: age >= 650 ? reasoningB : age >= 80 ? reasoningA : '',
                content: age >= 2300 ? finalAnswer : age >= 1300 ? pointSlice(finalAnswer, 0, pointLength(finalAnswer) - 70) : age >= 650 ? firstAnswer : '',
                state: age >= 2300 ? 'done' : 'running' };
        },
        meta(job) {
            const value = this.current(job);
            return { id: job.id, state: value.state, steps: ['done', 'failed', 'cancelled'].includes(value.state) ? 1 : 0,
                answer_started: Boolean(value.content), source, level: 'medium', error: value.state === 'failed' ? '시험용 응답 오류로 작업을 중단했습니다.' : null };
        },
        async fetch(path, options = {}) {
            const url = new URL(path, location.origin), method = options.method || 'GET';
            const data = typeof options.body === 'string' ? JSON.parse(options.body) : null;
            this.requests.push({ path: url.pathname, search: url.search, method, time: performance.now(), data });
            if (url.pathname.endsWith('/capabilities')) return this.respond({ success: true, storage, reasoning_version: 2, writes: true, file_tools: true, scopes: ['my', 'public'], tools: [] });
            if (url.pathname === '/api/ai/status') return this.respond({ success: true, state: 'ready', scope: url.searchParams.has('job_id') ? 'job' : 'selection', checked_at: Date.now() / 1000, expires_at: Date.now() / 1000 + 60, message: '연결 응답 확인' });
            if (url.pathname === '/api/ai/models') return this.respond({ success: true, models: [{ id: modelId, provider: '격리 출력 연결', label: '표시 검사 모델', available: true, tools: true,
                levels: ['off', 'low', 'medium', 'xhigh'], enabled_levels: ['off', 'low', 'medium', 'xhigh'], supported_levels: ['off', 'low', 'medium', 'xhigh'], default_level: 'medium', level_reasons: { high: '모델 미지원', max: '모델 미지원' } }], default_model: modelId });
            if (url.pathname === '/api/ai/conversations') return this.respond({ success: true, conversations: [...conversations.values()], next_cursor: null });
            const chat = /^\/api\/ai\/conversations\/([a-f0-9]{32})\/(messages|turns|selection)$/.exec(url.pathname);
            if (chat) {
                const item = conversations.get(chat[1]);
                if (chat[2] === 'selection') { item.selection_id = data.selection_id; item.next_level = data.level; item.selection_revision++; return this.respond({ success: true, revision: item.selection_revision }); }
                if (chat[2] === 'turns') {
                    const serial = ++this.jobSerial, job = { id: 'b'.repeat(30) + serial.toString(16).padStart(2, '0'), serial, messageId: serial * 10 + 102,
                        conversation: item.id, prompt: data.content, started: performance.now(), scenario: this.nextScenario };
                    this.jobs.push(job); item.updated++; return this.respond({ success: true, job_id: job.id }, 202);
                }
                const jobs = this.jobs.filter(job => job.conversation === item.id);
                const messages = [{ id: item.id === cid ? 1 : 2, job: null, role: 'assistant', content: historyText, reasoning: '' }];
                for (const job of jobs) {
                    const value = this.current(job);
                    messages.push({ id: job.messageId - 1, job: job.id, role: 'user', content: job.prompt, reasoning: '' },
                        { id: job.messageId, job: job.id, role: 'assistant', content: value.content, reasoning: value.reasoning });
                }
                return this.respond({ success: true, storage, conversation: { ...item }, messages, jobs: jobs.slice().reverse().map(job => this.meta(job)), proposals: [], next_before: null });
            }
            const jobPath = /^\/api\/ai\/jobs\/([a-f0-9]{32})(\/cancel)?$/.exec(url.pathname);
            if (jobPath) {
                const job = this.jobs.find(item => item.id === jobPath[1]);
                if (jobPath[2]) { job.frozen = this.current(job); job.cancelled = true; job.cancelledAt = performance.now() - job.started; return this.respond({ success: true, state: 'draining' }); }
                if (this.failNextJobRead) { this.failNextJobRead = false; this.disconnects++; throw new TypeError('synthetic stream read disconnect'); }
                const value = this.current(job), meta = this.meta(job), generation = 1;
                const ro = Math.min(Number(url.searchParams.get('r') || 0), pointLength(value.reasoning));
                const co = url.searchParams.get('v') === String(generation) ? Math.min(Number(url.searchParams.get('c') || 0), pointLength(value.content)) : 0;
                const reasoning = pointSlice(value.reasoning, ro, ro + 8192), content = pointSlice(value.content, co, co + 8192);
                return this.respond({ success: true, storage, ...meta, generation, message_id: job.messageId, reasoning, content,
                    r: ro + pointLength(reasoning), c: co + pointLength(content), reasoning_length: pointLength(value.reasoning), content_length: pointLength(value.content), proposals: [] });
            }
            return this.respond({ success: false, message: '예상하지 않은 격리 출력 요청입니다.' }, 422);
        },
    };
    window.__streamPolishServer = server;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (path, options = {}) => new URL(path, location.origin).pathname.startsWith('/api/ai/') ? server.fetch(path, options) : nativeFetch(path, options);

    document.addEventListener('DOMContentLoaded', async () => {
        const instrumented = instrumentPresenter();
        const checks = [], metrics = {}, mutations = [], report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id), pane = $('ai-scroll');
        const wait = async (condition, name, limit = 15000) => {
            const deadline = performance.now() + limit;
            while (performance.now() < deadline) { if (condition()) return; await sleep(10); }
            throw new Error(name + ' timed out');
        };
        const assert = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
        const observer = new MutationObserver(records => {
            if (records.some(record => record.target.closest?.('.ai-answer,.ai-thought-text') || record.target.parentElement?.closest('.ai-answer,.ai-thought-text')))
                mutations.push(performance.now());
        });
        observer.observe($('ai-messages'), { subtree: true, childList: true, characterData: true });
        const message = job => [...document.querySelectorAll('.ai-message[data-role="assistant"]')].find(article => article.querySelector('.ai-answer')?.textContent.includes('장비 확인')
            && job.serial === 1) || [...document.querySelectorAll('.ai-message[data-role="assistant"]')].at(-1);
        const resources = run => run.frames.size + run.page.size + run.motion.size;
        const latestRun = () => runs.at(-1);
        const send = async scenario => {
            await wait(() => !$('ai-send').disabled && !$('ai-input').disabled, 'composer ready');
            server.nextScenario = scenario; const count = server.jobs.length;
            const prompt = scenario + ' 표시 검증 요청 ' + (count + 1);
            $('ai-input').value = prompt; $('ai-input').dispatchEvent(new Event('input')); $('ai-form').requestSubmit();
            // POST acceptance precedes open()/hydration; the previous turn's idle flag cannot identify the new request.
            await wait(() => server.jobs.length > count && $('equipment-ai').getAttribute('aria-busy') === 'false'
                && [...document.querySelectorAll('.ai-message[data-role="user"] .ai-answer')].some(answer => answer.textContent === prompt), 'new turn accepted and hydrated');
            return server.jobs.at(-1);
        };
        const selectConversation = async id => {
            if (innerWidth <= 760 && !$('ai-sidebar').classList.contains('is-open')) $('ai-menu-toggle').click();
            document.querySelector(`#ai-conversations .ai-conversation[data-conversation-id="${id}"]`).click();
            await wait(() => $('ai-title').textContent === conversations.get(id).title && $('equipment-ai').getAttribute('aria-busy') === 'false', 'conversation switch');
        };
        try {
            assert(instrumented, 'candidate-loads-independent-presenter-before-first-user-turn');
            await wait(() => module.exports.markdown && !$('ai-send').disabled && $('ai-title').textContent === conversations.get(cid).title, 'initial actual-client hydration');
            if (window.frameElement) window.frameElement.style.height = (innerWidth <= 760 ? 900 : 1000) + 'px';
            await sleep(80);
            const normal = await send('normal');
            await wait(() => message(normal)?.querySelector('.ai-thought:not([hidden])')?.open && latestRun()?.renders.length > 1, 'live reasoning opens and advances');
            const article = message(normal), thought = article.querySelector('.ai-thought'), answer = article.querySelector('.ai-answer'), thoughtText = article.querySelector('.ai-thought-text');
            pane.scrollTop = 35; const readerTop = pane.scrollTop;
            assert(pane.scrollHeight - pane.clientHeight - readerTop > 100, 'test-reader-is-away-from-follow-bottom');
            $('ai-input').value = '스트리밍 동안 보존할 다음 질문🙂'; $('ai-input').dispatchEvent(new Event('input'));
            await wait(() => answer.textContent.includes('장비 확인'), 'first visible answer');
            assert(!thought.open, 'first-visible-answer-auto-collapses-reasoning-once');
            thought.querySelector('summary').click(); assert(thought.open, 'reader-can-manually-reopen-reasoning');
            thoughtText.scrollTop = 45; const thoughtTop = thoughtText.scrollTop;
            const firstText = document.createTreeWalker(answer, NodeFilter.SHOW_TEXT).nextNode();
            const range = document.createRange(); range.setStart(firstText, 0); range.setEnd(firstText, Math.min(4, firstText.textContent.length));
            document.getSelection().removeAllRanges(); document.getSelection().addRange(range);
            const selected = document.getSelection().toString();
            server.failNextJobRead = true;
            await wait(() => server.disconnects === 1 && $('ai-notice').textContent.includes('연결'), 'transient poll disconnect');
            await wait(() => !$('ai-send').disabled && normal && latestRun()?.instance.disposed, 'reconnect final flush', 12000);
            assert(thought.open, 'later-chunks-and-reconnect-keep-manually-reopened-reasoning');
            assert(document.getSelection().toString() === selected && selected.length > 0, 'streaming-safe-markdown-preserves-selected-text');
            assert(Math.abs(pane.scrollTop - readerTop) <= 1, 'incremental-output-preserves-reader-position');
            assert(Math.abs(thoughtText.scrollTop - thoughtTop) <= 1, 'incremental-reasoning-preserves-inner-reader-position');
            assert($('ai-input').value === '스트리밍 동안 보존할 다음 질문🙂', 'streaming-and-reconnect-preserve-next-question-draft');
            document.getSelection().removeAllRanges(); document.dispatchEvent(new Event('selectionchange'));
            await wait(() => answer.querySelectorAll('tbody tr').length === 120 && answer.textContent.includes('마지막 문장'), 'deferred final markdown');
            assert(!answer.querySelector('img,script') && !window.__streamPwned && answer.querySelector('pre').textContent.includes('<script>'), 'safe-markdown-keeps-model-html-inert');
            assert(answer.querySelector('strong')?.textContent === '확인했습니다.' && answer.querySelector('a[href="/my_equipment"]'), 'complete-markdown-keeps-allowed-format-and-local-link');
            assert(thoughtText.textContent === reasoningB, 'reconnect-cumulative-reasoning-matches-exact-source-without-duplicates');
            const normalRuns = runs.filter(run => run.updates.some(update => update.content.includes('# 장비 확인')));
            const finalPaint = normalRuns.flatMap(run => run.renders).at(-1);
            assert(finalPaint.content === finalAnswer && finalPaint.reasoning === reasoningB && finalPaint.streaming === false, 'terminal-flush-matches-exact-raw-answer-and-reasoning');
            const legalEnds = value => new Set([0, ...[...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(value)].map(part => part.index + part.segment.length)]);
            const answerEnds = legalEnds(finalAnswer), reasoningEnds = legalEnds(reasoningB);
            assert(normalRuns.flatMap(run => run.renders).every(frame => finalAnswer.startsWith(frame.content) && reasoningB.startsWith(frame.reasoning)
                && answerEnds.has(frame.content.length) && reasoningEnds.has(frame.reasoning.length)), 'real-dom-output-preserves-emoji-combining-hangul-and-flag-boundaries');
            assert(normalRuns.every(run => run.instance.disposed && resources(run) === 0), 'completed-output-releases-every-frame-and-listener');
            const intermediate = normalRuns.flatMap(run => run.renders).filter(frame => frame.pending > 0 && frame.raf !== null);
            assert(intermediate.length >= 4, 'real-raf-paints-multiple-prefixes-between-network-chunks');
            const costs = normalRuns.flatMap(run => run.renders).map(frame => frame.cost).sort((a, b) => a - b);
            const gaps = intermediate.slice(1).map((frame, index) => frame.time - intermediate[index].time).filter(gap => gap < 700);
            metrics.normal = { response_utf16: finalAnswer.length, reasoning_utf16: reasoningB.length, presenter_instances: normalRuns.length,
                intermediate_raf_renders: intermediate.length, actual_dom_mutations: mutations.length, min_frame_gap_ms: Math.min(...gaps),
                median_frame_gap_ms: gaps.slice().sort((a, b) => a - b)[Math.floor(gaps.length / 2)], max_renderer_ms: costs.at(-1),
                p95_renderer_ms: costs[Math.floor((costs.length - 1) * .95)], reconnects: server.disconnects,
                dom_mutation_samples_ms: mutations.filter(time => time >= normal.started).slice(0, 30).map(time => +(time - normal.started).toFixed(2)),
                samples: intermediate.slice(0, 24).map(frame => ({ ms: +(frame.time - normal.started).toFixed(2), raf: +frame.raf.toFixed(2), reasoning_chars: frame.reasoning.length, answer_chars: frame.content.length, pending: frame.pending, render_ms: +frame.cost.toFixed(2) })) };

            const failed = await send('failure');
            await wait(() => message(failed)?.querySelector('.ai-answer')?.textContent.includes('중단 전에'), 'partial answer before failure');
            await wait(() => $('ai-progress-text').textContent.includes('시험용 응답 오류') && !$('ai-send').disabled, 'failed job final state');
            const failedRun = latestRun();
            assert(failedRun.instance.disposed && resources(failedRun) === 0, 'failed-output-flushes-and-releases-animation');
            assert(failedRun.renders.at(-1).content === server.current(failed).content && document.querySelector('.ai-pulse').hidden, 'failure-preserves-accepted-raw-answer-and-stops-progress');

            const cancelled = await send('normal');
            await wait(() => message(cancelled)?.querySelector('.ai-thought:not([hidden])') && latestRun()?.renders.length, 'cancel test live output');
            $('ai-cancel').click();
            await wait(() => server.current(cancelled).state === 'cancelled' && !$('ai-send').disabled, 'own cancellation drained');
            assert(latestRun().instance.disposed && resources(latestRun()) === 0, 'cancelled-output-releases-animation-and-listeners');
            assert(server.requests.filter(request => request.method === 'POST' && request.path.endsWith('/cancel')).length === 1, 'cancel-only-addresses-the-own-fixture-job');

            const switching = await send('normal');
            await wait(() => latestRun()?.renders.length > 1 && !latestRun().instance.disposed, 'switch test live animation');
            const abandoned = latestRun(), oldNode = message(switching), countBeforeSwitch = abandoned.renders.length;
            $('ai-input').value = '대화 전환 중 보존할 초안'; $('ai-input').dispatchEvent(new Event('input'));
            await selectConversation(otherCid);
            assert(abandoned.instance.disposed && resources(abandoned) === 0 && !document.contains(oldNode), 'conversation-switch-releases-old-request-and-message');
            await sleep(650);
            assert(abandoned.renders.length === countBeforeSwitch, 'abandoned-request-cannot-paint-into-new-conversation');
            assert($('ai-input').value === '대화 전환 중 보존할 초안', 'conversation-switch-preserves-composer-draft');
            await sleep(Math.max(0, switching.started + 2350 - performance.now()));
            await selectConversation(cid);
            assert(message(switching).querySelector('.ai-thought-text').textContent === reasoningB, 'restored-snapshot-hydrates-full-reasoning-without-replay');
            assert(message(switching).querySelector('.ai-answer').textContent.includes('마지막 문장'), 'restored-snapshot-hydrates-complete-final-answer');

            // Exercise the expensive real Markdown path without an active selection deferring its work.
            const forcedTableWidth = document.createElement('style'); forcedTableWidth.textContent = '#equipment-ai .ai-message .ai-table-scroll table { min-width: 1800px; }'; document.body.append(forcedTableWidth);
            const beforePerformanceRuns = runs.length, performanceJob = await send('performance');
            await wait(() => message(performanceJob)?.querySelector('.ai-table-scroll'), 'large-table live render');
            const performanceArticle = message(performanceJob), liveTable = performanceArticle.querySelector('.ai-table-scroll');
            liveTable.querySelector('table').style.minWidth = '1800px';
            void liveTable.offsetWidth;
            pane.scrollTop = 65; liveTable.scrollLeft = 130;
            const performanceTop = pane.scrollTop, performanceLeft = liveTable.scrollLeft;
            const beforeTableWidth = { client_width: liveTable.clientWidth, scroll_width: liveTable.scrollWidth,
                table_min_width: getComputedStyle(liveTable.querySelector('table')).minWidth };
            assert(performanceLeft > 0, 'large-table-performance-scenario-has-real-horizontal-scroll');
            await wait(() => !$('ai-send').disabled && latestRun()?.instance.disposed, 'large-table completion');
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            const performanceRuns = runs.slice(beforePerformanceRuns), paints = performanceRuns.flatMap(run => run.renders);
            const lags = [];
            for (const run of performanceRuns) for (let index = 0; index < run.updates.length; index++) {
                const update = run.updates[index];
                if (index && update.content === run.updates[index - 1].content && update.reasoning === run.updates[index - 1].reasoning) continue;
                const complete = run.renders.find(frame => frame.time >= update.time && frame.content === update.content && frame.reasoning === update.reasoning);
                if (complete) lags.push(complete.time - update.time);
            }
            const performanceCosts = paints.map(frame => frame.cost).sort((a, b) => a - b);
            const positiveFrames = paints.filter(frame => frame.raf !== null && frame.content.length > 0 && frame.pending > 0);
            const largeFrames = paints.filter(frame => frame.raf !== null && frame.content.length > 2000 && frame.pending > 0);
            const finalTable = performanceArticle.querySelector('.ai-table-scroll'), finalTop = pane.scrollTop, finalLeft = finalTable.scrollLeft;
            metrics.large_markdown = { rows: 120, renders: paints.length, real_raf_renders: paints.filter(frame => frame.raf !== null).length,
                intermediate_positive_prefix_frames: positiveFrames.length, intermediate_large_prefix_frames: largeFrames.length,
                before_scroll: { top: performanceTop, left: performanceLeft, ...beforeTableWidth },
                after_scroll: { top: finalTop, left: finalLeft, client_width: finalTable.clientWidth, scroll_width: finalTable.scrollWidth,
                    table_min_width: getComputedStyle(finalTable.querySelector('table')).minWidth },
                max_renderer_ms: performanceCosts.at(-1), p95_renderer_ms: performanceCosts[Math.floor((performanceCosts.length - 1) * .95)],
                max_completed_snapshot_catch_up_ms: lags.length ? Math.max(...lags) : null,
                receipt_samples: performanceRuns.flatMap(run => run.updates).map(update => ({ ms: +(update.time - performanceJob.started).toFixed(2), reasoning_chars: update.reasoning.length, answer_chars: update.content.length, streaming: update.streaming })),
                samples: paints.map(frame => ({ ms: +(frame.time - performanceJob.started).toFixed(2), answer_chars: frame.content.length, pending: frame.pending,
                    render_ms: +frame.cost.toFixed(2), pane_top: frame.paneTop, table_left: frame.tableLeft,
                    table_client_width: frame.tableClientWidth, table_scroll_width: frame.tableScrollWidth })) };
            assert(paints.at(-1).content === finalAnswer && paints.at(-1).reasoning === reasoningB, 'large-backlog-final-text-is-exact');
            assert(positiveFrames.length >= 4 && largeFrames.length >= 2, 'large-markdown-backlog-is-painted-on-multiple-real-frames');
            assert(finalTable.scrollWidth > finalTable.clientWidth && getComputedStyle(finalTable.querySelector('table')).minWidth === '1800px', 'wide-table-remains-measurable-after-every-markdown-rebuild');
            assert(Math.abs(finalTop - performanceTop) <= 1 && Math.abs(finalLeft - performanceLeft) <= 1, 'large-markdown-rebuilds-preserve-main-and-table-reader-position');
            assert(lags.length > 1 && Math.max(...lags) <= 700, 'large-markdown-snapshots-catch-up-without-prolonged-artificial-delay');
            assert(document.documentElement.scrollWidth <= innerWidth + 1, 'streaming-table-fits-mobile-and-desktop-document-width');
            metrics.requests = server.requests.length; metrics.presenter_instances = runs.length;
            metrics.real_raf_callbacks = runs.reduce((sum, run) => sum + run.raf.length, 0);
            metrics.max_renderer_ms = Math.max(...runs.flatMap(run => run.renders).map(frame => frame.cost));
            pane.scrollTop = pane.scrollHeight;
            observer.disconnect(); window.dispatchEvent(new Event('pagehide'));
            assert(runs.every(run => run.instance.disposed && resources(run) === 0), 'pagehide-leaves-no-live-presenter-frame-or-listener');
            report.textContent = JSON.stringify({ status: 'pass', view: 'stream-polish', width: innerWidth, theme, checks, metrics, production_data_used: false,
                timing: 'real requestAnimationFrame and performance.now; synthetic transport; no model generation benchmark' });
        } catch (error) {
            observer.disconnect(); window.dispatchEvent(new Event('pagehide'));
            report.textContent = JSON.stringify({ status: 'fail', view: 'stream-polish', width: innerWidth, theme, error: error.message, checks, metrics,
                diagnostic: { title: $('ai-title')?.textContent, notice: $('ai-notice')?.textContent, progress: $('ai-progress-text')?.textContent,
                    jobs: server.jobs.map(job => ({ id: job.id, scenario: job.scenario, age: performance.now() - job.started, state: server.current(job).state })),
                    runs: runs.map(run => ({ renders: run.renders.length, updates: run.updates.length, disposed: run.instance?.disposed, resources: resources(run),
                        last: run.renders.length ? { reasoning: run.renders.at(-1).reasoning.length, content: run.renders.at(-1).content.length, streaming: run.renders.at(-1).streaming } : null })),
                    requests: server.requests.slice(-8) } });
        }
        if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin);
    });
})();
