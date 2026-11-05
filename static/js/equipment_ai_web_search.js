/* [MINI-COMMENT: ASSISTANT.WEB.UI] [EN rev.1]
 * [Role] Renders only server-projected search sources as safe native disclosures and explicit external links.
 * [Dependencies] Existing stable message articles and bounded versioned source arrays; no fetch, HTML parser or model-generated links.
 * [Impact] Repeated snapshots preserve focus/open state, result instructions remain text and citations never execute equipment operations.
 */
(function (global) {
    'use strict';
    function safeUrl(value) {
        /* [Role] Duplicates the citation's public-domain HTTPS boundary before assigning href. */
        if (typeof value !== 'string' || value.length > 1500 || /[\s\\\u0000-\u001f\u007f]/u.test(decodeSafe(value))) return null;
        try {
            const url = new URL(value), host = url.hostname;
            if (url.protocol !== 'https:' || url.username || url.password || url.port && url.port !== '443' || host.includes(':') || /^\d+(?:\.\d+)*$/.test(host)) return null;
            const labels = host.split('.');
            if (labels.length < 2 || labels.some(part => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/iu.test(part)) || /^\d+$/.test(labels.at(-1)) || /^(?:localhost|local|internal|test|invalid|onion)$/iu.test(labels.at(-1))) return null;
            return url.href;
        } catch (_) { return null; }
    }
    function decodeSafe(value) {
        /* [Role] Makes encoded control/backslash/whitespace visible to the URL rejection check without navigation. */
        try { return decodeURIComponent(decodeURIComponent(value)); } catch (_) { return '\u0000'; }
    }
    function render(article, searches) {
        /* [MINI-COMMENT: ASSISTANT.WEB.CITATIONS] [EN rev.1]
         * [Role] Appends bounded authoritative search evidence to one existing owner-visible message.
         * [Dependencies] At most two searches/five plain-text source records each and server-projected HTTPS URLs.
         * [Impact] No automatic outbound request, raw HTML or unsafe link; reload/trash view remains a read-only citation display.
         */
        if (!article || !Array.isArray(searches)) return;
        const accepted = searches.slice(0,2).map(search => ({
            query: String(search.query || '').slice(0,300), at: String(search.searched_at || '').slice(0,60),
            results: (Array.isArray(search.results) ? search.results : []).slice(0,5).map(item => ({
                title: String(item.title || '').slice(0,180), snippet: String(item.snippet || '').slice(0,700), url: safeUrl(item.url)
            })).filter(item => item.url && item.title)
        }));
        let element = article.querySelector('.ai-web-sources');
        const signature = JSON.stringify(accepted);
        if (element?.dataset.signature === signature || !accepted.length && !element) return;
        const opened = element?.open || false;
        if (!element) { element = article.ownerDocument.createElement('details'); element.className = 'ai-web-sources'; article.append(element); }
        const doc = article.ownerDocument, fragment = doc.createDocumentFragment(), summary = doc.createElement('summary');
        summary.textContent = '웹 검색 출처 · Yahoo · ' + accepted.reduce((sum,search) => sum + search.results.length,0) + '건'; fragment.append(summary);
        const note = doc.createElement('p'); note.className = 'ai-web-source-note'; note.textContent = '검색 결과의 제목과 요약입니다. 원문 전체를 열람한 결과는 아닙니다.'; fragment.append(note);
        for (const search of accepted) {
            const heading = doc.createElement('p'); heading.className = 'ai-web-query'; heading.textContent = '검색어: ' + search.query; fragment.append(heading);
            const when = doc.createElement('p'); when.className = 'ai-web-source-note'; when.textContent = '검색 시각: ' + search.at; fragment.append(when);
            if (!search.results.length) { const empty = doc.createElement('p'); empty.textContent = '검색 결과가 없습니다.'; fragment.append(empty); continue; }
            const list = doc.createElement('ol');
            for (const source of search.results) {
                const item = doc.createElement('li'), link = doc.createElement('a'), snippet = doc.createElement('p');
                link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.referrerPolicy = 'no-referrer'; link.textContent = source.title; link.title = source.url;
                snippet.textContent = source.snippet; item.append(link,snippet); list.append(item);
            }
            fragment.append(list);
        }
        element.replaceChildren(fragment); element.dataset.signature = signature; element.open = opened;
    }
    const api = {safeUrl,render};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    global.EquipmentAiWebSearch = api;
})(typeof window !== 'undefined' ? window : globalThis);
