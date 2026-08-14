/**
 * [역할] 전역 공통 유틸리티 및 UI 상태 제어 스크립트
 * [의존성 관계] root_frame.html 템플릿에 선로드됨
 * [변경 시 영향도] 모든 전역 로딩 오버레이 및 공통 메시지 렌더링에 영향
 */

// UI 메시지 상수 딕셔너리 (추후 DB 연동 및 다국어 확장을 위한 중앙 집중 관리)
const UI_MESSAGES = {
    LOADING_DEFAULT: "작업 처리 중입니다..."
};

/**
 * [역할]: 전역 로딩 오버레이 표출
 * [의존성 관계]: root_frame.html의 #global-loading-overlay 및 #global-loading-text DOM 요소
 * [변경 시 영향도]: 모든 비동기 처리(fetch) 시 발생하는 오버레이의 렌더링 방식 및 메시지 노출 방식이 변경됨
 * @param {string} message - 오버레이에 표출할 메시지 (기본값: UI_MESSAGES.LOADING_DEFAULT)
 */
window.showGlobalLoading = function(message = UI_MESSAGES.LOADING_DEFAULT) {
    const overlay = document.getElementById('global-loading-overlay');
    const textEl = document.getElementById('global-loading-text');
    if (overlay && textEl) {
        textEl.textContent = message;
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
    }
};

/**
 * [역할]: 전역 로딩 오버레이 숨김
 * [의존성 관계]: root_frame.html의 #global-loading-overlay DOM 요소
 * [변경 시 영향도]: 모든 비동기 처리 완료 시 오버레이가 닫히는 동작 방식이 변경됨
 */
window.hideGlobalLoading = function() {
    const overlay = document.getElementById('global-loading-overlay');
    if (overlay) {
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
    }
};

/**
 * [역할]: 메타 태그에 정의된 전역 CSRF 토큰을 반환합니다.
 * [의존성 관계]: root_frame.html의 <meta name="csrf-token"> 요소
 * [변경 시 영향도]: 모든 비동기 상태 변경(fetch) 요청 시 CSRF 토큰 헤더 탑재에 영향을 줍니다.
 * @returns {string} CSRF 토큰 문자열
 */
window.getCSRFToken = function() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
};
