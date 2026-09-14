// Browser-side geometry only. Return labels/metrics, never row data or input values.
export function readabilitySnapshot() {
    const visible = el => el.getBoundingClientRect().width > 0 && getComputedStyle(el).visibility !== 'hidden';
    const textNodes = el => {
        const result = [], walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) if (walker.currentNode.textContent.trim() && visible(walker.currentNode.parentElement)) result.push(walker.currentNode);
        return result;
    };
    const headers = [...document.querySelectorAll('th')].filter(visible).map(el => {
        const style = getComputedStyle(el), range = document.createRange();
        const rects = textNodes(el).flatMap(node => { range.selectNodeContents(node); return [...range.getClientRects()].filter(r => r.width > 0); });
        return {label: el.textContent.trim(), whiteSpace: style.whiteSpace,
            textHeight: rects.length ? Math.max(...rects.map(r => r.bottom)) - Math.min(...rects.map(r => r.top)) : 0,
            lineHeight: parseFloat(style.lineHeight), clipped: el.scrollWidth > el.clientWidth + 1};
    });
    const buttons = [...document.querySelectorAll('button, [role="button"], .roadmap-actions > a, .app-page-heading a, a.inline-block')].filter(visible).map(el => {
        const brokenWords = [];
        for (const node of textNodes(el)) {
            for (const match of node.textContent.matchAll(/[\p{L}\p{N}]+/gu)) {
                const range = document.createRange();
                range.setStart(node, match.index); range.setEnd(node, match.index + match[0].length);
                const rects = [...range.getClientRects()].filter(r => r.width > 0);
                if (rects.some(r => Math.abs(r.y - rects[0].y) > 2)) brokenWords.push(match[0]);
            }
        }
        return {label: el.textContent.trim(), brokenWords, clipped: el.scrollWidth > el.clientWidth + 1,
            wordBreak: getComputedStyle(el).wordBreak, textWrap: getComputedStyle(el).textWrap};
    });
    const scrollers = [...document.querySelectorAll('.overflow-x-auto, .roadmap-scroll')].filter(visible)
        .filter(el => el.querySelector('table')).map(el => {
            const start = el.scrollLeft;
            el.scrollLeft = el.scrollWidth;
            const moved = el.scrollLeft;
            el.scrollLeft = start;
            return {width: el.clientWidth, scrollWidth: el.scrollWidth, canReachEnd: el.scrollWidth - el.clientWidth - moved <= 1};
        });
    return {headers, buttons, scrollers, overflow: document.documentElement.scrollWidth - innerWidth};
}

export function assertReadability(assert, result, label) {
    assert.ok(result.overflow <= 1, label + ': page overflow');
    for (const h of result.headers) {
        assert.equal(h.whiteSpace, 'nowrap', label + ': header ' + h.label);
        assert.ok(h.textHeight <= h.lineHeight + 2, label + ': multiline header ' + h.label);
        assert.equal(h.clipped, false, label + ': clipped header ' + h.label);
    }
    for (const b of result.buttons) {
        assert.deepEqual(b.brokenWords, [], label + ': split button word ' + b.label);
        assert.equal(b.clipped, false, label + ': clipped button ' + b.label);
    }
    for (const s of result.scrollers) assert.equal(s.canReachEnd, true, label + ': horizontal scroll end');
}
