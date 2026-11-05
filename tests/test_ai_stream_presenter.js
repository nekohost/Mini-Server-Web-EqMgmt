/* [MINI-COMMENT: ASSISTANT.STREAM.PRESENTER.TEST]
 * [EN rev.2]
 * [Role] Exercises the actual presenter with a deterministic frame clock instead of wall-time sleeps or a model/server.
 * [Dependencies] Node's built-in test/assert modules and the Staging presenter; page/motion targets are synthetic.
 * [Impact] Verifies exact final text, bounded smoothing including late-arrival windows, Unicode/replay/generation recovery, render-cost adaptation and complete request teardown without touching production data.
 */
'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { create } = require('../static/js/ai_stream_presenter.js');

/** [Role] Supplies observable page/media listeners so a completed or abandoned request cannot hide a leak. */
class Events {
    constructor() { this.listeners = new Map(); }
    addEventListener(type, listener) {
        if (!this.listeners.has(type)) this.listeners.set(type, new Set());
        this.listeners.get(type).add(listener);
    }
    removeEventListener(type, listener) { this.listeners.get(type)?.delete(listener); }
    emit(type) { for (const listener of [...(this.listeners.get(type) || [])]) listener({ type }); }
    count() { return [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0); }
}

/** [Role] Runs one generation of requested animation frames at a selected deterministic refresh rate. */
class FrameClock {
    constructor() { this.time = 0; this.serial = 0; this.queued = new Map(); this.maximum = 0; }
    request(callback) {
        const id = ++this.serial; this.queued.set(id, callback);
        this.maximum = Math.max(this.maximum, this.queued.size); return id;
    }
    cancel(id) { this.queued.delete(id); }
    step(ms = 16) {
        this.time += ms;
        const callbacks = [...this.queued.values()]; this.queued.clear();
        for (const callback of callbacks) callback(this.time);
    }
    drain(ms = 16) {
        for (let attempts = 0; this.queued.size && attempts < 1000; attempts++) this.step(ms);
        assert.equal(this.queued.size, 0, 'presentation must terminate without a real timer');
    }
}

/** [Role] Binds the production API to synthetic time, preferences, snapshots and measurable renderer cost. */
function fixture({ initial, hidden = false, reduced = false, segmenter, renderCost = 0, render } = {}) {
    const clock = new FrameClock(), document = new Events(), motion = new Events(), frames = [];
    document.hidden = hidden; motion.matches = reduced;
    const presenter = create({
        initial, document, motionQuery: motion, segmenter,
        now: () => clock.time, requestFrame: callback => clock.request(callback), cancelFrame: id => clock.cancel(id),
        render(frame) {
            frames.push({ ...frame, time: clock.time });
            if (render) render(frame);
            clock.time += renderCost;
        },
    });
    return { presenter, clock, document, motion, frames };
}

/** [Role] Forms full canonical snapshots; transport offsets/deltas deliberately stay outside the display API. */
function snapshot(content, reasoning = '', generation = 1, streaming = true) {
    return { content, reasoning, generation, streaming };
}

/** [Role] Asserts every painted prefix is monotonic within one generation and the latest text is exact. */
function exactPrefixes(frames, expected, name = 'content') {
    let previous = '';
    for (const frame of frames) {
        assert.ok(expected.startsWith(frame[name]), `${name} stays a canonical prefix`);
        assert.ok(frame[name].startsWith(previous), `${name} cannot repeat or move backwards`);
        previous = frame[name];
    }
    assert.equal(previous, expected);
}

test('splits one chunky reasoning/answer snapshot into bounded, independently exact frames', t => {
    const h = fixture();
    const input = Object.freeze(snapshot('장비 🙂 답변입니다. '.repeat(100), '권한과 장비를 검토합니다. '.repeat(80)));
    h.presenter.update(input);
    assert.equal(h.frames.length, 0, 'active input waits for an animation frame');
    h.clock.drain();
    assert.ok(h.frames.length >= 6 && h.frames.length <= 20);
    assert.ok(h.frames[0].content.length < input.content.length);
    assert.ok(h.frames.at(-1).time <= 496, 'fixed catch-up deadline is below half a second plus one frame');
    assert.equal(h.clock.maximum, 1);
    exactPrefixes(h.frames, input.content); exactPrefixes(h.frames, input.reasoning, 'reasoning');
    h.presenter.dispose();
    assert.equal(h.document.count() + h.motion.count(), 0);
    t.diagnostic(JSON.stringify({ scenario: 'chunk', renders: h.frames.length, first_ms: h.frames[0].time,
        catch_up_ms: h.frames.at(-1).time, max_queued_frames: h.clock.maximum }));
});

test('uses elapsed time at different display refresh rates', () => {
    for (const step of [8, 16, 40, 100]) {
        const h = fixture(), input = snapshot('x'.repeat(2000));
        h.presenter.update(input); h.clock.drain(step);
        assert.equal(h.frames.at(-1).content, input.content);
        assert.ok(h.frames.at(-1).time <= 480 + step);
        assert.ok(h.frames.length <= 20, 'high refresh does not trigger unnecessary full renders');
        h.presenter.dispose();
    }
});

test('handles maximum policy-sized text without segmenting on animation frames', t => {
    let calls = 0, segmented = 0;
    const native = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
    const segmenter = { segment(text) { calls++; segmented += text.length; return native.segment(text); } };
    const h = fixture({ segmenter }), input = snapshot('a'.repeat(64000), 'r'.repeat(100000));
    h.presenter.update(input);
    const ingestCalls = calls, ingestSize = segmented;
    h.clock.drain();
    assert.equal(calls, ingestCalls); assert.equal(segmented, ingestSize);
    assert.equal(h.frames.at(-1).content, input.content); assert.equal(h.frames.at(-1).reasoning, input.reasoning);
    assert.ok(h.frames.length <= 20); assert.ok(h.frames.at(-1).time <= 496); assert.equal(h.clock.maximum, 1);
    h.presenter.dispose();
    t.diagnostic(JSON.stringify({ scenario: '100k-reasoning-64k-answer', renders: h.frames.length,
        catch_up_ms: h.frames.at(-1).time, segmentation_passes: calls, segmented_utf16: segmented }));
});

test('segments only appended suffixes, with one previous cluster replayed at each boundary', () => {
    let segmented = 0;
    const native = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
    const h = fixture({ segmenter: { segment(text) { segmented += text.length; return native.segment(text); } } });
    let content = 'a'.repeat(10000);
    h.presenter.update(snapshot(content)); h.presenter.flush();
    const firstSize = segmented;
    for (let index = 0; index < 100; index++) {
        content += '🙂'; h.presenter.update(snapshot(content)); h.clock.step(16);
    }
    h.clock.drain();
    assert.ok(segmented - firstSize <= 400, 'does not re-segment a growing 10k response for every received chunk');
    assert.equal(h.frames.at(-1).content, content); h.presenter.dispose();
});

test('preserves full emoji/mark/Hangul/flag clusters with native and dependency-free segmentation', () => {
    const content = 'A👩🏽‍💻e\u0301한🇰🇷👨‍👩‍👧‍👦Z'.repeat(40);
    const legalEnds = new Set([0, ...[...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(content)]
        .map(part => part.index + part.segment.length)]);
    for (const segmenter of [undefined, null]) {
        const h = fixture({ segmenter }); h.presenter.update(snapshot(content)); h.clock.drain();
        for (const frame of h.frames) {
            assert.ok(legalEnds.has(frame.content.length), 'painted prefixes end at a full grapheme');
            assert.doesNotMatch(frame.content, /[\uD800-\uDBFF]$/u, 'never cuts a surrogate pair');
        }
        exactPrefixes(h.frames, content); h.presenter.dispose();
    }
});

test('completes a cluster that arrives as a later combining/ZWJ suffix', () => {
    for (const segmenter of [undefined, null]) {
        const h = fixture({ segmenter, initial: snapshot('A👩') });
        const text = 'A👩🏽‍💻e\u0301한🇰🇷' + 'z'.repeat(80);
        h.presenter.update(snapshot(text)); h.clock.drain();
        assert.ok(h.frames[0].content.startsWith('A👩🏽‍💻'));
        assert.equal(h.frames.at(-1).content, text); h.presenter.dispose();
    }
});

test('duplicate/reconnected snapshots neither duplicate text nor postpone the original catch-up deadline', () => {
    const initial = snapshot('저장된 답변🙂', '저장된 추론', 3), h = fixture({ initial });
    assert.equal(h.frames.length, 0, 'hydration is seeded without re-rendering');
    h.presenter.update(initial); assert.equal(h.frames.length, 0); assert.equal(h.clock.queued.size, 0);
    const input = snapshot(initial.content + ' 새 답변 '.repeat(100), initial.reasoning + ' 추가 추론', 3);
    h.presenter.update(input); h.clock.step(100);
    for (let replay = 0; replay < 6; replay++) { h.presenter.update(input); h.clock.step(32); }
    h.clock.drain();
    assert.ok(h.frames.at(-1).time <= 496);
    assert.equal(h.frames.at(-1).content, input.content); assert.equal(h.frames.at(-1).reasoning, input.reasoning);
    const count = h.frames.length;
    h.presenter.update(input); h.presenter.flush();
    assert.equal(h.frames.length, count); assert.equal(h.clock.queued.size, 0); h.presenter.dispose();
});

test('a large late append gets its own window without extending old text or re-segmenting duplicate snapshots', () => {
    let segmented = 0;
    const native = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
    const h = fixture({ segmenter: { segment(text) { segmented += text.length; return native.segment(text); } } });
    const oldText = 'a'.repeat(5000), newText = oldText + 'b'.repeat(5000);
    h.presenter.update(snapshot(oldText));
    for (let count = 0; count < 25; count++) h.clock.step(16);
    assert.ok(h.frames.at(-1).content.length < oldText.length, 'the previous batch still has accepted text queued');
    h.clock.time = 416;
    const before = h.frames.length, beforeSegmented = segmented;
    h.presenter.update(snapshot(oldText));
    assert.equal(h.frames.length, before, 'a duplicate near the deadline does not flush or restart pacing');
    assert.equal(segmented, beforeSegmented);
    h.presenter.update(snapshot(newText));
    assert.equal(h.frames.length, before + 1, 'only the older accepted snapshot flushes synchronously');
    assert.equal(h.frames.at(-1).content, oldText); assert.equal(h.frames.at(-1).time, 416);
    assert.equal(segmented - beforeSegmented, 5001, 'segments only the new suffix and the previous final cluster');
    h.clock.drain();
    const newFrames = h.frames.slice(before + 1);
    assert.ok(newFrames.length >= 6, 'the fresh 5000-character suffix cannot appear in one deadline frame');
    assert.ok(newFrames[0].content.length > oldText.length && newFrames[0].content.length < newText.length);
    assert.equal(newFrames.at(-1).content, newText); assert.ok(newFrames.at(-1).time <= 416 + 496);
    assert.equal(segmented, 10001, 'animation frames never segment either snapshot again');
    h.presenter.dispose();

    const terminal = fixture(); terminal.presenter.update(snapshot(oldText));
    for (let count = 0; count < 25; count++) terminal.clock.step(16);
    terminal.clock.time = 416; const terminalBefore = terminal.frames.length;
    terminal.presenter.update(snapshot(newText, '', 1, false));
    assert.equal(terminal.frames.length, terminalBefore + 1, 'completion bypasses the late-append split');
    assert.equal(terminal.frames.at(-1).content, newText); assert.equal(terminal.frames.at(-1).time, 416);
    assert.equal(terminal.clock.queued.size + terminal.document.count() + terminal.motion.count(), 0);
});

test('same-generation authoritative replacements flush exactly once and cancel stale work', () => {
    const h = fixture(); h.presenter.update(snapshot('오래된 임시 내용 '.repeat(100))); h.clock.step(32);
    h.presenter.update(snapshot('서버에서 복구한 원문', '복구된 추론'));
    assert.equal(h.frames.at(-1).content, '서버에서 복구한 원문');
    assert.equal(h.frames.at(-1).reasoning, '복구된 추론'); assert.equal(h.clock.queued.size, 0);
    const count = h.frames.length; h.clock.step(1000); assert.equal(h.frames.length, count); h.presenter.dispose();
});

test('new generation replaces the provisional answer while preserving cumulative reasoning', () => {
    const h = fixture({ initial: snapshot('이전 단계의 초안', '첫 단계의 추론', 1) });
    const input = snapshot('새 최종 답변 '.repeat(30), '첫 단계의 추론\n\n두 번째 단계의 추론', 2);
    h.presenter.update(input); h.clock.drain();
    assert.ok(h.frames.every(frame => input.content.startsWith(frame.content) && !frame.content.includes('이전')));
    assert.ok(h.frames.every(frame => frame.reasoning.startsWith('첫 단계의 추론') && frame.generation === 2));
    assert.equal(h.frames.at(-1).content, input.content); assert.equal(h.frames.at(-1).reasoning, input.reasoning);
    h.presenter.dispose();
});

test('completion synchronously flushes the exact final text and releases frames/listeners', () => {
    const h = fixture(), input = snapshot('최종 🙂 답변 '.repeat(200), '최종 추론 '.repeat(200));
    h.presenter.update(input); h.clock.step(32);
    const abandonedCallback = [...h.clock.queued.values()][0];
    h.presenter.update({ ...input, streaming: false });
    assert.equal(h.frames.at(-1).content, input.content); assert.equal(h.frames.at(-1).reasoning, input.reasoning);
    assert.equal(h.frames.at(-1).streaming, false); assert.equal(h.presenter.disposed, true);
    assert.equal(h.clock.queued.size + h.document.count() + h.motion.count(), 0);
    const count = h.frames.length; abandonedCallback?.(); h.clock.step(1000);
    assert.equal(h.frames.length, count); assert.equal(h.presenter.update(snapshot('late')), false);
});

test('failure/cancellation can flush accepted text, while conversation disposal discards detached UI', () => {
    for (const finalFlush of [false, true]) {
        const h = fixture(), input = snapshot('보존할 원문 '.repeat(100));
        h.presenter.update(input); h.clock.step(32);
        const count = h.frames.length, oldCallback = [...h.clock.queued.values()][0];
        h.presenter.dispose({ flush: finalFlush }); h.presenter.dispose(); h.presenter.flush(); oldCallback?.();
        assert.equal(h.presenter.disposed, true); assert.equal(h.clock.queued.size + h.document.count() + h.motion.count(), 0);
        if (finalFlush) assert.equal(h.frames.at(-1).content, input.content);
        else assert.equal(h.frames.length, count);
    }
});

test('hidden/visible transitions flush immediately and never replay a background backlog', () => {
    const h = fixture(); h.presenter.update(snapshot('백그라운드 전 '.repeat(100))); h.clock.step(32);
    h.document.hidden = true; h.document.emit('visibilitychange');
    assert.equal(h.frames.at(-1).content, '백그라운드 전 '.repeat(100)); assert.equal(h.clock.queued.size, 0);
    h.presenter.update(snapshot('백그라운드 전 '.repeat(100) + ' 숨은 탭에서 수신'));
    assert.ok(h.frames.at(-1).content.endsWith('숨은 탭에서 수신')); assert.equal(h.clock.queued.size, 0);
    const count = h.frames.length; h.document.hidden = false; h.document.emit('visibilitychange'); h.clock.step(5000);
    assert.equal(h.frames.length, count); h.presenter.dispose();
});

test('reduced motion is immediate initially and when enabled during a running batch', () => {
    const h = fixture({ reduced: true }), input = snapshot('모션 감소 '.repeat(100));
    h.presenter.update(input); assert.equal(h.frames.at(-1).content, input.content); assert.equal(h.clock.queued.size, 0);
    h.motion.matches = false; h.motion.emit('change');
    h.presenter.update(snapshot(input.content + ' 추가 '.repeat(100))); h.clock.step(32);
    assert.ok(h.clock.queued.size);
    h.motion.matches = true; h.motion.emit('change');
    assert.equal(h.frames.at(-1).content, input.content + ' 추가 '.repeat(100)); assert.equal(h.clock.queued.size, 0);
    h.presenter.dispose(); assert.equal(h.document.count() + h.motion.count(), 0);
});

test('removes legacy media-query listeners symmetrically', () => {
    const listeners = new Set(), clock = new FrameClock();
    const motionQuery = { matches: false, addListener: listener => listeners.add(listener), removeListener: listener => listeners.delete(listener) };
    const presenter = create({ render() {}, document: null, motionQuery, now: () => clock.time,
        requestFrame: callback => clock.request(callback), cancelFrame: id => clock.cancel(id) });
    assert.equal(listeners.size, 1); presenter.dispose(); assert.equal(listeners.size, 0);
});

test('adapts callback frequency to expensive Markdown without leaving a long tail', t => {
    const h = fixture({ renderCost: 22 }), input = snapshot('표와 코드 '.repeat(2000));
    h.presenter.update(input); h.clock.drain();
    assert.equal(h.frames.at(-1).content, input.content);
    assert.ok(h.frames.length <= 9, 'expensive full renders are automatically spaced further apart');
    assert.ok(h.frames.at(-1).time <= 496 + 22, 'renderer cost does not reset the catch-up deadline');
    h.presenter.dispose();
    t.diagnostic(JSON.stringify({ scenario: '22ms-renderer', renders: h.frames.length,
        final_start_ms: h.frames.at(-1).time, final_end_ms: h.clock.time }));
});

test('a renderer exception cannot leave a live frame or preference/page listener', () => {
    const h = fixture({ render() { throw new Error('synthetic renderer failure'); } });
    h.presenter.update(snapshot('원문 '.repeat(100)));
    assert.throws(() => h.clock.step(32), /synthetic renderer failure/);
    assert.equal(h.presenter.disposed, true); assert.equal(h.clock.queued.size + h.document.count() + h.motion.count(), 0);
});

test('final hydration and malformed snapshots do not create leaked requests', () => {
    const final = fixture({ initial: snapshot('저장된 최종 답변', '저장된 추론', 2, false) });
    assert.equal(final.presenter.disposed, true); assert.equal(final.frames.length, 0);
    assert.equal(final.clock.queued.size + final.document.count() + final.motion.count(), 0);
    const h = fixture(); assert.throws(() => h.presenter.update(null), TypeError);
    h.presenter.update({ content: {}, reasoning: 5, generation: 0, streaming: false });
    assert.equal(h.frames.at(-1).content, ''); assert.equal(h.frames.at(-1).reasoning, '');
    assert.equal(h.clock.queued.size + h.document.count() + h.motion.count(), 0);
    assert.throws(() => create(), /render callback/);
});
