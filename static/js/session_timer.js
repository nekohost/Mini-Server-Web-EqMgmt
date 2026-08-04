// session_timer.js
// 세션 만료 시간(기본 30분) 및 동기화 스크립트

(function() {
    // 전역 상태
    window.userSettings = {};
    const SESSION_DURATION = 30 * 60 * 1000; // 30분 (밀리초)
    let sessionEndTime = Date.now() + SESSION_DURATION;
    let timerInterval = null;
    let pollInterval = null;

    // 세션 시간 연장 (클라이언트 로컬 변수 리셋)
    function resetSessionTimer() {
        sessionEndTime = Date.now() + SESSION_DURATION;
        updateTimerUI();
    }

    // 명시적 세션 연장 요청 (서버 통신)
    async function extendSession() {
        try {
            const response = await fetch('/api/extend_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            const data = await response.json();
            if (data.success) {
                resetSessionTimer();
                showToast('세션이 연장되었습니다.');
            }
        } catch (error) {
            console.error('Session extension failed:', error);
        }
    }

    // 간단한 토스트 알림 함수
    function showToast(message) {
        let toast = document.getElementById('session-toast');
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
        toast.textContent = message;
        toast.style.opacity = '1';
        
        setTimeout(() => {
            toast.style.opacity = '0';
        }, 3000);
    }

    // 타이머 UI 업데이트 로직
    function updateTimerUI() {
        const badge = document.getElementById('session-timer-badge');
        if (!badge) return; // UI가 없는 페이지(예: 로그인화면)는 무시

        const now = Date.now();
        const remaining = sessionEndTime - now;

        if (remaining <= 0) {
            badge.innerHTML = '만료됨';
            badge.className = 'cursor-pointer px-2 py-1 bg-red-600 text-white text-xs rounded shadow-sm flex items-center gap-1';
            // 실제 만료 시 페이지 새로고침을 통해 백엔드의 강제 로그아웃/리다이렉트를 타게 함
            window.location.reload(); 
            return;
        }

        const minutes = Math.floor(remaining / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);

        // 평상시: 분 단위 표출 (5분 이상 남았을 때)
        if (minutes >= 5) {
            badge.innerHTML = `⏱ ${minutes}분 남음`;
            badge.className = 'cursor-pointer px-2 py-1 bg-gray-100 hover:bg-emerald-100 hover:text-emerald-700 text-gray-600 text-xs rounded transition-colors flex items-center gap-1';
            badge.title = '클릭하여 세션 연장';
        } else {
            // 임박 시(5분 미만): 초 단위 표출 및 붉은색 경고
            const secStr = seconds < 10 ? '0' + seconds : seconds;
            badge.innerHTML = `⏱ <strong>${minutes}:${secStr}</strong> 남음 (연장)`;
            badge.className = 'cursor-pointer px-2 py-1 bg-red-100 hover:bg-red-200 text-red-600 text-xs rounded transition-colors flex items-center gap-1 animate-pulse';
            badge.title = '세션 만료가 임박했습니다. 클릭하여 연장하세요!';
        }
    }

    // 초기화 및 이벤트 바인딩
    function initTimer() {
        // UI가 로드된 이후에 이벤트 할당을 시도
        const badge = document.getElementById('session-timer-badge');
        if (badge) {
            badge.addEventListener('click', extendSession);
            updateTimerUI();
            timerInterval = setInterval(updateTimerUI, 1000);
        }
    }

    // 서버에 세션 유효성(동시 로그인 여부 등)을 주기적으로 확인하는 폴링 함수
    async function pollSession() {
        try {
            const response = await originalFetch('/api/check_session');
            if (response.status === 401) {
                const data = await response.json();
                if (data.reason === 'concurrent_login') {
                    window.location.href = '/login?error=concurrent_login';
                } else {
                    window.location.href = '/login?error=session_expired';
                }
            }
        } catch (err) {
            console.error('Session poll failed:', err);
        }
    }

    // Fetch API 전역 인터셉터 (Auto-Sync)
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        const result = await originalFetch.apply(this, args);
        
        // extend_session 자체 호출은 위에서 명시적으로 처리하므로 제외
        if (url && !url.includes('/api/extend_session')) {
            // 다른 API 통신이 성공적이면 백엔드 세션도 연장된 것이므로 프론트엔드도 리셋
            if (result.ok) {
                resetSessionTimer();
            } else if (result.status === 401) {
                // 동시 로그인 등에 의해 401 Unauthorized 발생 시 즉각 새로고침하여 로그인창으로
                window.location.reload();
            }
        }
        return result;
    };

    // 스마트 동적 뒤로가기 네비게이션 초기화
    function initSmartBackNavigation() {
        const backBtn = document.getElementById('smart-back-btn');
        const backText = document.getElementById('smart-back-text');
        if (backBtn) {
            const referrer = document.referrer;
            const origin = window.location.origin;
            
            // 1) 동일 도메인이면서 2) 직전 페이지가 포털이 아니고 3) 로그인 페이지가 아닌 경우에만 '이전으로' 활성화
            if (referrer && referrer.startsWith(origin) && 
                !referrer.endsWith('/portal') && 
                !referrer.includes('/login')) {
                
                if (backText) backText.innerText = '이전으로';
                backBtn.href = 'javascript:void(0)';
                backBtn.onclick = function(e) {
                    e.preventDefault();
                    window.history.back();
                };
            }
        }
    }

    // DOM 로드 시 초기화
    document.addEventListener('DOMContentLoaded', async () => {
        // 빠른 테마 초기화 (로컬 스토리지 캐시 기반)
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        initTimer();
        initSmartBackNavigation();
        pollInterval = setInterval(pollSession, 5000);
        
        // 서버 설정 동기화
        await loadUserSettings();
    });

    // 서버 설정 로드
    window.loadUserSettings = async function() {
        try {
            const res = await originalFetch('/api/user_settings');
            if (res.ok) {
                const data = await res.json();
                window.userSettings = data.settings || {};
                applySettings(window.userSettings);
            }
        } catch(e) {
            console.error('Failed to load user settings', e);
        }
    };

    // 서버 설정 저장
    window.saveUserSettings = async function(newSettings) {
        try {
            const res = await originalFetch('/api/user_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newSettings)
            });
            if (res.ok) {
                const data = await res.json();
                window.userSettings = data.settings;
                applySettings(window.userSettings);
            }
        } catch(e) {
            console.error('Failed to save user settings', e);
        }
    };

    // 설정 기반으로 UI 반영 (다크 모드, 인덱스 화면 체크박스 등)
    function applySettings(settings) {
        // 1. 테마 UI 및 설정 동기화
        const theme = settings.theme || 'system';
        applyThemeUI(theme);

        // 2. index.html의 '내 장비 최상단 보기' 체크박스 복원
        const cb = document.getElementById('includeMineCheckbox');
        if (cb && settings.show_my_equip_first !== undefined) {
            // 값이 변경되었을 때만 처리(무한 루프 방지)
            if (cb.checked !== settings.show_my_equip_first) {
                cb.checked = settings.show_my_equip_first;
                // 체크박스 상태가 바뀌면 리스트 다시 불러오기
                if (typeof window.fetchEquipment === 'function') {
                    window.fetchEquipment();
                }
            }
        }
    }

    // 테마 UI 적용 및 동기화
    function applyThemeUI(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
            localStorage.theme = 'dark';
        } else if (theme === 'light') {
            document.documentElement.classList.remove('dark');
            localStorage.theme = 'light';
        } else { // system
            localStorage.theme = 'system';
            if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }

        // 상단바 아이콘 업데이트
        updateThemeToggleIcon(theme);

        // 마이페이지(mypage.html) 라디오 버튼 동기화
        const themeRadios = document.querySelectorAll('input[name="theme_setting"]');
        if (themeRadios.length > 0) {
            themeRadios.forEach(radio => {
                radio.checked = (radio.value === theme);
            });
        }
    }

    // 상단 테마 토글 버튼 아이콘 및 타이틀 동적 업데이트
    function updateThemeToggleIcon(theme) {
        const btn = document.getElementById('theme-toggle-btn');
        const icon = document.getElementById('theme-toggle-icon');
        if (!icon) return;

        if (theme === 'light') {
            icon.className = 'fa-solid fa-sun text-lg text-amber-500';
            if (btn) btn.title = '테마: 라이트 모드 (클릭 시 다크 모드로 변경)';
        } else if (theme === 'dark') {
            icon.className = 'fa-solid fa-moon text-lg text-indigo-400';
            if (btn) btn.title = '테마: 다크 모드 (클릭 시 시스템 설정으로 변경)';
        } else { // system
            icon.className = 'fa-solid fa-desktop text-lg text-slate-500 dark:text-slate-400';
            if (btn) btn.title = '테마: 시스템 설정 따름 (클릭 시 라이트 모드로 변경)';
        }
    }

    // OS 시스템 테마 변경 실시간 감지
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        const currentTheme = window.userSettings?.theme || localStorage.theme || 'system';
        if (currentTheme === 'system') {
            if (e.matches) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }
    });

    // 테마 토글 버튼용 함수 노출 (light -> dark -> system 3단계 순환)
    window.toggleTheme = function() {
        const currentTheme = window.userSettings?.theme || localStorage.theme || 'system';
        let nextTheme = 'light';
        if (currentTheme === 'light') {
            nextTheme = 'dark';
        } else if (currentTheme === 'dark') {
            nextTheme = 'system';
        } else {
            nextTheme = 'light';
        }
        window.saveUserSettings({ theme: nextTheme });
    };

})();
