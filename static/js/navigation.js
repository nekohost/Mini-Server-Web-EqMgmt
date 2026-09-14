/* In-app history is not the menu hierarchy. Parent links are declared by templates. */
(function (global) {
    'use strict';
    if (global.AppNavigation && global.AppNavigation.destroy) global.AppNavigation.destroy();
    let stopTitle = () => {};
    const authPaths = new Set(['/login', '/logout', '/register', '/reset_password']);
    const normalize = text => String(text).trim().replace(/\s+/gu, ' ');
    const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('ko', {granularity: 'grapheme'}) : null;
    function weightedLength(text) {
        const chars = segmenter ? Array.from(segmenter.segment(normalize(text)), item => item.segment) : Array.from(normalize(text));
        return chars.reduce((sum, char) => sum + (/\s/u.test(char) ? .5 : 1), 0);
    }
    // Minimize line count, then unused-space variance. Break only between whole words.
    function titleLines(text, maxWidth = Infinity, measure = weightedLength, maxUnits = 10) {
        const words = normalize(text).split(' ').filter(Boolean), best = Array(words.length + 1);
        best[words.length] = {lines: [], count: 0, cost: 0};
        for (let start = words.length - 1; start >= 0; start--) {
            for (let end = start + 1; end <= words.length; end++) {
                const line = words.slice(start, end).join(' '), units = weightedLength(line), width = measure(line);
                if (end > start + 1 && (units > maxUnits || width > maxWidth)) break;
                const rest = best[end], spare = Math.max(0, Math.min(maxUnits - units, (maxWidth - width) / Math.max(1, maxWidth) * maxUnits));
                const candidate = {lines: [line, ...rest.lines], count: rest.count + 1, cost: rest.cost + (Number.isFinite(spare) ? spare * spare : (maxUnits - units) ** 2)};
                if (!best[start] || candidate.count < best[start].count || (candidate.count === best[start].count && candidate.cost < best[start].cost)) best[start] = candidate;
            }
        }
        return best[0].lines;
    }
    function initTitle() {
        const title = document.querySelector('.app-nav-title');
        if (!title) return;
        let source = normalize(title.textContent), previous = '';
        const canvas = document.createElement('canvas'), context = canvas.getContext('2d');
        const narrow = matchMedia('(max-width: 599px)');
        function format() {
            if (!title.isConnected) return;
            const current = normalize(title.textContent);
            if (current !== source) source = current;
            const style = getComputedStyle(title), width = Math.max(1, title.clientWidth - 1);
            const key = [source, narrow.matches, width, style.font].join('|');
            if (key === previous) return;
            previous = key;
            title.setAttribute('aria-label', source);
            title.dataset.weightedLength = String(weightedLength(source));
            if (!narrow.matches) { if (title.children.length) title.textContent = source; return; }
            context.font = style.font;
            const lines = titleLines(source, width, value => context.measureText(value).width);
            const fragment = document.createDocumentFragment();
            lines.forEach((line, index) => {
                if (index) fragment.append(document.createTextNode(' '));
                const span = document.createElement('span'); span.className = 'app-nav-title-line'; span.textContent = line;
                fragment.append(span);
            });
            title.replaceChildren(fragment);
        }
        const mutations = new MutationObserver(format);
        mutations.observe(title, {childList: true, characterData: true, subtree: true});
        const size = typeof ResizeObserver === 'function' ? new ResizeObserver(format) : null;
        if (size) size.observe(title);
        narrow.addEventListener('change', format);
        window.addEventListener('resize', format);
        if (document.fonts) document.fonts.ready.then(() => { previous = ''; format(); });
        stopTitle = () => {
            mutations.disconnect(); if (size) size.disconnect();
            narrow.removeEventListener('change', format); window.removeEventListener('resize', format);
        };
        format();
    }
    function canGoBack(current, referrer, length) {
        try {
            const here = new URL(current), previous = new URL(referrer);
            return length > 1 && previous.origin === here.origin && !authPaths.has(previous.pathname.replace(/\/$/, ''));
        } catch { return false; }
    }
    function init() {
        initTitle();
        const back = document.getElementById('smart-back-btn');
        if (back) {
            back.disabled = !canGoBack(location.href, document.referrer, history.length);
            back.title = back.disabled ? '이 창에서 돌아갈 이전 화면이 없습니다.' : '이전 화면으로 돌아가기';
            back.addEventListener('click', () => { if (!back.disabled) history.back(); });
        }
        const parent = document.getElementById('parent-menu-link');
        if (parent) {
            const path = value => new URL(value, location.href).pathname.replace(/\/$/, '');
            if (path(parent.href) === path(location.href)) {
                parent.removeAttribute('href');
                parent.setAttribute('aria-disabled', 'true');
                parent.tabIndex = -1;
                parent.title = '최상위 메뉴입니다.';
            } else {
                parent.title = '상위 메뉴: ' + parent.dataset.parentName;
            }
        }
    }
    global.AppNavigation = {canGoBack, weightedLength, titleLines, destroy: () => stopTitle()};
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
    else init();
})(window);
