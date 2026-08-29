/**
 * ================================================================================
 * [파일명]: Staging/static/js/session_timer.js
 * [역할]: 클라이언트-서버 간 사용자 세션 수명 주기(30분) 동기화, 만료 카운트다운 배지 렌더링, 5초 주기 동시 로그인 폴링 감지, Fetch API 자동 세션 연장 인터셉터 및 다크모드/사용자 개인화 설정 관리 스크립트
 * [의존성 관계]:
 *   - 상위 템플릿: templates/root_frame.html (HTML 하단에 로드되어 세션 및 테마 전역 제어)
 *   - 백엔드 API 엔드포인트:
 *     - POST /api/extend_session (세션 수명 30분 명시적 연장)
 *     - GET  /api/check_session  (5초 주기 세션 유효성 및 동시 로그인 감지 폴링)
 *     - GET  /api/user_settings  (사용자 개인화 테마 및 정렬 설정 조회)
 *     - POST /api/user_settings  (사용자 개인화 테마 및 정렬 설정 저장)
 *   - 대상 DOM 엘리먼트:
 *     - #session-timer-badge (상단바 세션 잔여 시간 표출 배지)
 *     - #smart-back-btn, #smart-back-text (스마트 뒤로가기 버튼)
 *     - #theme-toggle-btn, #theme-toggle-icon (상단바 테마 전환 아이콘)
 *     - #includeMineCheckbox (index.html 내 장비 최상단 표시 체크박스)
 *     - input[name="theme_setting"] (mypage.html 테마 라디오 버튼 그룹)
 * [변경 시 영향도]:
 *   - 세션 만료 시간, 자동 로그아웃 동작, 모든 API 통신 시의 세션 자동 연장 메커니즘 및 다크/라이트 테마 전역 렌더링에 직결됨
 * ================================================================================
 */

// [1] 전역 스코프 오염 방지 및 독립 실행 환경 조성을 위한 즉시 실행 함수(IIFE)
(function() {
    // [2] 사용자 맞춤 개인화 설정을 메모리에 캐싱할 전역 객체 선언
    window.userSettings = {};

    // [3] 표준 세션 유지 시간 상수 정의 (30분 = 30 * 60 * 1000 밀리초)
    const SESSION_DURATION = 30 * 60 * 1000;

    // [4] 클라이언트 기준 세션 만료 예정 절대 시각(타임스탬프) 변수 초기화
    let sessionEndTime = Date.now() + SESSION_DURATION;

    // [5] 1초 주기 타이머 UI 갱신 인터벌 핸들러 변수
    let timerInterval = null;

    // [6] 5초 주기 서버 세션 유효성 체크 폴링 인터벌 핸들러 변수
    let pollInterval = null;

    /**
     * [역할]: 클라이언트 로컬의 세션 만료 예정 시각을 현재 시각 기준 30분 뒤로 리셋하고 UI를 즉시 갱신합니다.
     * [의존성 관계]:
     *   - 전역 변수: SESSION_DURATION, sessionEndTime
     *   - 호출 함수: updateTimerUI()
     * [변경 시 영향도]:
     *   - 클라이언트 화면의 카운트다운 타이머가 즉시 30분으로 재설정됨
     */
    function resetSessionTimer() {
        // [1] 현재 시각에 30분(밀리초)을 더해 만료 시각 재계산
        sessionEndTime = Date.now() + SESSION_DURATION;

        // [2] 변경된 만료 시각을 기준으로 상단바 UI 배지 즉시 갱신
        updateTimerUI();
    }

    /**
     * [역할]: 서버의 /api/extend_session 엔드포인트에 비동기 POST 요청을 보내 Flask 세션 만료를 명시적으로 30분 연장합니다.
     * [의존성 관계]:
     *   - 백엔드 엔드포인트: POST /api/extend_session
     *   - 보안 함수: window.getCSRFToken()
     *   - 로컬 함수: resetSessionTimer(), showToast()
     * [변경 시 영향도]:
     *   - 서버 측 쿠키 및 Redis/세션 저장소의 세션 유효 시간이 갱신되며, 실패 시 세션 연장이 누락될 수 있음
     */
    async function extendSession() {
        try {
            // [1] 서버 세션 연장 API 비동기 호출 (CSRF 토큰 헤더 포함)
            const response = await fetch('/api/extend_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : ''
                }
            });

            // [2] 서버 JSON 응답 파싱
            const data = await response.json();

            // [3] 연장 성공 시 클라이언트 로컬 타이머를 리셋하고 성공 토스트 안내 표시
            if (data.success) {
                resetSessionTimer();
                showToast('세션이 연장되었습니다.');
            }
        } catch (error) {
            // [4] 통신 실패 시 콘솔에 에러 기록
            console.error('Session extension failed:', error);
        }
    }

    /**
     * [역할]: 화면 우측 하단에 3초간 표시되는 세션 연장 성공 토스트 알림창을 동적으로 생성하고 표출합니다.
     * [의존성 관계]:
     *   - DOM: document.body (하위에 #session-toast 동적 추가)
     * [변경 시 영향도]:
     *   - 세션 연장 성공 피드백 알림 메시지의 시각적 위치, 배경색 및 지속 시간(3초) 변경
     * @param {string} message - 토스트 알림에 표시할 문자열
     */
    function showToast(message) {
        // [1] 기존에 생성된 세션 토스트 엘리먼트가 있는지 확인
        let toast = document.getElementById('session-toast');

        // [2] 엘리먼트가 없으면 신규 div를 생성하여 인라인 스타일 및 Tailwind 속성 부여
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'session-toast';
            toast.style.position = 'fixed';
            toast.style.bottom = '20px';
            toast.style.right = '20px';
            toast.style.backgroundColor = '#10B981'; // Tailwind emerald-500
            toast.style.color = '#fff';
            toast.style.padding = '10px 20px';
            toast.style.borderRadius = '5px';
            toast.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
            toast.style.zIndex = '9999';
            toast.style.transition = 'opacity 0.3s ease';
            document.body.appendChild(toast);
        }

        // [3] 전달받은 메시지 텍스트를 주입하고 투명도를 1로 올려 화면에 노출
        toast.textContent = message;
        toast.style.opacity = '1';

        // [4] 3초(3000ms) 경과 후 서서히 사라지도록 투명도를 0으로 전환하는 타이머 등록
        setTimeout(() => {
            toast.style.opacity = '0';
        }, 3000);
    }

    /**
     * [역할]: 매 1초마다 상단바 #session-timer-badge 엘리먼트의 남은 시간을 계산하여 분/초 단위 텍스트 및 경고 스타일을 동적으로 갱신합니다.
     * [의존성 관계]:
     *   - DOM: #session-timer-badge
     *   - 전역 변수: sessionEndTime
     * [변경 시 영향도]:
     *   - 세션 잔여 시간 표기 형식(5분 이상: 분 단위, 5분 미만: 초 단위 붉은 펄스 깜빡임), 만료 시 강제 새로고침 동작이 변경됨
     */
    function updateTimerUI() {
        // [1] 상단바 세션 타이머 배지 엘리먼트 탐색
        const badge = document.getElementById('session-timer-badge');

        // [2] 타이머 배지가 없는 페이지(예: 로그인 화면, 에러 화면)인 경우 로직 조기 종료
        if (!badge) return;

        // [3] 현재 시각 취득 및 만료까지 남은 밀리초(remaining) 계산
        const now = Date.now();
        const remaining = sessionEndTime - now;

        // [4] 세션 만료 상태(남은 시간 0 이하) 처리
        if (remaining <= 0) {
            badge.innerHTML = '만료됨';
            badge.className = 'cursor-pointer px-2 py-1 bg-red-600 text-white text-xs rounded shadow-sm flex items-center gap-1';
            // 실제 만료 시 페이지를 즉시 새로고침하여 백엔드 인증 미들웨어의 강제 로그아웃/로그인 페이지 리다이렉트 유도
            window.location.reload(); 
            return;
        }

        // [5] 남은 분(minutes) 및 초(seconds) 단위 환산
        const minutes = Math.floor(remaining / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);

        // [6] 평상시 (5분 이상 남았을 때): 분 단위 텍스트 및 안정적인 회색/초록 호버 스타일 표출
        if (minutes >= 5) {
            badge.innerHTML = `⏱ ${minutes}분 남음`;
            badge.className = 'cursor-pointer px-2 py-1 bg-gray-100 hover:bg-emerald-100 hover:text-emerald-700 text-gray-600 text-xs rounded transition-colors flex items-center gap-1';
            badge.title = '클릭하여 세션 연장';
        } else {
            // [7] 만료 임박 시 (5분 미만 남았을 때): 00:00 초 단위 표출 및 붉은색 경고 깜빡임(animate-pulse) 스타일 적용
            const secStr = seconds < 10 ? '0' + seconds : seconds;
            badge.innerHTML = `⏱ <strong>${minutes}:${secStr}</strong> 남음 (연장)`;
            badge.className = 'cursor-pointer px-2 py-1 bg-red-100 hover:bg-red-200 text-red-600 text-xs rounded transition-colors flex items-center gap-1 animate-pulse';
            badge.title = '세션 만료가 임박했습니다. 클릭하여 연장하세요!';
        }
    }

    /**
     * [역할]: 타이머 UI 배지에 클릭 이벤트(수동 세션 연장)를 바인딩하고 1초 주기 인터벌 타이머를 가동합니다.
     * [의존성 관계]:
     *   - DOM: #session-timer-badge
     *   - 함수: extendSession(), updateTimerUI()
     * [변경 시 영향도]:
     *   - 타이머 배지 클릭 인터랙션 및 1초 주기 렌더링 루프 시작 시점 제어
     */
    function initTimer() {
        // [1] 배지 엘리먼트 검색
        const badge = document.getElementById('session-timer-badge');

        // [2] 배지가 존재하면 클릭 시 extendSession()이 실행되도록 이벤트 리스너 등록
        if (badge) {
            badge.addEventListener('click', extendSession);
            // [3] 즉시 1회 UI를 업데이트하여 초기 깜빡임 방지
            updateTimerUI();
            // [4] 1초(1000ms) 주기로 updateTimerUI()를 반복 실행하는 인터벌 등록
            timerInterval = setInterval(updateTimerUI, 1000);
        }
    }

    /**
     * [역할]: 5초 주기로 서버의 /api/check_session 엔드포인트를 호출하여 중복 로그인 또는 백엔드 세션 만료 여부를 실시간 폴링합니다.
     * [의존성 관계]:
     *   - 백엔드 엔드포인트: GET /api/check_session
     *   - 통신 함수: originalFetch
     * [변경 시 영향도]:
     *   - 다른 기기/브라우저에서 동일 계정으로 로그인 시 현재 기기에서 즉각 감지하여 에러 파라미터와 함께 로그인 화면으로 강제 이동시킴
     */
    async function pollSession() {
        try {
            // [1] 인터셉터를 거치지 않는 순수 Fetch로 세션 체크 API 호출
            const response = await originalFetch('/api/check_session');

            // [2] 401 Unauthorized(미인증/만료) 응답 수신 시
            if (response.status === 401) {
                const data = await response.json();
                // [3] 사유가 중복 로그인인 경우 해당 에러 코드를 붙여 로그인 페이지로 이동
                if (data.reason === 'concurrent_login') {
                    window.location.href = '/login?error=concurrent_login';
                } else {
                    // [4] 단순 세션 만료인 경우 세션 만료 코드를 붙여 로그인 페이지로 이동
                    window.location.href = '/login?error=session_expired';
                }
            }
        } catch (err) {
            // [5] 폴링 중 네트워크 오류 발생 시 콘솔 로깅
            console.error('Session poll failed:', err);
        }
    }

    // [7] 원본 window.fetch 함수를 별도 변수에 백업하여 재귀 호출 방지 및 인터셉터 구현 기반 마련
    const originalFetch = window.fetch;

    /**
     * [역할]: 전역 window.fetch를 가로채어(Intercept) 모든 비동기 API 통신 성공 시 클라이언트 세션 타이머를 자동으로 연장(Auto-Sync)합니다.
     * [의존성 관계]:
     *   - 전역 함수: window.fetch, originalFetch
     *   - 로컬 함수: resetSessionTimer()
     * [변경 시 영향도]:
     *   - 시스템 내의 모든 fetch 요청(장비 등록, 수정, 조회 등) 시 사용자가 화면을 이용 중이면 별도의 연장 버튼 클릭 없이도 세션이 무한 유지됨
     */
    window.fetch = async function(...args) {
        // [1] 요청 URL 문자열 추출
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;

        // [2] 원본 Fetch 함수를 실행하여 실제 서버 응답 취득
        const result = await originalFetch.apply(this, args);

        // [3] extend_session 자체 호출은 위에서 명시적으로 처리하므로 무한 루프 방지를 위해 제외
        if (url && !url.includes('/api/extend_session')) {
            // [4] API 응답이 성공(HTTP 200~299)한 경우 백엔드 세션도 갱신되었으므로 클라이언트 타이머도 리셋
            if (result.ok) {
                resetSessionTimer();
            } else if (result.status === 401) {
                // [5] 401 Unauthorized 발생 시 즉시 페이지를 새로고침하여 로그인 화면으로 강제 전환
                window.location.reload();
            }
        }

        // [6] 호출자에게 최종 응답 객체 반환
        return result;
    };

    /**
     * [역할]: 웹 브라우저의 referrer를 검사하여 안전한 내부 이동일 때만 스마트 뒤로가기 버튼을 활성화합니다.
     * [의존성 관계]:
     *   - DOM: #smart-back-btn, #smart-back-text
     *   - 브라우저 API: document.referrer, window.location.origin, window.history.back()
     * [변경 시 영향도]:
     *   - 포털이나 로그인 화면을 제외한 업무 화면 간 직전 페이지 복귀 편의성 제공
     */
    function initSmartBackNavigation() {
        // [1] 스마트 뒤로가기 버튼 및 텍스트 엘리먼트 검색
        const backBtn = document.getElementById('smart-back-btn');
        const backText = document.getElementById('smart-back-text');

        // [2] 버튼이 존재하는 경우 레퍼러 검증 수행
        if (backBtn) {
            const referrer = document.referrer;
            const origin = window.location.origin;

            // [3] 조건 검사: 1) 동일 도메인이면서 2) 직전 페이지가 포털(/portal)이 아니고 3) 로그인 페이지(/login)가 아닌 경우
            if (referrer && referrer.startsWith(origin) && 
                !referrer.endsWith('/portal') && 
                !referrer.includes('/login')) {

                // [4] 뒤로가기 텍스트를 '이전으로'로 변경
                if (backText) backText.innerText = '이전으로';

                // [5] 기본 href 이동 방지
                backBtn.href = 'javascript:void(0)';

                // [6] 클릭 시 브라우저 히스토리 이전 페이지(history.back()) 실행
                backBtn.onclick = function(e) {
                    e.preventDefault();
                    window.history.back();
                };
            }
        }
    }

    // [8] HTML DOM 트리가 완전히 파싱된 시점에 이벤트 리스너 실행
    document.addEventListener('DOMContentLoaded', async () => {
        // [1] 로컬 스토리지에 캐시된 테마 설정을 기반으로 깜빡임 없는 고속 테마 렌더링
        applyThemeUI(localStorage.theme || 'system');

        // [2] 타이머 이벤트 및 1초 루프 초기화
        initTimer();

        // [3] 스마트 뒤로가기 버튼 초기화
        initSmartBackNavigation();

        // [4] 5초(5000ms) 주기로 서버 세션 유효성을 체크하는 폴링 인터벌 등록
        pollInterval = setInterval(pollSession, 5000);

        // [5] 서버에 저장된 사용자 개인화 설정 비동기 로드 및 화면 반영
        await loadUserSettings();
    });

    /**
     * [역할]: 서버의 /api/user_settings 엔드포인트에서 사용자 설정(테마, 장비 정렬 기본값 등)을 가져와 메모리에 캐시하고 UI에 반영합니다.
     * [의존성 관계]:
     *   - 백엔드 엔드포인트: GET /api/user_settings
     *   - 전역 객체: window.userSettings
     *   - 로컬 함수: applySettings()
     * [변경 시 영향도]:
     *   - 로그인한 사용자별로 저장된 다크모드 및 목록 필터 기본값이 화면에 자동 적용됨
     */
    window.loadUserSettings = async function() {
        try {
            // [1] 사용자 설정 API 비동기 조회
            const res = await originalFetch('/api/user_settings');

            // [2] 응답 성공 시 메모리에 저장하고 UI 반영 함수 호출
            if (res.ok) {
                const data = await res.json();
                window.userSettings = data.settings || {};
                applySettings(window.userSettings);
            }
        } catch(e) {
            // [3] 설정 로드 실패 시 콘솔 로깅
            console.error('Failed to load user settings', e);
        }
    };

    /**
     * [역할]: 사용자가 변경한 개인화 설정을 서버의 /api/user_settings에 POST로 저장하고 로컬 UI에 즉시 동기화합니다.
     * [의존성 관계]:
     *   - 백엔드 엔드포인트: POST /api/user_settings
     *   - 보안 함수: window.getCSRFToken()
     *   - 로컬 함수: applySettings()
     * [변경 시 영향도]:
     *   - 테마 전환, 정렬 옵션 변경 등이 서버 DB에 영구 보존되어 다음 로그인 시에도 유지됨
     * @param {Object} newSettings - 저장할 설정 키/값 딕셔너리 (예: { theme: 'dark' })
     */
    window.saveUserSettings = async function(newSettings) {
        try {
            // [1] 설정 저장 API 비동기 POST 호출 (CSRF 토큰 및 JSON 본문 전달)
            const res = await originalFetch('/api/user_settings', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCSRFToken ? window.getCSRFToken() : ''
                },
                body: JSON.stringify(newSettings)
            });

            // [2] 저장 성공 시 메모리 갱신 및 UI 재반영
            if (res.ok) {
                const data = await res.json();
                window.userSettings = data.settings;
                applySettings(window.userSettings);
            }
        } catch(e) {
            // [3] 설정 저장 실패 시 콘솔 로깅
            console.error('Failed to save user settings', e);
        }
    };

    /**
     * [역할]: 전달받은 사용자 설정 객체(settings)를 기반으로 테마 적용 및 인덱스 화면의 체크박스 상태를 동기화합니다.
     * [의존성 관계]:
     *   - DOM: #includeMineCheckbox
     *   - 함수: applyThemeUI(), window.fetchEquipment()
     * [변경 시 영향도]:
     *   - 화면 테마가 전환되고 '내 장비 최상단 보기' 체크박스 복원 및 목록 자동 재조회가 트리거됨
     * @param {Object} settings - 사용자 설정 객체
     */
    function applySettings(settings) {
        // [1] 테마 UI 및 로컬 스토리지 동기화
        const theme = settings.theme || 'system';
        applyThemeUI(theme);

        // [2] index.html의 '내 장비 최상단 보기' 체크박스 상태 복원
        const cb = document.getElementById('includeMineCheckbox');
        if (cb && settings.show_my_equip_first !== undefined) {
            // 값이 실제로 변경되었을 때만 처리하여 무한 호출 루프 방지
            if (cb.checked !== settings.show_my_equip_first) {
                cb.checked = settings.show_my_equip_first;
                // 체크박스 상태가 변경되면 장비 목록 조회 함수 재호출
                if (typeof window.fetchEquipment === 'function') {
                    window.fetchEquipment();
                }
            }
        }
    }

    /**
     * [역할]: 'dark', 'light', 'system' 테마에 맞춰 <html> 루트 태그에 'dark' 클래스를 토글하고 로컬 스토리지 및 라디오 버튼을 동기화합니다.
     * [의존성 관계]:
     *   - DOM: document.documentElement (<html> 태그), input[name="theme_setting"]
     *   - 브라우저 API: localStorage, window.matchMedia
     *   - 함수: updateThemeToggleIcon()
     * [변경 시 영향도]:
     *   - 전체 페이지의 Tailwind CSS 다크모드 스타일 활성화/비활성화 및 아이콘 렌더링 전환
     * @param {string} theme - 'dark' | 'light' | 'system'
     */
    function applyThemeUI(theme) {
        // [1] 다크 모드 명시적 적용
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
        } else if (theme === 'light') {
            // [2] 라이트 모드 명시적 적용
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
        } else { 
            // [3] 시스템 설정 따름 (system) 적용
            localStorage.theme = 'system';
            // OS가 다크모드인지 감지하여 <html> 태그 클래스 반영
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }

        // [4] 상단바 테마 토글 버튼의 아이콘 및 툴팁 텍스트 갱신
        updateThemeToggleIcon(theme);

        // [5] 마이페이지(mypage.html) 내부의 테마 선택 라디오 버튼 상태 동기화
        const themeRadios = document.querySelectorAll('input[name="theme_setting"]');
        if (themeRadios.length > 0) {
            themeRadios.forEach(radio => {
                radio.checked = (radio.value === theme);
            });
        }
    }

    /**
     * [역할]: 상단 네비게이션 바의 #theme-toggle-icon 클래스 및 #theme-toggle-btn 툴팁(title)을 현재 테마 모드에 맞춰 동적으로 변경합니다.
     * [의존성 관계]:
     *   - DOM: #theme-toggle-btn, #theme-toggle-icon
     * [변경 시 영향도]:
     *   - 사용자가 상단바의 아이콘(해/달/모니터)을 보고 현재 활성화된 테마 및 클릭 시 변경될 다음 테마를 직관적으로 인지할 수 있음
     * @param {string} theme - 'dark' | 'light' | 'system'
     */
    function updateThemeToggleIcon(theme) {
        // [1] 테마 토글 버튼 및 아이콘 엘리먼트 검색
        const btn = document.getElementById('theme-toggle-btn');
        const icon = document.getElementById('theme-toggle-icon');

        // [2] 아이콘 엘리먼트가 없으면 조기 종료
        if (!icon) return;

        // [3] 라이트 모드일 때: 태양 아이콘(fa-sun, 호박색) 표출
        if (theme === 'light') {
            icon.className = 'fa-solid fa-sun text-lg text-amber-500';
            if (btn) btn.title = '테마: 라이트 모드 (클릭 시 다크 모드로 변경)';
        } else if (theme === 'dark') {
            // [4] 다크 모드일 때: 달 아이콘(fa-moon, 인디고색) 표출
            icon.className = 'fa-solid fa-moon text-lg text-indigo-400';
            if (btn) btn.title = '테마: 다크 모드 (클릭 시 시스템 설정으로 변경)';
        } else { 
            // [5] 시스템 설정일 때: 데스크톱 아이콘(fa-desktop, 회색) 표출
            icon.className = 'fa-solid fa-desktop text-lg text-slate-500 dark:text-slate-400';
            if (btn) btn.title = '테마: 시스템 설정 따름 (클릭 시 라이트 모드로 변경)';
        }
    }

    // [9] 사용자의 OS 시스템 테마(라이트/다크) 실시간 변경 이벤트 감지 리스너 등록
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        const currentTheme = window.userSettings?.theme || localStorage.theme || 'system';
        // 현재 설정이 'system'일 때만 OS 변경 이벤트에 즉시 반응
        if (currentTheme === 'system') {
            if (e.matches) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }
    });

    /**
     * [역할]: 상단바 테마 토글 버튼 클릭 시 'light' -> 'dark' -> 'system' 3단계로 순환 변경하고 서버에 저장합니다.
     * [의존성 관계]:
     *   - 전역 객체: window.userSettings, localStorage
     *   - 함수: window.saveUserSettings()
     * [변경 시 영향도]:
     *   - 상단바 버튼 클릭 한 번으로 모든 화면의 테마 모드가 즉각 순환 전환됨
     */
    window.toggleTheme = function() {
        // [1] 현재 활성화된 테마 확인
        const currentTheme = window.userSettings?.theme || localStorage.theme || 'system';

        // [2] light -> dark -> system 3단계 순환 분기
        let nextTheme = 'light';
        if (currentTheme === 'light') {
            nextTheme = 'dark';
        } else if (currentTheme === 'dark') {
            nextTheme = 'system';
        } else {
            nextTheme = 'light';
        }

        // [3] 변경된 테마를 서버 저장 함수에 전달하여 DB 저장 및 UI 반영 수행
        window.saveUserSettings({ theme: nextTheme });
    };

})();
