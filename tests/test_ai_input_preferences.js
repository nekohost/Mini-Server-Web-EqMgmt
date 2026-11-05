/* [MINI-COMMENT: USER.PREFERENCES.KEYBOARD.BROWSER] [EN rev.3]
 * [Role] Drives both Enter modes in actual candidate DOM with native Chromium key input and synthetic IME edge orders.
 * [Dependencies] The reviewed in-memory chat transport, candidate settings/client assets and the private keyboard CDP capture.
 * [Impact] Verifies single acceptance, pending navigation/lifecycle guards, disabled/active-job guards and later-draft preservation without real accounts, model calls or production writes.
 */
function runAiInputPreferenceFixture(server, cid, modelId, sleep, theme) {
    'use strict';
    window.userSettings = { ai_enter_action: 'send' };
    let sawEarlySavedMode = false;
    const earlyMode = new MutationObserver(() => {
        if (document.getElementById('ai-input-shortcut')?.textContent === 'Enter 보내기 · Shift+Enter 줄바꿈') sawEarlySavedMode = true;
    });
    earlyMode.observe(document.getElementById('ai-form'), { childList: true, subtree: true, characterData: true });
    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id);
        const wait = async (test, label = 'condition') => { for (let index = 0; index < 1200; index++) { if (test()) return; await sleep(10); } throw Error(label + ' timed out'); };
        const assert = (value, label) => { if (!value) throw Error(label); checks.push(label); };
        let nativeSequence = 0, nativeObserved = null, attemptedTurns = 0, holdTurn = null, releaseTurn = null, releaseCompletion = null;
        let holdCreation = null, releaseCreation = null, attemptedCreations = 0;
        const originalFetch = server.fetch.bind(server);
        server.fetch = async (path, options = {}) => {
            if ((options.method || 'GET') === 'POST' && new URL(path, location.origin).pathname === '/api/ai/conversations') {
                attemptedCreations++;
                if (holdCreation) { const pending = holdCreation; holdCreation = null; await pending; }
            }
            if ((options.method || 'GET') === 'POST' && /\/turns$/.test(new URL(path, location.origin).pathname)) {
                attemptedTurns++;
                if (holdTurn) { const pending = holdTurn; holdTurn = null; await pending; }
            }
            return originalFetch(path, options);
        };
        const key = options => {
            const event = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true, ...options });
            $('ai-input').dispatchEvent(event); return event;
        };
        const mode = action => { window.userSettings = { ...window.userSettings, ai_enter_action: action }; window.applyRoadmapSettings(window.userSettings); };
        const draft = text => { $('ai-input').value = text; $('ai-input').dispatchEvent(new Event('input', { bubbles: true })); $('ai-input').focus(); };
        const nativeEnter = async shift => {
            nativeObserved = null; $('ai-input').focus();
            const id = ++nativeSequence; window.parent.__aiInputKeyRequest = { id, shift: Boolean(shift) };
            await wait(() => window.parent.__aiInputKeyDone === id, 'native Enter delivery');
            assert(nativeObserved?.isTrusted && nativeObserved.shiftKey === Boolean(shift), 'native-' + id + '-key-is-trusted');
        };
        const holdAcceptance = () => { holdTurn = new Promise(resolve => { releaseTurn = resolve; }); };
        const holdCompletion = () => { server.holdStreamCompletion = new Promise(resolve => { releaseCompletion = resolve; }); };
        const finish = async () => {
            $('ai-send').disabled = true;
            server.holdStreamCompletion = false; releaseCompletion?.(); releaseCompletion = null;
            await wait(() => server.polls >= 3 && !$('ai-send').disabled && !$('ai-model').disabled, 'completed job unlock');
        };
        try {
            await wait(() => window.module.exports.bindInputShortcuts && !$('ai-send').disabled && !$('ai-model').disabled && $('equipment-ai').getAttribute('aria-busy') === 'false', 'candidate ready');
            $('ai-input').addEventListener('keydown', event => { if (event.isTrusted) nativeObserved = { isTrusted: true, shiftKey: event.shiftKey }; });
            assert(sawEarlySavedMode, 'saved-mode-before-settings-event-restored-on-initialize');
            earlyMode.disconnect();
            window.applyRoadmapSettings({});
            assert($('ai-input-shortcut').textContent === 'Enter 줄바꿈 · Shift+Enter 보내기', 'absent-or-failed-settings-default-to-newline');
            assert($('ai-input').getAttribute('aria-describedby').split(/\s+/).includes('ai-input-shortcut'), 'accessible-hint-associated-with-input');
            draft('첫 줄'); await nativeEnter(false);
            assert($('ai-input').value === '첫 줄\n' && attemptedTurns === 0, 'default-native-enter-inserts-newline-without-request');

            holdAcceptance(); holdCompletion();
            const submitted = '기본 설정으로 전송'; draft(submitted); await nativeEnter(true);
            await wait(() => attemptedTurns === 1, 'first acceptance pending');
            assert($('ai-send').disabled, 'pending-submit-disables-send');
            draft('접수 중에 입력한 다음 초안');
            const conversationCount = server.conversations.size;
            $('ai-more-conversations').click();
            await wait(() => $('ai-conversations').querySelectorAll('.ai-conversation').length >= 2, 'pending history page');
            const otherHistory = [...$('ai-conversations').querySelectorAll('.ai-conversation')].find(button => button.dataset.conversationId !== cid);
            assert(otherHistory.disabled && $('ai-trash-current').disabled && $('ai-rename-current').disabled && $('ai-trash-tab').disabled && $('ai-new').disabled && !$('ai-input').disabled, 'pending-navigation-locked-while-next-draft-editable');
            otherHistory.disabled = false; otherHistory.click();
            for (const id of ['ai-trash-current', 'ai-rename-current', 'ai-trash-tab', 'ai-new']) { $(id).disabled = false; $(id).click(); }
            const otherTrash = otherHistory.closest('.ai-conversation-row').querySelector('[data-lifecycle-action]');
            otherTrash.disabled = false; otherTrash.click();
            await sleep(30);
            assert(!$('ai-lifecycle-dialog').open && !$('ai-rename-dialog').open && $('ai-active-tab').getAttribute('aria-pressed') === 'true' && $('ai-conversations').querySelector('.ai-conversation[aria-current="true"]').dataset.conversationId === cid && server.conversations.size === conversationCount && !server.requests.some(entry => entry.method === 'POST' && /\/(?:trash|restore|purge)$/.test(entry.path)), 'forced-enabled-history-and-lifecycle-actions-cannot-redirect-pending-turn');
            $('ai-model-refresh').click(); await wait(() => !$('ai-model-refresh').disabled, 'pending model refresh');
            assert($('ai-send').disabled, 'model-refresh-keeps-submit-latch');
            $('ai-send').disabled = false; key({ shiftKey: true }); $('ai-form').requestSubmit();
            assert(attemptedTurns === 1 && $('ai-input').value === '접수 중에 입력한 다음 초안', 'pending-shortcut-and-form-submit-remain-single');
            releaseTurn(); releaseTurn = null;
            await wait(() => server.sent === 1 && server.polls >= 2, 'accepted active request');
            assert($('ai-input').value === '접수 중에 입력한 다음 초안', 'accepted-snapshot-preserves-later-draft');
            assert(server.requests.find(entry => entry.path.endsWith('/turns')).data.content === submitted, 'request-uses-original-submitted-snapshot');
            assert(server.requests.find(entry => entry.path.endsWith('/turns')).path === '/api/ai/conversations/' + cid + '/turns' && $('ai-conversations').querySelector('.ai-conversation[aria-current="true"]').dataset.conversationId === cid, 'accepted-turn-reloads-original-conversation');
            mode('send');
            assert($('ai-input-shortcut').textContent === 'Enter 보내기 · Shift+Enter 줄바꿈' && $('ai-input').value === '접수 중에 입력한 다음 초안', 'settings-update-changes-hint-without-changing-draft');
            $('ai-send').disabled = false; await nativeEnter(false); $('ai-form').requestSubmit();
            assert(attemptedTurns === 1 && $('ai-input').value === '접수 중에 입력한 다음 초안', 'active-job-guards-survive-stale-button-state');
            await finish();

            draft('전송 설정의 첫 줄'); await nativeEnter(true);
            assert($('ai-input').value === '전송 설정의 첫 줄\n' && attemptedTurns === 1, 'send-mode-native-shift-enter-inserts-newline');
            for (const action of ['newline', 'send']) {
                mode(action); const shiftKey = action === 'newline'; draft('한글 조합 중인 초안');
                const before = attemptedTurns;
                assert(!key({ shiftKey, isComposing: true }).defaultPrevented && attemptedTurns === before, action + '-isComposing-enter-never-sends');
                $('ai-input').dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true, data: '한' }));
                assert(!key({ shiftKey }).defaultPrevented && attemptedTurns === before, action + '-tracked-composition-enter-never-sends');
                $('ai-input').dispatchEvent(new CompositionEvent('compositionend', { bubbles: true, data: '한' }));
                assert(!key({ shiftKey }).defaultPrevented && attemptedTurns === before, action + '-compositionend-before-keydown-never-sends');
                $('ai-input').dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
                assert(!key({ shiftKey, keyCode: 229 }).defaultPrevented && attemptedTurns === before, action + '-legacy-ime-keycode-never-sends');
                for (const modifier of ['ctrlKey', 'altKey', 'metaKey']) assert(!key({ shiftKey, [modifier]: true }).defaultPrevented && attemptedTurns === before, action + '-' + modifier + '-is-not-intercepted');
                assert(key({ shiftKey, repeat: true }).defaultPrevented && attemptedTurns === before, action + '-held-enter-never-sends');
                $('ai-send').disabled = true;
                assert(key({ shiftKey }).defaultPrevented && attemptedTurns === before, action + '-disabled-send-shortcut-keeps-draft');
                $('ai-send').disabled = false; $('ai-input').disabled = true;
                key({ shiftKey }); $('ai-form').requestSubmit();
                assert(attemptedTurns === before, action + '-disabled-input-cannot-submit');
                $('ai-input').disabled = false;
                assert($('ai-input').value === '한글 조합 중인 초안', action + '-all-blocked-keys-preserve-draft');
            }
            mode('send'); draft('   '); await nativeEnter(false);
            assert(attemptedTurns === 1 && $('ai-input').value === '   ', 'whitespace-shortcut-keeps-draft-without-request');
            server.rejectNextTurn = true; draft('거부 후 보존할 초안'); await nativeEnter(false);
            await wait(() => attemptedTurns === 2 && !$('ai-send').disabled && $('ai-notice').textContent.includes('초안은 유지'), 'rejected request recovered');
            assert($('ai-input').value === '거부 후 보존할 초안', 'rejection-preserves-draft-and-unlocks-send');
            holdCompletion(); draft('Enter 보내기 확인'); await nativeEnter(false);
            await wait(() => attemptedTurns === 3 && server.sent === 2 && server.polls >= 2, 'send-mode acceptance');
            assert($('ai-input').value === '', 'send-mode-native-enter-submits-once-and-clears-submitted-draft');
            await finish();
            const pendingNewDraft = '명시 새 대화 생성 중에 보존할 초안'; draft(pendingNewDraft);
            holdCreation = new Promise(resolve => { releaseCreation = resolve; });
            $('ai-new').click(); await wait(() => attemptedCreations === 1, 'explicit new conversation pending');
            assert($('ai-new').disabled && $('ai-send').disabled && $('ai-model').disabled && $('ai-level').disabled, 'explicit-new-conversation-locks-composer-before-request-yields');
            $('ai-input').disabled = false; $('ai-send').disabled = false;
            await nativeEnter(false); $('ai-form').requestSubmit();
            $('ai-new').disabled = false; $('ai-new').click();
            assert(attemptedTurns === 3 && attemptedCreations === 1 && $('ai-input').value === pendingNewDraft, 'explicit-new-pending-rejects-forced-enabled-keyboard-form-and-duplicate-create');
            releaseCreation(); releaseCreation = null;
            await wait(() => !$('ai-send').disabled && !$('ai-model').disabled && $('ai-conversations').querySelector('.ai-conversation[aria-current="true"]')?.dataset.conversationId === '7'.repeat(32), 'acknowledged explicit new conversation');
            assert($('ai-input').value === pendingNewDraft && attemptedTurns === 3, 'acknowledged-new-conversation-opens-normally-and-preserves-draft');
            assert(document.documentElement.scrollWidth <= innerWidth + 1, 'hint-and-composer-have-no-horizontal-overflow');
            report.textContent = JSON.stringify({ status: 'pass', view: 'input-preferences', checks, width: innerWidth, theme,
                keyboard: 'trusted native Enter/Shift+Enter via private CDP; IME composition event orders are synthetic', attempted_turns: attemptedTurns, accepted_turns: server.sent,
                production_data_used: false, schema_migration_required: false });
        } catch (error) {
            report.textContent = JSON.stringify({ status: 'fail', view: 'input-preferences', checks, width: innerWidth, theme, error: error.message,
                attempted_turns: attemptedTurns, accepted_turns: server.sent, polls: server.polls, send_disabled: $('ai-send')?.disabled, input_disabled: $('ai-input')?.disabled, hint: $('ai-input-shortcut')?.textContent, notice: $('ai-notice')?.textContent, draft: $('ai-input')?.value });
        } finally {
            earlyMode.disconnect(); releaseTurn?.(); releaseCreation?.(); server.holdStreamCompletion = false; releaseCompletion?.();
        }
        if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}

/* [MINI-COMMENT: USER.PREFERENCES.STARTUP.BROWSER] [EN rev.1]
 * [Role] Holds the original initial-history snapshot while the user sends an early native-key turn or chooses another history view.
 * [Dependencies] The same candidate DOM, reviewed synthetic owner transport and private trusted-key bridge.
 * [Impact] A late initial list must not hydrate the old conversation over an acknowledged new one or undo explicit sidebar steering.
 */
function runAiStartupRaceFixture(server, cid, modelId, sleep, theme, scenario) {
    'use strict';
    const originalFetch = server.fetch.bind(server);
    let initialWaiting = false, initialReleased = false, releaseInitial = null, firstList = true;
    const initialGate = new Promise(resolve => { releaseInitial = resolve; });
    server.fetch = async (path, options = {}) => {
        const url = new URL(path, location.origin), method = options.method || 'GET';
        const response = await originalFetch(path, options);
        if (firstList && method === 'GET' && url.pathname === '/api/ai/conversations') {
            firstList = false; initialWaiting = true;
            await initialGate; initialReleased = true;
        }
        return response;
    };
    document.addEventListener('DOMContentLoaded', async () => {
        const checks = [], report = document.createElement('pre'); report.id = 'browser-test-result'; report.hidden = true; document.body.append(report);
        const $ = id => document.getElementById(id);
        const wait = async (test, label) => { for (let index = 0; index < 1200; index++) { if (test()) return; await sleep(10); } throw Error(label + ' timed out'); };
        const assert = (value, label) => { if (!value) throw Error(label); checks.push(label); };
        const messageReads = () => server.requests.filter(entry => entry.method === 'GET' && /\/messages$/.test(entry.path));
        try {
            await wait(() => initialWaiting && !$('ai-send').disabled && !$('ai-model').disabled && window.userSettings?.theme, 'delayed initial history with ready composer');
            assert(messageReads().length === 0, 'initial-history-response-is-held-before-any-auto-open');
            if (scenario === 'early-submit') {
                const submitted = '초기 목록 도착 전에 보낼 질문';
                window.userSettings = { ...window.userSettings, ai_enter_action: 'send' }; window.applyRoadmapSettings(window.userSettings);
                $('ai-input').value = submitted; $('ai-input').dispatchEvent(new Event('input', { bubbles: true })); $('ai-input').focus();
                let trusted = false;
                $('ai-input').addEventListener('keydown', event => { if (event.isTrusted && event.key === 'Enter') trusted = true; });
                window.parent.__aiInputKeyRequest = { id: 1, shift: false };
                await wait(() => window.parent.__aiInputKeyDone === 1, 'early trusted Enter');
                await wait(() => server.sent === 1 && messageReads().some(entry => entry.path.includes('/' + '7'.repeat(32) + '/')), 'early accepted conversation hydration');
                assert(trusted, 'early-submit-uses-trusted-native-enter');
                const turn = server.requests.find(entry => entry.method === 'POST' && entry.path.endsWith('/turns'));
                assert(turn.path === '/api/ai/conversations/' + '7'.repeat(32) + '/turns' && turn.data.content === submitted, 'early-turn-targets-its-newly-created-conversation');
                releaseInitial();
                await wait(() => initialReleased && !$('ai-send').disabled && $('equipment-ai').getAttribute('aria-busy') === 'false', 'late initial history settlement');
                await sleep(100);
                assert(server.sent === 1 && !messageReads().some(entry => entry.path.includes('/' + cid + '/')) && $('ai-conversations').querySelector('.ai-conversation[aria-current="true"]')?.dataset.conversationId === '7'.repeat(32), 'late-initial-history-cannot-replace-accepted-new-conversation');
            } else if (scenario === 'history-view') {
                $('ai-trash-tab').click();
                await wait(() => $('ai-trash-tab').getAttribute('aria-pressed') === 'true' && server.requests.some(entry => entry.path === '/api/ai/conversations' && entry.search.includes('view=trash')), 'explicit trash history steering');
                releaseInitial(); await wait(() => initialReleased, 'late list released after view steering'); await sleep(100);
                assert(messageReads().length === 0 && $('ai-trash-tab').getAttribute('aria-pressed') === 'true' && !$('ai-notice').textContent, 'late-initial-history-respects-explicit-history-view-steering');
                assert(!server.requests.some(entry => entry.method === 'POST'), 'history-steering-creates-no-model-or-business-request');
            } else throw Error('unsupported startup race scenario');
            report.textContent = JSON.stringify({ status: 'pass', view: 'input-preferences-startup', scenario, checks, width: innerWidth, theme,
                keyboard: scenario === 'early-submit' ? 'trusted native Enter via private CDP' : 'programmatic explicit history button', production_data_used: false });
        } catch (error) {
            report.textContent = JSON.stringify({ status: 'fail', view: 'input-preferences-startup', scenario, checks, width: innerWidth, theme, error: error.message,
                initialWaiting, initialReleased, sent: server.sent, messages: messageReads().map(entry => entry.path + entry.search), notice: $('ai-notice')?.textContent });
        } finally { releaseInitial(); }
        if (window.parent !== window) window.parent.postMessage({ fixtureResult: report.textContent }, location.origin);
        window.dispatchEvent(new Event('pagehide'));
    });
}
