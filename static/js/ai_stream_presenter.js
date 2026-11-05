/* [MINI-COMMENT: ASSISTANT.STREAM.PRESENTER]
 * [EN rev.2]
 * [Role] Presents already accepted cumulative text snapshots in short, time-based batches.
 * [Dependencies] One requestAnimationFrame, optional native grapheme segmentation and page/motion events; the caller owns transport cursors, safe Markdown and DOM/reader state.
 * [Impact] Presentation never edits stored responses or replays deltas. A 480ms catch-up ceiling, separate late-append windows, synchronous final flush and explicit disposal bound delay and release every scheduled callback/listener.
 */
(function (scope) {
    'use strict';

    const mark = /\p{Mark}/u;

    /** [Role] Classifies conjoining Korean letters for the dependency-free segmentation fallback. */
    function hangul(code) {
        if (code >= 0x1100 && code <= 0x115f || code >= 0xa960 && code <= 0xa97c) return 'L';
        if (code >= 0x1160 && code <= 0x11a7 || code >= 0xd7b0 && code <= 0xd7c6) return 'V';
        if (code >= 0x11a8 && code <= 0x11ff || code >= 0xd7cb && code <= 0xd7fb) return 'T';
        if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 ? 'LVT' : 'LV';
        return '';
    }

    /** [Role] Keeps surrogate pairs, marks, emoji joins/flags and Hangul intact when Intl.Segmenter is unavailable. */
    function fallbackEnds(text) {
        const ends = [];
        let end = 0, previous = 0, regionalRun = 0;
        for (const point of text) {
            const code = point.codePointAt(0), regional = code >= 0x1f1e6 && code <= 0x1f1ff;
            const left = hangul(previous), right = hangul(code);
            const joinedHangul = left === 'L' && ['L', 'V', 'LV', 'LVT'].includes(right)
                || ['LV', 'V'].includes(left) && ['V', 'T'].includes(right)
                || ['LVT', 'T'].includes(left) && right === 'T';
            const extension = mark.test(point) || code >= 0xfe00 && code <= 0xfe0f
                || code >= 0xe0100 && code <= 0xe01ef || code >= 0x1f3fb && code <= 0x1f3ff;
            const joins = ends.length && (extension || code === 0x200d || previous === 0x200d
                || previous === 0x0d && code === 0x0a || regional && regionalRun % 2 === 1 || joinedHangul);
            end += point.length;
            if (joins) ends[ends.length - 1] = end;
            else ends.push(end);
            regionalRun = regional ? regionalRun + 1 : 0;
            previous = code;
        }
        return ends;
    }

    /** [Role] Produces UTF-16 slicing boundaries once per received suffix, never once per animation frame. */
    function boundaries(text, segmenter) {
        if (!segmenter) return fallbackEnds(text);
        const ends = [];
        for (const part of segmenter.segment(text)) ends.push(part.index + part.segment.length);
        return ends;
    }

    /** [Role] Finds the first complete grapheme covering an already visible UTF-16 offset. */
    function coveringIndex(ends, offset) {
        if (!offset) return 0;
        let low = 0, high = ends.length;
        while (low < high) {
            const middle = (low + high) >>> 1;
            if (ends[middle] < offset) low = middle + 1;
            else high = middle;
        }
        return Math.min(ends.length, low + 1);
    }

    /** [Role] Appends only newly segmented suffixes; replaying the final cluster also handles a later combining mark/ZWJ. */
    function accept(field, text, segmenter, reset = false) {
        if (!reset && text === field.text) return false;
        const append = !reset && text.startsWith(field.text);
        const offset = append && field.visible ? field.ends[field.visible - 1] : 0;
        const stable = append ? Math.max(0, field.ends.length - 1) : 0;
        const start = stable ? field.ends[stable - 1] : 0;
        const ends = append ? field.ends.slice(0, stable) : [];
        for (const end of boundaries(text.slice(start), segmenter)) ends.push(start + end);
        field.text = text; field.ends = ends; field.visible = coveringIndex(ends, offset);
        return true;
    }

    /** [MINI-COMMENT: ASSISTANT.STREAM.PRESENTER.CREATE]
     * [EN rev.2]
     * [Role] Creates one disposable presenter for one live request; initial seeds text already hydrated in the DOM without rendering it again.
     * [Dependencies] Full post-merge snapshots {reasoning, content, generation, streaming}, a render callback and optional deterministic clock/frame/page/motion adapters.
     * [Impact] Repeated/recovered snapshots cannot append twice. A late append flushes only older accepted text before its own bounded window; terminal/reconciliation/reduced motion/hidden pages flush immediately, and disposal releases request resources.
     */
    function create(options = {}) {
        if (typeof options.render !== 'function') throw new TypeError('A stream render callback is required.');
        const render = options.render;
        const now = options.now || (() => scope.performance ? scope.performance.now() : Date.now());
        const requestFrame = options.requestFrame || (callback => scope.requestAnimationFrame(callback));
        const cancelFrame = options.cancelFrame || (id => scope.cancelAnimationFrame(id));
        const doc = options.document === undefined ? scope.document : options.document;
        const motion = options.motionQuery === undefined ? scope.matchMedia?.('(prefers-reduced-motion: reduce)') : options.motionQuery;
        const segmenter = options.segmenter === undefined
            ? typeof Intl !== 'undefined' && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: 'grapheme' }) : null
            : options.segmenter;
        const maxCatchUp = Number.isFinite(options.maxCatchUpMs) ? Math.max(32, Math.min(500, options.maxCatchUpMs)) : 480;
        const interval = Number.isFinite(options.frameIntervalMs) ? Math.max(16, Math.min(100, options.frameIntervalMs)) : 32;
        const baseRate = 80 / 1000;
        const fields = { reasoning: { text: '', ends: [], visible: 0 }, content: { text: '', ends: [], visible: 0 } };
        let latest = { reasoning: '', content: '', generation: null, streaming: true };
        let emitted = { ...latest }, frame = null, deadline = null, lastTick = now(), renderCost = 0, disposed = false;

        /** [Role] Counts queued graphemes without scanning or segmenting the response again. */
        function pending() {
            return fields.reasoning.ends.length - fields.reasoning.visible + fields.content.ends.length - fields.content.visible;
        }

        /** [Role] Cancels the sole queued animation callback and releases its catch-up deadline. */
        function unschedule() {
            if (frame !== null) cancelFrame(frame);
            frame = null; deadline = null;
        }

        /** [Role] Emits changed complete-cluster prefixes and measures rendering cost to avoid excessive Markdown rebuilds. */
        function emit() {
            const value = { generation: latest.generation, streaming: latest.streaming };
            for (const name of ['reasoning', 'content']) {
                const field = fields[name];
                value[name] = field.text.slice(0, field.visible ? field.ends[field.visible - 1] : 0);
            }
            if (value.reasoning === emitted.reasoning && value.content === emitted.content
                && value.generation === emitted.generation && value.streaming === emitted.streaming) return;
            const changed = { reasoning: value.reasoning !== emitted.reasoning, content: value.content !== emitted.content };
            emitted = value;
            const started = now();
            try { render({ ...value, changed, pending: pending() }); }
            catch (error) { dispose(); throw error; }
            finally { renderCost = Math.max(0, Math.min(200, now() - started)); }
        }

        /** [Role] Displays all currently accepted text synchronously, retaining no animation backlog. */
        function flush() {
            if (disposed) return;
            unschedule();
            for (const field of Object.values(fields)) field.visible = field.ends.length;
            emit(); lastTick = now();
        }

        /** [Role] Queues at most one frame only while there is live visible-page work. */
        function schedule() {
            if (!disposed && frame === null && pending()) frame = requestFrame(tick);
        }

        /** [Role] Shares a time-based release budget between reasoning and answer and catches up within the fixed batch deadline. */
        function tick() {
            frame = null;
            if (disposed) return;
            if (doc?.hidden || motion?.matches) { flush(); return; }
            const time = now(), elapsed = Math.max(0, time - lastTick);
            // Slow full-Markdown renders reduce callback frequency; their larger elapsed budget still meets the same deadline.
            const effectiveInterval = Math.min(100, Math.max(interval, renderCost * 3));
            if (elapsed < effectiveInterval && time < deadline) { schedule(); return; }
            const total = pending();
            if (!total) { deadline = null; return; }
            const budget = time >= deadline ? total : Math.min(total, Math.max(1,
                Math.floor(elapsed * Math.max(baseRate, total / Math.max(effectiveInterval, deadline - time)))));
            const remainingReason = fields.reasoning.ends.length - fields.reasoning.visible;
            const remainingAnswer = fields.content.ends.length - fields.content.visible;
            let reasonBudget = Math.min(remainingReason, Math.ceil(budget * remainingReason / total));
            if (remainingAnswer && budget > 1 && reasonBudget === budget) reasonBudget--;
            fields.reasoning.visible += reasonBudget;
            fields.content.visible += Math.min(remainingAnswer, budget - reasonBudget);
            lastTick = time; emit();
            if (pending()) schedule();
            else deadline = null;
        }

        /** [Role] Accepts full canonical text without owning/advancing transport cursors or accumulating replayed deltas. */
        function update(snapshot, { immediate = false } = {}) {
            if (disposed) return false;
            if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) throw new TypeError('A stream snapshot is required.');
            const receivedAt = now();
            const next = {
                reasoning: typeof snapshot.reasoning === 'string' ? snapshot.reasoning : '',
                content: typeof snapshot.content === 'string' ? snapshot.content : '',
                generation: snapshot.generation ?? null, streaming: snapshot.streaming !== false,
            };
            const generationChanged = latest.generation !== null && latest.generation !== next.generation;
            const replacement = !next.reasoning.startsWith(latest.reasoning)
                || !generationChanged && !next.content.startsWith(latest.content);
            const appended = next.reasoning !== latest.reasoning || next.content !== latest.content;
            // Keep the older text's latency bound without forcing a newly arrived large suffix through its nearly expired window.
            if (appended && next.streaming && !immediate && !replacement && !generationChanged && !doc?.hidden && !motion?.matches
                && pending() && deadline !== null && deadline - receivedAt <= Math.min(96, maxCatchUp)) {
                flush();
                if (disposed) return false;
            }
            accept(fields.reasoning, next.reasoning, segmenter);
            accept(fields.content, next.content, segmenter, generationChanged);
            latest = next;
            if (immediate || replacement || !next.streaming || doc?.hidden || motion?.matches) flush();
            else if (pending()) {
                if (deadline === null) { lastTick = now(); deadline = receivedAt + Math.min(maxCatchUp, Math.max(96, pending() / baseRate)); }
                if (deadline <= now()) flush();
                else schedule();
            } else emit();
            if (!next.streaming) dispose();
            return true;
        }

        /** [Role] Prevents background/return animations and immediately honors a newly enabled reduced-motion preference. */
        function pageChanged() {
            if (!disposed) flush();
        }

        /** [Role] Flushes on reduced motion only; disabling the preference does not restart an already displayed response. */
        function motionChanged() {
            if (motion?.matches) flush();
        }

        /** [Role] Releases this request's frame/listeners/text; conversation switches discard queued UI while failures/cancellation may flush first. */
        function dispose({ flush: finalFlush = false } = {}) {
            if (disposed) return;
            if (finalFlush) flush();
            disposed = true; unschedule();
            doc?.removeEventListener?.('visibilitychange', pageChanged);
            if (motion?.removeEventListener) motion.removeEventListener('change', motionChanged);
            else motion?.removeListener?.(motionChanged);
            for (const field of Object.values(fields)) { field.text = ''; field.ends = []; field.visible = 0; }
            latest = emitted = null;
        }

        if (options.initial) {
            latest = { reasoning: typeof options.initial.reasoning === 'string' ? options.initial.reasoning : '',
                content: typeof options.initial.content === 'string' ? options.initial.content : '',
                generation: options.initial.generation ?? null, streaming: options.initial.streaming !== false };
            for (const name of ['reasoning', 'content']) {
                accept(fields[name], latest[name], segmenter); fields[name].visible = fields[name].ends.length;
            }
            emitted = { ...latest };
        }
        doc?.addEventListener?.('visibilitychange', pageChanged);
        if (motion?.addEventListener) motion.addEventListener('change', motionChanged);
        else motion?.addListener?.(motionChanged);
        if (!latest.streaming) dispose();
        return { update, flush, dispose, get disposed() { return disposed; } };
    }

    const api = { create };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    if (scope.document) scope.EquipmentAIStreamPresenter = api;
})(typeof globalThis === 'undefined' ? this : globalThis);
