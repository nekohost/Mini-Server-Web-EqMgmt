/* [MINI-COMMENT: STRATA.PAGE.FRAME]
 * [EN rev.1]
 * [Role] Opens the console after a bounded health check and keeps failure local to this menu.
 * [Dependencies] Admin-only status endpoint and the authenticated iframe.
 * [Impact] No inference is sent here; connection errors do not redirect other menus.
 */
(function () {
    'use strict';
    const frame = document.getElementById('strata-console');
    const status = document.getElementById('strata-status');
    const retry = document.getElementById('strata-retry');
    const notice = document.getElementById('strata-notice');
    const error = document.getElementById('strata-error');
    const navigation = document.querySelector('nav');
    let pending = false;

    function sizeFrame() {
        const header = navigation ? navigation.getBoundingClientRect().height : 0;
        const toolbar = document.querySelector('.strata-toolbar').getBoundingClientRect().height;
        frame.style.height = Math.max(360, (window.visualViewport?.height || window.innerHeight) - header - toolbar) + 'px';
    }
    function showFailure(message) {
        error.textContent = message;
        status.textContent = message;
        notice.hidden = false;
        frame.hidden = true;
        frame.src = 'about:blank';
    }
    async function connect() {
        if (pending) return;
        pending = true; retry.disabled = true;
        status.textContent = 'Strata 연결을 확인하고 있습니다.';
        try {
            const response = await fetch('/api/strata/status', {cache:'no-store', credentials:'same-origin'});
            if (response.status === 401) throw new Error('로그인이 만료되었습니다. 다시 로그인해 주세요.');
            if (response.status === 403) throw new Error('Strata 관리자 권한 또는 기능 설정을 확인해 주세요.');
            const data = await response.json();
            if (!response.ok || !data.connected) throw new Error(data.message || 'Strata에 연결할 수 없습니다.');
            status.textContent = data.message;
            notice.hidden = true;
            frame.hidden = false;
            if (frame.getAttribute('src') === 'about:blank') frame.src = frame.dataset.src;
            sizeFrame();
        } catch (failure) {
            showFailure(failure.message || '연결 상태를 확인할 수 없습니다. 다시 시도해 주세요.');
        } finally {
            pending = false; retry.disabled = false;
        }
    }
    window.addEventListener('message', function (event) {
        if (event.origin !== window.location.origin || event.source !== frame.contentWindow) return;
        if (event.data?.type === 'eqmgmt-strata-access-error') {
            showFailure('접근이 거부되었습니다. 로그인·관리자 권한 또는 Strata 연동 설정을 확인해 주세요.');
        }
    });
    window.addEventListener('resize', sizeFrame);
    window.visualViewport?.addEventListener('resize', sizeFrame);
    if (window.ResizeObserver && navigation) new ResizeObserver(sizeFrame).observe(navigation);
    retry.addEventListener('click', connect);
    connect();
})();
