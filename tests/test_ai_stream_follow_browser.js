/* [MINI-COMMENT: ASSISTANT.STREAM.FOLLOW.BROWSER.DRIVER]
 * [EN rev.1]
 * [Role] Drives a controllable virtual answer model through live reasoning and answer output while real Chromium wheel/touch gestures move the reader.
 * [Dependencies] Appended after the reviewed stream-polish synthetic transport prefix (server, cid, conversations, sleep); the parent-frame __followAction/__followAck bridge served by stream_follow_browser_fixture.capture_scroll_input.
 * [Impact] Proves follow, upward detach, held position, inner reasoning ownership and reattachment for the pane and the reasoning box; a stage marker freezes the model for a matching screenshot. No account, model or database is used.
 */
    const stage = window.__streamFollowStage || 'complete';
    const model = { phase: 'idle', reasoning: 0, answer: 0, done: false };
    const reasoningLine = index => `추론 ${index + 1}단계: 장비 기록과 사용 권한 범위를 차례로 확인합니다.\n`;
    const answerLine = index => `문단 ${index + 1}: 가상 답변 모델이 출력한 ${index + 1}번째 문단입니다. 사용자가 읽고 있는 위치를 존중해야 합니다.\n\n`;
    const modelText = () => ({ reasoning: Array.from({ length: model.reasoning }, (_, index) => reasoningLine(index)).join(''),
        content: Array.from({ length: model.answer }, (_, index) => answerLine(index)).join('') });
    // The virtual model emits one line per tick only in its active phase, so each stage can be frozen for a screenshot.
    const ticker = setInterval(() => {
        if (model.phase === 'reasoning' && model.reasoning < 160) model.reasoning++;
        if (model.phase === 'answer' && model.answer < 400) model.answer++;
    }, 110);
    // The current client resumes the owner's latest conversation from the list response; the shared prefix predates that field.
    const baseFetch = server.fetch.bind(server);
    server.fetch = async (path, options = {}) => {
        const url = new URL(path, location.origin);
        if (url.pathname !== '/api/ai/conversations' || (options.method || 'GET') !== 'GET') return baseFetch(path, options);
        server.requests.push({ path: url.pathname, search: url.search, method: 'GET', time: performance.now(), data: null });
        const active = url.searchParams.get('view') !== 'trash';
        return server.respond({ success: true, resume_conversation: active ? { ...conversations.get(cid) } : null,
            conversations: active ? [...conversations.values()] : [], next_cursor: null });
    };
    const baseCurrent = server.current.bind(server);
    server.current = job => {
        if (job.scenario !== 'follow') return baseCurrent(job);
        const value = modelText();
        return { ...value, state: model.done ? 'done' : 'running' };
    };

    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], metrics = { gestures: [] }, report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id), pane = $('ai-scroll'), touch = innerWidth <= 760;
        const wait = async (condition, name, limit = 15000) => {
            const deadline = performance.now() + limit;
            while (performance.now() < deadline) { if (condition()) return; await sleep(10); }
            throw new Error(name + ' timed out');
        };
        const assert = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
        const frames = count => new Promise(resolve => { const step = left => left ? requestAnimationFrame(() => step(left - 1)) : resolve(); step(count); });
        const gap = element => element.scrollHeight - element.scrollTop - element.clientHeight;
        const article = () => [...document.querySelectorAll('.ai-message[data-role="assistant"]')].at(-1);
        const shownLines = (element, word) => (element.textContent.match(new RegExp(word + ' \\d+', 'g')) || []).length;
        let serial = 0;
        /** [Role] Requests one trusted Chromium scroll gesture at a point inside the element; positive distance scrolls up. */
        const gesture = async (element, distance, at) => {
            const box = element.getBoundingClientRect(), frame = window.frameElement.getBoundingClientRect(), id = ++serial;
            const x = Math.round(frame.left + box.left + box.width / 2), y = Math.round(frame.top + box.top + box.height * at);
            window.parent.__followAction = { id, kind: touch ? 'touch' : 'wheel', x, y, distance: Math.round(distance) };
            await wait(() => window.parent.__followAck === id, 'native scroll input acknowledgement');
            let last = -1, stable = 0;
            for (let index = 0; index < 40 && stable < 4; index++) { await frames(1); stable = Math.abs(element.scrollTop - last) < .5 ? stable + 1 : 0; last = element.scrollTop; }
            metrics.gestures.push({ target: element.id || element.className, distance: Math.round(distance), source: touch ? 'touch-drag' : 'mouse-wheel', top: Math.round(element.scrollTop), gap: Math.round(gap(element)) });
        };
        /** [Role] Scrolls a reader up with a finger/wheel path that stays inside the visible viewport. */
        const readUp = (element, distance) => gesture(element, touch ? Math.min(distance, element.getBoundingClientRect().height * .55) : distance, touch ? .3 : .5);
        /** [Role] Returns the reader to the newest output using repeated bounded gestures, as a person would.
         * The virtual model pauses during the return (a fixed-speed drag cannot outrun ~700px/s narrow output) and resumes, so following is proven on new output. */
        const returnToEnd = async element => {
            const phase = model.phase; model.phase = 'paused'; await sleep(400);
            for (let index = 0; index < 14 && gap(element) > 8; index++)
                await gesture(element, -(touch ? Math.min(gap(element) + 120, element.getBoundingClientRect().height * .6) : gap(element) + 200), touch ? .85 : .5);
            assert(gap(element) <= 24, 'reader-reaches-latest-output-' + (element.id || 'reasoning'));
            model.phase = phase;
        };
        /** [Role] Lets the virtual model add lines while every frame confirms the reader stays exactly where it was. */
        const holds = async (element, counter, more, name) => {
            const top = element.scrollTop, start = counter(), samples = [];
            await wait(() => { samples.push(element.scrollTop); return counter() >= start + more; }, name + ' output growth');
            await frames(3); samples.push(element.scrollTop);
            metrics.last_hold = { name, top, gap: gap(element), samples: [...new Set(samples.map(Math.round))].slice(0, 20) };
            assert(samples.every(value => Math.abs(value - top) <= 1) && gap(element) > 24, name);
            return { top: Math.round(top), samples: samples.length, gap: Math.round(gap(element)) };
        };
        /** [Role] Confirms new lines arrive while the element remains on the newest output. */
        const follows = async (element, counter, more, name) => {
            const start = counter();
            await wait(() => counter() >= start + more && gap(element) <= 2, name, 8000);
            checks.push(name);
        };
        const freeze = async name => {
            if (stage !== name) return false;
            model.phase = 'paused'; await sleep(700); await frames(3);
            metrics.final_geometry = { pane: { top: Math.round(pane.scrollTop), gap: Math.round(gap(pane)) }, thought: article() && { top: Math.round(article().querySelector('.ai-thought-text').scrollTop), gap: Math.round(gap(article().querySelector('.ai-thought-text'))) } };
            return true;
        };
        const finish = status => {
            clearInterval(ticker);
            report.textContent = JSON.stringify({ status, view: 'stream-follow', stage, width: innerWidth, theme, checks, metrics, production_data_used: false,
                interaction: touch ? 'Chromium CDP Input.dispatchTouchEvent drag (touch emulation)' : 'Chromium CDP Input.dispatchMouseEvent mouseWheel', model: 'virtual answer model over synthetic transport' });
        };
        /** [Role] Runs the scenario up to the requested stage; returning early leaves that stage on screen. */
        const scenario = async () => {
            await wait(() => module.exports.markdown && !$('ai-send').disabled && $('ai-title').textContent === conversations.get(cid).title, 'initial hydration');
            window.frameElement.style.height = (touch ? 900 : 1000) + 'px';
            await sleep(120);
            server.nextScenario = 'follow'; const count = server.jobs.length, prompt = '자동 스크롤 확인 요청';
            $('ai-input').value = prompt; $('ai-input').dispatchEvent(new Event('input')); $('ai-form').requestSubmit();
            await wait(() => server.jobs.length > count && $('equipment-ai').getAttribute('aria-busy') === 'false'
                && [...document.querySelectorAll('.ai-message[data-role="user"] .ai-answer')].some(answer => answer.textContent === prompt), 'turn accepted');
            assert(gap(pane) <= 2, 'sent-turn-opens-at-latest-output');

            model.phase = 'reasoning';
            await wait(() => article()?.querySelector('.ai-thought:not([hidden])')?.open, 'live reasoning opens');
            const thought = article().querySelector('.ai-thought-text'), answer = article().querySelector('.ai-answer');
            const reasoningShown = () => shownLines(thought, '추론');
            await wait(() => thought.scrollHeight > thought.clientHeight + 160, 'reasoning exceeds its box', 20000);
            await follows(thought, reasoningShown, 3, 'reasoning-box-follows-latest-reasoning');
            assert(gap(pane) <= 2, 'conversation-follows-live-reasoning');
            if (await freeze('reasoning-follow')) return;

            await readUp(thought, 140);
            assert(gap(thought) > 24, 'upward-gesture-moves-reasoning-reader');
            metrics.reasoning_hold = await holds(thought, reasoningShown, 4, 'reasoning-box-holds-reader-position-while-reasoning-continues');
            assert(gap(pane) <= 2, 'inner-reasoning-gesture-does-not-detach-conversation');
            if (await freeze('reasoning-detached')) return;

            await returnToEnd(thought);
            await follows(thought, reasoningShown, 3, 'returning-to-reasoning-end-resumes-following');

            model.phase = 'answer';
            const answerShown = () => shownLines(answer, '문단');
            await wait(() => answerShown() > 0 && !article().querySelector('.ai-thought').open, 'answer starts and reasoning collapses');
            await wait(() => pane.scrollHeight > pane.clientHeight * 2 && answer.getBoundingClientRect().height > pane.clientHeight, 'answer exceeds the visible pane', 25000);
            await follows(pane, answerShown, 3, 'conversation-follows-live-answer');

            await readUp(pane, 260);
            assert(gap(pane) > 60, 'upward-gesture-moves-conversation-reader');
            metrics.answer_hold = await holds(pane, answerShown, 5, 'answer-holds-reader-position-while-output-continues');
            if (await freeze('answer-detached')) return;

            await returnToEnd(pane);
            await follows(pane, answerShown, 3, 'returning-to-latest-answer-resumes-following');

            // The previous client snapped back whenever the reader stayed within 100px of the end.
            await readUp(pane, 60);
            metrics.small_hold = await holds(pane, answerShown, 5, 'small-upward-gesture-below-previous-100px-threshold-holds');

            await returnToEnd(pane);
            await follows(pane, answerShown, 3, 'second-return-to-latest-answer-resumes-following');
            if (await freeze('answer-reattached')) return;

            model.phase = 'paused'; model.done = true;
            await wait(() => !$('ai-send').disabled && answer.textContent.includes(`문단 ${model.answer}:`), 'final flush');
            await sleep(300); await frames(3);
            assert(gap(pane) <= 2, 'completed-answer-ends-at-latest-output-while-following');
            assert(thought.textContent === modelText().reasoning, 'reasoning-text-is-exact-after-follow-changes');
            assert(document.documentElement.scrollWidth <= innerWidth + 1, 'no-document-horizontal-overflow');
        };
        try {
            await scenario();
            finish('pass');
        } catch (error) {
            metrics.failure_geometry = { pane: { top: Math.round(pane.scrollTop), gap: Math.round(gap(pane)), height: pane.scrollHeight }, model: { ...model } };
            finish('fail'); const value = JSON.parse(report.textContent); value.error = error.message; report.textContent = JSON.stringify(value);
        }
        if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin);
    });
})();
