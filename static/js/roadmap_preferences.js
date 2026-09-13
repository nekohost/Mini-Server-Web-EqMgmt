/* [역할] 제안 019/008 설정 UI. [의존성 관계] session_timer applySettings. [변경 시 영향도] 계정별 서버 설정만 사용합니다. */
(function () {
    'use strict';
    // [역할] 허용 스킨/동의만 화면에 복원. [의존성 관계] 서버 PreferencesJSON. [변경 시 영향도] 다른 계정 캐시 유출 없음.
    window.applyRoadmapSettings = function (settings) {
        const skin = settings.layout_skin === 'edge' ? 'edge' : 'standard';
        document.documentElement.dataset.layoutSkin = skin;
        const select = document.getElementById('roadmap-skin'), optIn = document.getElementById('roadmap-opt-in');
        if (select) select.value = skin;
        if (optIn) optIn.checked = settings.deadline_email_opt_in === true;
    };
    document.addEventListener('DOMContentLoaded', () => {
        const button = document.getElementById('roadmap-preferences-save');
        if (!button) return;
        window.applyRoadmapSettings(window.userSettings || {});
        button.addEventListener('click', async () => {
            const message = document.getElementById('roadmap-preferences-message');
            button.disabled = true; message.textContent = '저장 중입니다…';
            try {
                const response = await fetch('/api/user_settings', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken()}, body: JSON.stringify({layout_skin: document.getElementById('roadmap-skin').value, deadline_email_opt_in: document.getElementById('roadmap-opt-in').checked})});
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || result.error || '설정을 저장하지 못했습니다.');
                window.userSettings = result.settings; window.applyRoadmapSettings(result.settings);
                message.textContent = '설정을 저장했습니다.';
            } catch (error) { message.textContent = error.message; }
            finally { button.disabled = false; }
        });
    });
})();
