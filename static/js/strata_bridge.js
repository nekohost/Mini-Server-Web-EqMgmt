/* [MINI-COMMENT: STRATA.CONSOLE.BRIDGE]
 * [EN rev.1]
 * [Role] Adapts the pinned Strata UI to website authentication without a shared browser API key.
 * [Dependencies] Server-rendered CSRF/namespace metadata and the Nginx /strata/ gateway.
 * [Impact] Chat storage is session-scoped; mutating fetches carry CSRF and access failures lock the frame.
 */
(function () {
    'use strict';
    const metadata = name => document.querySelector('meta[name="' + name + '"]')?.content || '';
    const csrf = metadata('eqmgmt-strata-csrf');
    const identity = metadata('eqmgmt-strata-namespace');
    if (!/^[a-f0-9]{32}$/.test(identity) || !csrf) throw new Error('Strata authentication context is missing');
    const namespace = 'eqmgmt.strata.' + identity + '.';
    const activeKey = 'eqmgmt.strata.active';
    const prototype = Storage.prototype;
    const nativeGet = prototype.getItem;
    const nativeSet = prototype.setItem;
    const nativeRemove = prototype.removeItem;
    const nativeKey = prototype.key;
    const nativeFetch = window.fetch.bind(window);
    let storage;
    try { storage = window.localStorage; } catch (failure) { storage = null; }

    function removeNamespace(prefix) {
        if (!storage || !/^eqmgmt\.strata\.[a-f0-9]{32}\.$/.test(prefix || '')) return;
        try {
            for (let index = storage.length - 1; index >= 0; index--) {
                const key = nativeKey.call(storage, index);
                if (key?.startsWith(prefix)) nativeRemove.call(storage, key);
            }
        } catch (failure) { /* Storage may be disabled; the original UI keeps working in memory. */ }
    }
    if (storage) {
        try {
            const previous = nativeGet.call(storage, activeKey);
            if (previous && previous !== namespace) removeNamespace(previous);
            nativeSet.call(storage, activeKey, namespace);
        } catch (failure) { /* Do not turn a storage policy into a page failure. */ }
    }
    prototype.getItem = function (key) {
        if (this === storage && key === 'strata.apikey') return null;
        return nativeGet.call(this, this === storage && String(key).startsWith('strata.') ? namespace + key : key);
    };
    prototype.setItem = function (key, value) {
        if (this === storage && key === 'strata.apikey') return;
        return nativeSet.call(this, this === storage && String(key).startsWith('strata.') ? namespace + key : key, value);
    };
    prototype.removeItem = function (key) {
        return nativeRemove.call(this, this === storage && String(key).startsWith('strata.') ? namespace + key : key);
    };
    const forget = () => removeNamespace(namespace);
    const accessFailed = () => {
        forget();
        window.parent.postMessage({type:'eqmgmt-strata-access-error'}, window.location.origin);
    };
    window.fetch = async function (input, options) {
        const url = new URL(input instanceof Request ? input.url : input, document.baseURI);
        if (url.origin !== window.location.origin || !url.pathname.startsWith('/strata/')) {
            throw new TypeError('The embedded console only connects through its configured gateway');
        }
        const request = input instanceof Request ? input : new Request(url.href);
        const headers = new Headers(options?.headers || request.headers);
        headers.delete('Authorization');
        headers.delete('x-api-key');
        const method = String(options?.method || request.method || 'GET').toUpperCase();
        if (!['GET', 'HEAD'].includes(method)) headers.set('X-CSRFToken', csrf);
        const response = await nativeFetch(request, {...options, headers, credentials:'same-origin', cache:'no-store'});
        if (response.status === 401 || response.status === 403) accessFailed();
        return response;
    };
    window.addEventListener('message', function (event) {
        if (event.source === window.parent && event.origin === window.location.origin &&
            event.data?.type === 'eqmgmt-strata-forget') forget();
    });
    try {
        window.parent.document.addEventListener('click', function (event) {
            const link = event.target.closest?.('a[href]');
            if (link && new URL(link.href).pathname === '/logout') forget();
        }, true);
    } catch (failure) { /* A different embedding origin is not granted access. */ }
})();
