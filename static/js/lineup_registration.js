/*
 * [역할] 장비등록 카탈로그 선택기 안에서 루트 또는 하위 노드를 추가합니다.
 * [의존성 관계] /api/lineup_node, window.getCSRFToken, 기존 nodeCache_v2 갱신 callback.
 * [변경 시 영향도] 빈 트리와 선택된 노드 다음 단계의 신규 노드 요청 UX에 영향을 줍니다.
 */
(function attachLineupRegistrationFactory(global) {
    'use strict';

    function createElement(tagName, className, text) {
        /* [역할] 사용자 입력을 HTML로 해석하지 않는 안전한 DOM 요소를 생성합니다. */
        const element = document.createElement(tagName);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    global.createLineupNodeRegistration = function createLineupNodeRegistration(options) {
        /*
         * [역할] 기존 LineupApp이 주입한 캐시 갱신·선택 callback과 노드 생성 UI를 결합합니다.
         * [의존성 관계] options.onApproved/onPending/onError와 CSRF helper를 사용합니다.
         * [변경 시 영향도] 생성 성공 후 즉시 선택 또는 승인 대기 안내 흐름에 영향을 줍니다.
         */
        const config = Object.assign({ endpoint: '/api/lineup_node', maxNameLength: 100 }, options || {});
        let requestInFlight = false;

        async function submitNode(payload, controls) {
            /* [역할] 중복 제출을 잠그고 노드 생성 결과의 승인 상태를 분기합니다. */
            if (requestInFlight) return;
            requestInFlight = true;
            if (config.onBusy) config.onBusy(true); // 장비 저장과 노드 생성을 직렬화합니다.
            controls.button.disabled = true;
            controls.message.textContent = '노드를 등록하는 중입니다…';
            controls.message.className = 'mt-2 text-xs text-blue-600 dark:text-blue-300';

            try {
                const response = await fetch(config.endpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': global.getCSRFToken()
                    },
                    body: JSON.stringify(payload)
                });
                const result = await response.json().catch(() => ({}));
                if (!response.ok || !result.success) {
                    throw new Error(result.message || '노드를 등록하지 못했습니다.');
                }

                if (result.status === 'APPROVED') {
                    controls.message.textContent = '노드가 등록되었습니다. 목록을 갱신합니다.';
                    controls.message.className = 'mt-2 text-xs text-emerald-600 dark:text-emerald-300';
                    if (typeof config.onApproved === 'function') await config.onApproved(result, payload);
                } else {
                    controls.message.textContent = '승인 요청이 접수되었습니다. 승인 후 이 노드를 선택할 수 있습니다.';
                    controls.message.className = 'mt-2 text-xs text-amber-600 dark:text-amber-300';
                    controls.input.value = '';
                    if (typeof config.onPending === 'function') config.onPending(result, payload);
                }
            } catch (error) {
                controls.message.textContent = error.message || '서버 통신 중 오류가 발생했습니다.';
                controls.message.className = 'mt-2 text-xs text-red-600 dark:text-red-300';
                if (typeof config.onError === 'function') config.onError(error);
            } finally {
                requestInFlight = false;
                if (config.onBusy) config.onBusy(false); // 성공·실패 모두 저장 잠금을 해제합니다.
                controls.button.disabled = false;
            }
        }

        function mount(container, context) {
            /*
             * [역할] 지정 위치에 루트/하위 노드 이름 입력과 요청 버튼을 렌더링합니다.
             * [의존성 관계] context.categoryId/manufacturerId/parentId/depth를 사용합니다.
             * [변경 시 영향도] 노드가 없는 조합과 각 계층의 추가 진입점 표시에 영향을 줍니다.
             */
            container.replaceChildren();
            const panel = createElement(
                'div',
                'rounded-lg border border-dashed border-blue-300 bg-blue-50/70 p-3 dark:border-blue-700 dark:bg-blue-950/30'
            );
            const title = createElement(
                'p',
                'text-sm font-bold text-blue-900 dark:text-blue-200',
                context.parentId ? `${context.depth}차 하위 노드 추가` : '최상위 라인업 노드 추가'
            );
            const hint = createElement(
                'p',
                'mt-1 text-xs text-slate-600 dark:text-slate-300',
                '관리자는 즉시 사용할 수 있고, 일반 사용자는 승인 후 사용할 수 있습니다.'
            );
            const row = createElement('div', 'mt-3 flex flex-col gap-2 sm:flex-row');
            const input = createElement('input', 'min-w-0 flex-1 rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white');
            input.type = 'text';
            input.maxLength = config.maxNameLength;
            input.placeholder = context.parentId ? '새 하위 노드명' : '새 최상위 모델명';
            const button = createElement('button', 'rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50', '노드 추가');
            button.type = 'button';
            const message = createElement('p', 'mt-2 text-xs text-slate-500 dark:text-slate-400', '');

            button.addEventListener('click', () => {
                const name = input.value.trim();
                if (!name) {
                    message.textContent = '노드 이름을 입력해 주세요.';
                    message.className = 'mt-2 text-xs text-red-600 dark:text-red-300';
                    input.focus();
                    return;
                }
                submitNode(
                    {
                        name,
                        category_id: context.categoryId,
                        manufacturer_id: context.manufacturerId,
                        parent_id: context.parentId || null
                    },
                    { input, button, message }
                );
            });
            input.addEventListener('keydown', event => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    button.click();
                }
            });

            row.append(input, button);
            panel.append(title, hint, row, message);
            container.append(panel);
            return panel;
        }

        return { mount };
    };
})(window);
