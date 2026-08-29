/**
 * ================================================================================
 * [파일명]: Staging/static/js/common.js
 * [역할]: 웹 시스템 전역에서 공통으로 사용되는 UI 오버레이, 메시지 상수 및 보안(CSRF) 유틸리티 제어 스크립트
 * [의존성 관계]:
 *   - 상위 템플릿: templates/root_frame.html (HTML 헤더에 선행 로드되어 전역 window 객체에 유틸리티 등록)
 *   - 대상 DOM 엘리먼트:
 *     - #global-loading-overlay (전역 반투명 배경 및 스피너 컨테이너)
 *     - #global-loading-text (로딩 메시지 텍스트 출력 span)
 *     - meta[name="csrf-token"] (Flask 서버가 주입한 세션 고유 CSRF 보안 토큰 메타 태그)
 *   - 호출 모듈: portal.html, dashboard.html, dynamic_metadata_*.html 등 모든 비동기 AJAX(fetch) 호출 스크립트
 * [변경 시 영향도]:
 *   - 전역 로딩 오버레이 렌더링, 메시지 표출 방식 및 모든 상태 변경 POST/PUT/DELETE fetch 요청의 CSRF 인증 헤더 취득에 직결됨
 * ================================================================================
 */

// [1] 전역 UI 메시지 중앙 집중 관리 상수 객체 정의 (추후 DB 연동 및 다국어 확장을 위한 단일 진실 공급원)
const UI_MESSAGES = {
    // 기본 로딩 안내 메시지 (파라미터 미전달 시 기본 폴백 값으로 사용)
    LOADING_DEFAULT: "작업 처리 중입니다..."
};

/**
 * [역할]: 화면 전체를 덮는 전역 반투명 로딩 오버레이 및 안내 문구를 표출합니다.
 * [의존성 관계]:
 *   - HTML DOM: root_frame.html 내부의 #global-loading-overlay, #global-loading-text
 *   - 전역 상수: UI_MESSAGES.LOADING_DEFAULT
 *   - 호출 지점: 데이터 조회(fetch), 장비 등록/수정/삭제, 백업 생성 등 긴 지연시간이 예상되는 모든 비동기 작업 시작 지점
 * [변경 시 영향도]:
 *   - 비동기 처리 중 사용자의 중복 클릭/입력을 방지하는 전역 차단 UI의 표시 방식 및 메시지 노출 메커니즘이 변경됨
 * @param {string} message - 로딩 스피너 하단에 표시할 사용자 맞춤 안내 문구 (기본값: UI_MESSAGES.LOADING_DEFAULT)
 */
window.showGlobalLoading = function(message = UI_MESSAGES.LOADING_DEFAULT) {
    // [1] DOM에서 전역 로딩 오버레이 컨테이너 엘리먼트 검색
    const overlay = document.getElementById('global-loading-overlay');

    // [2] DOM에서 로딩 텍스트를 출력할 텍스트 엘리먼트 검색
    const textEl = document.getElementById('global-loading-text');

    // [3] 오버레이와 텍스트 엘리먼트가 모두 정상적으로 존재하는지 유효성 검사
    if (overlay && textEl) {
        // [4] 전달받은 메시지 문자열을 텍스트 엘리먼트에 안전하게 주입 (XSS 방어를 위해 textContent 사용)
        textEl.textContent = message;

        // [5] Tailwind CSS 숨김 클래스('hidden') 제거하여 요소를 화면에 활성화
        overlay.classList.remove('hidden');

        // [6] 중앙 정렬 플렉스 레이아웃 클래스('flex')를 추가하여 화면 정중앙에 스피너와 문구 렌더링
        overlay.classList.add('flex');
    }
};

/**
 * [역할]: 화면에 표출 중인 전역 로딩 오버레이를 닫고 일반 화면으로 복원합니다.
 * [의존성 관계]:
 *   - HTML DOM: root_frame.html 내부의 #global-loading-overlay
 *   - 호출 지점: 비동기 AJAX(fetch) 통신의 성공(then), 실패(catch), 또는 최종 완료(finally) 블록
 * [변경 시 영향도]:
 *   - 비동기 처리가 끝난 후 로딩 오버레이가 정상적으로 해제되지 않으면 화면이 조작 불가능(Freezing) 상태에 빠질 수 있음
 */
window.hideGlobalLoading = function() {
    // [1] DOM에서 전역 로딩 오버레이 엘리먼트 검색
    const overlay = document.getElementById('global-loading-overlay');

    // [2] 오버레이 엘리먼트가 존재하는 경우 스타일 클래스 전환
    if (overlay) {
        // [3] Tailwind CSS 숨김 클래스('hidden')를 추가하여 화면에서 감춤
        overlay.classList.add('hidden');

        // [4] 플렉스 레이아웃 클래스('flex')를 제거하여 디스플레이 속성 비활성화
        overlay.classList.remove('flex');
    }
};

/**
 * [역할]: HTML 문서 헤더(<head>)의 메타 태그에 서버가 렌더링한 전역 CSRF 보안 토큰 값을 추출하여 반환합니다.
 * [의존성 관계]:
 *   - HTML DOM: root_frame.html의 <meta name="csrf-token" content="{{ csrf_token() }}">
 *   - 호출 지점: POST, PUT, DELETE, PATCH 등 서버의 상태를 변경하는 모든 비동기 fetch 요청의 'X-CSRFToken' 헤더 구성부
 * [변경 시 영향도]:
 *   - 토큰이 누락되거나 잘못 반환될 경우 서버(Flask-WTF / CSRFProtect)에서 HTTP 400 Bad Request (CSRF token missing/invalid) 오류를 반환하여 모든 쓰기 작업이 실패함
 * @returns {string} CSRF 보안 토큰 문자열 (태그 미존재 시 빈 문자열 반환)
 */
window.getCSRFToken = function() {
    // [1] DOM <head> 내에서 name 속성이 'csrf-token'인 meta 태그 검색
    const meta = document.querySelector('meta[name="csrf-token"]');

    // [2] meta 태그가 존재하면 content 속성값(토큰 문자열)을 반환하고, 없으면 빈 문자열('')을 안전하게 반환
    return meta ? meta.getAttribute('content') : '';
};
