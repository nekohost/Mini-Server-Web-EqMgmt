import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import test, { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// Read template file
const templatePath = path.resolve('templates/access_logs.html');
const templateHtml = fs.readFileSync(templatePath, 'utf8');

// Extract script block from template
const scriptMatch = templateHtml.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
    throw new Error('Could not find <script> in templates/access_logs.html');
}
const scriptCode = scriptMatch[1];

/**
 * Creates an isolated mock DOM and runtime harness to execute access_logs.html script in node:vm
 */
function createHarness(mockFetch, options = {}) {
    const alerts = [];
    const elements = new Map();

    function getOrCreateElement(id) {
        if (!elements.has(id)) {
            const classes = new Set();
            let text = '';
            const elem = {
                id,
                value: '',
                innerHTML: '',
                disabled: false,
                get innerText() { return text; },
                set innerText(val) { text = String(val ?? ''); },
                get textContent() { return text; },
                set textContent(val) { text = String(val ?? ''); },
                get className() { return Array.from(classes).join(' '); },
                set className(val) {
                    classes.clear();
                    if (val) {
                        val.split(/\s+/).filter(Boolean).forEach(c => classes.add(c));
                    }
                },
                classList: {
                    add: (...cls) => cls.forEach(c => classes.add(c)),
                    remove: (...cls) => cls.forEach(c => classes.delete(c)),
                    toggle: (c) => classes.has(c) ? classes.delete(c) : classes.add(c),
                    contains: (c) => classes.has(c)
                },
                closest: () => null,
                contains: () => false
            };
            elements.set(id, elem);
        }
        return elements.get(id);
    }

    // Pre-populate elements present in access_logs.html
    const standardIds = [
        'cleanupModal', 'cleanupDropdown', 'cleanupModalTitle', 'cleanupModalDesc',
        'confirmCleanupBtn', 'filterIp', 'filterMethod', 'filterStatus', 'filterPath',
        'autoRefreshSelect', 'countdownBadge', 'statTotalRequests', 'statApiRequests',
        'statStaticRequests', 'statErrorRate', 'statSectionTitle', 'statTotalTitle',
        'btnStatPeriod_today', 'btnStatPeriod_all', 'logsTableBody', 'totalCountBadge',
        'perPageSelect', 'paginationNav', 'qf_all', 'qf_api', 'qf_static', 'payloadModal',
        'modalReqPayload', 'modalResPayload'
    ];
    for (const id of standardIds) {
        getOrCreateElement(id);
    }

    // Modal is hidden initially
    getOrCreateElement('cleanupModal').classList.add('hidden');
    getOrCreateElement('cleanupDropdown').classList.add('hidden');

    const dom = {
        getElementById: (id) => getOrCreateElement(id),
        querySelectorAll: (sel) => {
            if (sel === '.qf-btn') {
                return [getOrCreateElement('qf_all'), getOrCreateElement('qf_api'), getOrCreateElement('qf_static')];
            }
            return [];
        },
        querySelector: () => null,
        addEventListener: () => {}
    };

    const windowObj = {
        getCSRFToken: () => options.csrfToken !== undefined ? options.csrfToken : 'test-csrf-token-abc123',
        showGlobalLoading: () => {},
        hideGlobalLoading: () => {},
        escapeMarkup: (s) => String(s ?? ''),
        location: { search: '' }
    };

    const sandbox = {
        document: dom,
        window: windowObj,
        alert: (msg) => alerts.push(msg),
        console: {
            log: () => {},
            error: () => {},
            warn: () => {}
        },
        fetch: mockFetch,
        URLSearchParams,
        setInterval: () => 1,
        clearInterval: () => {},
        setTimeout: () => 1,
        clearTimeout: () => {},
        Number,
        Math,
        JSON,
        parseInt,
        encodeURIComponent
    };

    const context = vm.createContext(sandbox);
    vm.runInContext(scriptCode, context);

    return {
        context,
        elements,
        getElem: getOrCreateElement,
        alerts,
        get currentPage() { return vm.runInContext('currentPage', context); },
        set currentPage(val) { vm.runInContext(`currentPage = ${val};`, context); },
        get activeCleanupAction() { return vm.runInContext('activeCleanupAction', context); },
        set activeCleanupAction(val) { vm.runInContext(`activeCleanupAction = ${JSON.stringify(val)};`, context); },
        openCleanupModal: (action) => context.openCleanupModal(action),
        closeCleanupModal: () => context.closeCleanupModal(),
        executeCleanup: (targetAction) => context.executeCleanup(targetAction),
        fetchLogs: (silent) => context.fetchLogs(silent),
        fetchStats: () => context.fetchStats()
    };
}

describe('Web Log Cleanup UI & Contract Tests', () => {

    describe('1. UI markup and action distinction in template', () => {
        it('should define all cleanup actions in dropdown including all_including_ai', () => {
            assert.match(templateHtml, /openCleanupModal\('older_30d'\)/);
            assert.match(templateHtml, /openCleanupModal\('static_only'\)/);
            assert.match(templateHtml, /openCleanupModal\('all'\)/);
            assert.match(templateHtml, /openCleanupModal\('all_including_ai'\)/);

            // Labels distinguish ordinary all vs all_including_ai
            assert.match(templateHtml, /일반 웹 접근 로그 삭제\s*\(AI 경로 제외\)/);
            assert.match(templateHtml, /웹 접근 로그 전체 삭제\s*\(AI 경로 포함\)/);
        });

        it('should explain constraints in openCleanupModal dialog without filler', () => {
            const harness = createHarness(async () => ({ ok: true, json: async () => ({}) }));
            const titleEl = harness.getElem('cleanupModalTitle');
            const descEl = harness.getElem('cleanupModalDesc');
            const modalEl = harness.getElem('cleanupModal');

            // 1. ordinary 'all' action
            harness.openCleanupModal('all');
            assert.equal(modalEl.classList.contains('hidden'), false);
            assert.equal(harness.activeCleanupAction, 'all');
            assert.match(titleEl.innerText, /일반 웹 접근 로그 삭제/);
            assert.match(titleEl.innerText, /AI 경로 제외/);
            // Ordinary all excludes AI paths and preserves historic AI HTTP records
            assert.match(descEl.innerText, /AI 경로를 제외한 모든 일반 웹 접근 로그/);
            assert.match(descEl.innerText, /과거 AI HTTP 기록은 보존/);
            // Explains web access records only
            assert.match(descEl.innerText, /웹 접근 기록이 대상/);
            // Explains fixed start boundary and later events survive
            assert.match(descEl.innerText, /정리 시작 시점까지 접수/);
            assert.match(descEl.innerText, /이후 접수된 기록은 목록에 남습니다/);
            // Explains AI conversations & business receipts retained
            assert.match(descEl.innerText, /AI 대화·작업, 장비 변경 및 CSV 반출 영수증/);

            // 2. 'all_including_ai' action
            harness.openCleanupModal('all_including_ai');
            assert.equal(harness.activeCleanupAction, 'all_including_ai');
            assert.match(titleEl.innerText, /웹 접근 로그 전체 삭제/);
            assert.match(titleEl.innerText, /AI 경로 포함/);
            // Explains including historic AI HTTP entries
            assert.match(descEl.innerText, /과거 AI 경로의 HTTP 기록을 포함한 모든 웹 접근 로그/);
            // Explains web access records only, boundary, and retention of conversations/receipts
            assert.match(descEl.innerText, /웹 접근 기록이 대상/);
            assert.match(descEl.innerText, /정리 시작 시점/);
            assert.match(descEl.innerText, /구버전의 미전송 기록은 별도 보관본/);
            assert.match(descEl.innerText, /이후 접수된 기록은 목록에 남습니다/);
            assert.match(descEl.innerText, /AI 대화·작업, 장비 변경 및 CSV 반출 영수증/);

            // 3. 'older_30d' action
            harness.openCleanupModal('older_30d');
            assert.equal(harness.activeCleanupAction, 'older_30d');
            assert.match(descEl.innerText, /AI 경로 제외/);
            assert.match(descEl.innerText, /웹 접근 기록이 대상/);

            // 4. 'static_only' action
            harness.openCleanupModal('static_only');
            assert.equal(harness.activeCleanupAction, 'static_only');
            assert.match(descEl.innerText, /AI 경로 제외/);
            assert.match(descEl.innerText, /정적 리소스/);
        });
    });

    describe('2. Successful cleanup execution for both actions (all vs all_including_ai)', () => {
        it('should execute ordinary all cleanup, validate CSRF, contract steps, preserve filters and reset page to 1', async () => {
            const recordedCalls = [];
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                recordedCalls.push({ url, method: opts.method, headers: opts.headers, body });

                if (url.includes('/api/access_logs/cleanup')) {
                    assert.equal(opts.method, 'POST');
                    assert.equal(opts.headers['X-CSRFToken'], 'test-csrf-token-abc123');

                    if (body.step === 'count') {
                        assert.equal(body.action, 'all');
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                operation_id: 'op-all-456',
                                total_count: 500
                            })
                        };
                    }
                    if (body.step === 'delete_chunk') {
                        assert.equal(body.action, 'all');
                        assert.equal(body.operation_id, 'op-all-456');
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 250
                            })
                        };
                    }
                    if (body.step === 'finish') {
                        assert.equal(body.action, 'all');
                        assert.equal(body.operation_id, 'op-all-456');
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 500,
                                remaining_count: 0
                            })
                        };
                    }
                }

                // Stats and Logs mock endpoints called after successful cleanup
                if (url.includes('/api/access_logs/stats')) {
                    return { ok: true, json: async () => ({ total: 10, api_count: 8, static_count: 2, error_rate: 0 }) };
                }
                if (url.includes('/api/access_logs?')) {
                    return { ok: true, json: async () => ({ total: 10, page: 1, per_page: 50, logs: [] }) };
                }

                throw new Error(`Unexpected request to ${url}`);
            };

            const harness = createHarness(mockFetch);

            // Set up search and filter state on page 3
            harness.currentPage = 3;
            harness.getElem('filterIp').value = '10.0.0.99';
            harness.getElem('filterMethod').value = 'POST';
            harness.getElem('filterStatus').value = '500';
            harness.getElem('filterPath').value = '/auth/login';

            harness.openCleanupModal('all');
            await harness.executeCleanup();

            // Modal closed
            assert.equal(harness.getElem('cleanupModal').classList.contains('hidden'), true);

            // Success alert shown with authoritative deleted count (500)
            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /기준 시점까지 남은 대상은 0건/);
            assert.match(harness.alerts[0], /500건/);

            // Page reset to 1
            assert.equal(harness.currentPage, 1);

            // Filter state preserved
            assert.equal(harness.getElem('filterIp').value, '10.0.0.99');
            assert.equal(harness.getElem('filterMethod').value, 'POST');
            assert.equal(harness.getElem('filterStatus').value, '500');
            assert.equal(harness.getElem('filterPath').value, '/auth/login');

            // Verify calls sequence: count -> 2 chunks -> finish -> fetchStats -> fetchLogs
            const cleanupSteps = recordedCalls.filter(c => c.url.includes('/api/access_logs/cleanup')).map(c => c.body.step);
            assert.deepEqual(cleanupSteps, ['count', 'delete_chunk', 'delete_chunk', 'finish']);

            // Verified fetchStats and fetchLogs were invoked
            assert.ok(recordedCalls.some(c => c.url.includes('/api/access_logs/stats')));
            assert.ok(recordedCalls.some(c => c.url.includes('/api/access_logs?page=1')));
        });

        it('should execute all_including_ai cleanup passing action to all contract steps', async () => {
            const stepsReceived = [];
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    stepsReceived.push(body);
                    if (body.step === 'count') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                operation_id: 'op-ai-789',
                                total_count: 120
                            })
                        };
                    }
                    if (body.step === 'delete_chunk') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 120
                            })
                        };
                    }
                    if (body.step === 'finish') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 120,
                                remaining_count: 0
                            })
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 4;
            harness.openCleanupModal('all_including_ai');
            await harness.executeCleanup();

            assert.equal(stepsReceived.length, 3);
            assert.deepEqual(stepsReceived[0], { action: 'all_including_ai', step: 'count' });
            assert.deepEqual(stepsReceived[1], { action: 'all_including_ai', step: 'delete_chunk', operation_id: 'op-ai-789' });
            assert.deepEqual(stepsReceived[2], { action: 'all_including_ai', step: 'finish', operation_id: 'op-ai-789' });

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /120건/);
            assert.equal(harness.currentPage, 1);
        });
    });

    describe('3. Total zero scenario (count=0 must still call finish)', () => {
        it('should call finish even when total_count is 0 without delete_chunk, and complete successfully', async () => {
            const cleanupSteps = [];
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    cleanupSteps.push(body);
                    if (body.step === 'count') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                operation_id: 'op-zero-001',
                                total_count: 0
                            })
                        };
                    }
                    if (body.step === 'delete_chunk') {
                        throw new Error('delete_chunk should NOT be called when total_count is 0');
                    }
                    if (body.step === 'finish') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 0,
                                remaining_count: 0
                            })
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 2;
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            // Assert count and finish were called, but NOT delete_chunk
            assert.equal(cleanupSteps.length, 2);
            assert.equal(cleanupSteps[0].step, 'count');
            assert.equal(cleanupSteps[1].step, 'finish');
            assert.equal(cleanupSteps[1].operation_id, 'op-zero-001');

            // Success alert showing 0 records
            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /기준 시점까지 남은 대상은 0건/);
            assert.match(harness.alerts[0], /0건/);

            // Successful page reset to 1
            assert.equal(harness.currentPage, 1);
            assert.equal(harness.getElem('cleanupModal').classList.contains('hidden'), true);
        });
    });

    describe('4. Malformed / failed finish responses (show error not success)', () => {
        it('should show error and NOT success when finish returns HTTP 500 error', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-err-1', total_count: 10 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: 10 }) };
                    }
                    if (body.step === 'finish') {
                        return { ok: false, status: 500, json: async () => ({ status: 'error', message: 'Internal Server Error' }) };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 5;
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /HTTP 500/);
            // Page NOT reset to 1 on failure
            assert.equal(harness.currentPage, 5);
        });

        it('should show error and NOT success when finish returns status != success', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-err-2', total_count: 10 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: 10 }) };
                    }
                    if (body.step === 'finish') {
                        return { ok: true, json: async () => ({ status: 'error', message: 'DB lock timeout occurred' }) };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 3;
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /DB lock timeout occurred/);
            assert.equal(harness.currentPage, 3);
        });

        it('should show error when finish reports remaining_count > 0', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-err-3', total_count: 50 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: 45 }) };
                    }
                    if (body.step === 'finish') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 45,
                                remaining_count: 5 // remaining > 0 failure!
                            })
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 2;
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /잔여 로그가 있습니다/);
            assert.match(harness.alerts[0], /5건/);
            assert.equal(harness.currentPage, 2);
        });

        it('should show error when finish returns non-numeric or malformed fields', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-err-4', total_count: 10 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: 10 }) };
                    }
                    if (body.step === 'finish') {
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: 'invalid_string', // non-integer
                                remaining_count: 0
                            })
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.currentPage = 4;
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /deleted_count/);
            assert.equal(harness.currentPage, 4);
        });

        it('should show error when finish response is non-JSON malformed text', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-err-5', total_count: 5 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: 5 }) };
                    }
                    if (body.step === 'finish') {
                        return {
                            ok: true,
                            json: async () => { throw new Error('Unexpected token < in JSON at position 0'); }
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /JSON/);
        });
    });

    describe('5. Start boundary and survival of later events', () => {
        it('should respect fixed start boundary so new records arriving after boundary survive in mock DB', async () => {
            // Simulated server database
            const mockDatabase = [];
            const START_BOUNDARY_TIME = 1000;

            // Seed initial records created before start boundary
            for (let i = 1; i <= 300; i++) {
                mockDatabase.push({ id: i, created_at: START_BOUNDARY_TIME - i, deleted: false });
            }

            let activeOperation = null;

            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        // Start boundary fixed at operation start
                        const opId = 'op-boundary-session-1';
                        activeOperation = {
                            id: opId,
                            boundaryTime: START_BOUNDARY_TIME,
                            targetIds: mockDatabase.filter(r => r.created_at <= START_BOUNDARY_TIME && !r.deleted).map(r => r.id),
                            deletedIds: new Set()
                        };
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                operation_id: opId,
                                total_count: activeOperation.targetIds.length
                            })
                        };
                    }
                    if (body.step === 'delete_chunk') {
                        assert.equal(body.operation_id, activeOperation.id);
                        // Delete chunk from boundary targets only
                        const pending = activeOperation.targetIds.filter(id => !activeOperation.deletedIds.has(id));
                        const chunk = pending.slice(0, 150);
                        for (const id of chunk) {
                            activeOperation.deletedIds.add(id);
                            const record = mockDatabase.find(r => r.id === id);
                            if (record) record.deleted = true;
                        }

                        // SIMULATION: While chunk deletion is underway, 25 new records arrive (later events)
                        if (activeOperation.deletedIds.size === 150) {
                            for (let n = 1; n <= 25; n++) {
                                mockDatabase.push({
                                    id: 1000 + n,
                                    created_at: START_BOUNDARY_TIME + n * 10, // Arrived AFTER boundary!
                                    deleted: false
                                });
                            }
                        }

                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: chunk.length
                            })
                        };
                    }
                    if (body.step === 'finish') {
                        assert.equal(body.operation_id, activeOperation.id);
                        // Remaining count for the boundary target scope
                        const remaining = activeOperation.targetIds.filter(id => !activeOperation.deletedIds.has(id)).length;
                        return {
                            ok: true,
                            json: async () => ({
                                status: 'success',
                                deleted_count: activeOperation.deletedIds.size,
                                remaining_count: remaining
                            })
                        };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            // Assert authoritative deleted count reported was 300
            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /300건/);

            // Assert that records after start boundary survived and remain non-deleted
            const survivingNewRecords = mockDatabase.filter(r => r.created_at > START_BOUNDARY_TIME);
            assert.equal(survivingNewRecords.length, 25, '25 records arrived after start boundary');
            assert.ok(survivingNewRecords.every(r => r.deleted === false), 'All events arriving after start boundary must survive');

            // Assert boundary records were indeed deleted
            const boundaryRecords = mockDatabase.filter(r => r.created_at <= START_BOUNDARY_TIME);
            assert.equal(boundaryRecords.length, 300);
            assert.ok(boundaryRecords.every(r => r.deleted === true), 'All target records within boundary were deleted');
        });
    });

    describe('6. Validation of count and delete_chunk responses', () => {
        it('should show error when count response has empty or invalid operation_id', async () => {
            const mockFetch = async () => ({
                ok: true,
                json: async () => ({
                    status: 'success',
                    operation_id: '   ', // empty string
                    total_count: 10
                })
            });

            const harness = createHarness(mockFetch);
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /operation_id/);
        });

        it('should show error when count response has negative or non-integer total_count', async () => {
            const mockFetch = async () => ({
                ok: true,
                json: async () => ({
                    status: 'success',
                    operation_id: 'op-valid',
                    total_count: -5
                })
            });

            const harness = createHarness(mockFetch);
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /total_count/);
        });

        it('should show error when delete_chunk returns negative or non-numeric deleted_count', async () => {
            const mockFetch = async (url, opts = {}) => {
                const body = opts.body ? JSON.parse(opts.body) : null;
                if (url.includes('/api/access_logs/cleanup')) {
                    if (body.step === 'count') {
                        return { ok: true, json: async () => ({ status: 'success', operation_id: 'op-chunk-err', total_count: 50 }) };
                    }
                    if (body.step === 'delete_chunk') {
                        return { ok: true, json: async () => ({ status: 'success', deleted_count: -1 }) };
                    }
                }
                return { ok: true, json: async () => ({}) };
            };

            const harness = createHarness(mockFetch);
            harness.openCleanupModal('all');
            await harness.executeCleanup();

            assert.equal(harness.alerts.length, 1);
            assert.match(harness.alerts[0], /❌ 정리 실패/);
            assert.match(harness.alerts[0], /deleted_count/);
        });
    });
});
