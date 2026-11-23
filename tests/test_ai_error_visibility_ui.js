'use strict';

/** [Role] Pure Node unit tests for formatJobFailure() and mailStatus() regression invariants.
 * [Dependencies] Node built-in test runner/assert and ../static/js/equipment_ai.js exports only.
 * [Impact] Verifies error code sanitization, recovery guidance separation, and non-mail mailStatus safety without DOM or Flask.
 */
const assert = require('node:assert/strict');
const test = require('node:test');
const { mailStatus, formatJobFailure } = require('../static/js/equipment_ai.js');

test('mailStatus preserves empty output for non-mail failed jobs and status text for mail jobs', () => {
    assert.equal(mailStatus({ state: 'failed', source: {} }), '');
    assert.equal(mailStatus({ state: 'failed', error_code: 'CONTEXT_LIMIT', error: '입력 한도 초과', source: {} }), '');
    assert.equal(mailStatus(null), '');
    assert.equal(mailStatus({ state: 'failed', source: { mail_translation: 'en-ko' }, error: '중단 사유' }), ' · 번역 미완료 · 중단 사유');
    assert.equal(mailStatus({ state: 'done', source: { mail_translation: 'en-ko' } }), ' · 메일 번역');
});

test('formatJobFailure returns null for non-failure and invalid job inputs', () => {
    for (const value of [null, undefined, {}, 'failed', { state: 'done' }, { state: 'running' }, { state: 'queued' }, { state: 'waiting_confirmation' }]) {
        assert.equal(formatJobFailure(value), null);
    }
});

test('formatJobFailure preserves non-recovery failed causes and error codes', () => {
    assert.deepEqual(
        formatJobFailure({ state: 'failed', error_code: 'CONTEXT_LIMIT', error: '  입력 길이가 모델의 최대 컨텍스트 한도를 초과했습니다.  ' }),
        {
            state: 'failed',
            heading: '작업 중단됨',
            detail: '입력 길이가 모델의 최대 컨텍스트 한도를 초과했습니다.',
            recoveredText: '',
            code: 'CONTEXT_LIMIT',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'failed', error_code: 'PROCESSING_FAILED', error: '   ' }),
        {
            state: 'failed',
            heading: '작업 중단됨',
            detail: '응답을 완료하지 못했습니다.',
            recoveredText: '',
            code: 'PROCESSING_FAILED',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'failed', error_code: 'WEB_SEARCH_BLOCKED', error: '웹 검색 정책으로 인해 요청이 차단되었습니다.' }),
        {
            state: 'failed',
            heading: '작업 중단됨',
            detail: '웹 검색 정책으로 인해 요청이 차단되었습니다.',
            recoveredText: '',
            code: 'WEB_SEARCH_BLOCKED',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'failed' }),
        {
            state: 'failed',
            heading: '작업 중단됨',
            detail: '응답을 완료하지 못했습니다.',
            recoveredText: '',
            code: '',
            confirmedIncomplete: false,
        }
    );
});

test('formatJobFailure marks confirmed-incomplete stream/connection failures and replaces obsolete recovery instruction', () => {
    for (const code of ['STREAM_INCOMPLETE', 'CONNECTION_TIMEOUT', 'CONNECTION_FAILED']) {
        assert.deepEqual(
            formatJobFailure({
                state: 'failed',
                error_code: code,
                error: 'AI 응답 연결이 끝까지 확인되지 않아 작업을 중단했습니다. 이전 요청의 종료 확인이 필요합니다.',
            }),
            {
                state: 'failed',
                heading: '작업 중단됨',
                detail: 'AI 응답 연결이 끝까지 확인되지 않아 작업을 중단했습니다.',
                recoveredText: '이전 요청의 종료가 확인되었습니다. 이 대화에서 새 요청을 보낼 수 있습니다.',
                code,
                confirmedIncomplete: true,
            }
        );
        assert.deepEqual(
            formatJobFailure({ state: 'failed', error_code: code, error: '' }),
            {
                state: 'failed',
                heading: '작업 중단됨',
                detail: '응답을 완료하지 못했습니다.',
                recoveredText: '이전 요청의 종료가 확인되었습니다. 이 대화에서 새 요청을 보낼 수 있습니다.',
                code,
                confirmedIncomplete: true,
            }
        );
    }
});

test('formatJobFailure keeps recovery_required and draining states locked without confirmedIncomplete', () => {
    assert.deepEqual(
        formatJobFailure({
            state: 'recovery_required',
            error_code: 'STREAM_INCOMPLETE',
            error: 'AI 응답 연결이 끝까지 확인되지 않아 작업을 중단했습니다. 이전 요청의 종료 확인이 필요합니다.',
        }),
        {
            state: 'recovery_required',
            heading: '작업 중단됨 · 종료 확인 필요',
            detail: 'AI 응답 연결이 끝까지 확인되지 않아 작업을 중단했습니다. 이전 요청의 종료 확인이 필요합니다.',
            recoveredText: '',
            code: 'STREAM_INCOMPLETE',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'recovery_required' }),
        {
            state: 'recovery_required',
            heading: '작업 중단됨 · 종료 확인 필요',
            detail: '이 요청의 종료 확인이 필요합니다. 관리자에게 문의해 주세요.',
            recoveredText: '',
            code: '',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'draining', error_code: 'CONNECTION_TIMEOUT', error: '연결 타임아웃으로 종료를 확인하고 있습니다.' }),
        {
            state: 'draining',
            heading: '작업 중단됨 · 응답 종료 확인 중',
            detail: '연결 타임아웃으로 종료를 확인하고 있습니다.',
            recoveredText: '',
            code: 'CONNECTION_TIMEOUT',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'draining' }),
        {
            state: 'draining',
            heading: '작업 중단됨 · 응답 종료 확인 중',
            detail: '이 요청의 응답 종료를 확인하고 있습니다.',
            recoveredText: '',
            code: '',
            confirmedIncomplete: false,
        }
    );
});

test('formatJobFailure handles cancelled state with and without explicit error text', () => {
    assert.deepEqual(
        formatJobFailure({ state: 'cancelled' }),
        {
            state: 'cancelled',
            heading: '작업 취소됨',
            detail: '사용자의 요청으로 작업을 중단했습니다. 이미 적용된 결과는 유지됩니다.',
            recoveredText: '',
            code: '',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'cancelled', error: '사용자의 요청으로 작업을 중단했습니다. 이미 적용된 결과는 유지됩니다.' }),
        {
            state: 'cancelled',
            heading: '작업 취소됨',
            detail: '사용자의 요청으로 작업을 중단했습니다. 이미 적용된 결과는 유지됩니다.',
            recoveredText: '',
            code: '',
            confirmedIncomplete: false,
        }
    );
    assert.deepEqual(
        formatJobFailure({ state: 'cancelled', error: '대화를 휴지통으로 이동하여 작업을 중단했습니다.', error_code: 'USER_CANCELLED' }),
        {
            state: 'cancelled',
            heading: '작업 취소됨',
            detail: '대화를 휴지통으로 이동하여 작업을 중단했습니다.',
            recoveredText: '',
            code: 'USER_CANCELLED',
            confirmedIncomplete: false,
        }
    );
});

test('formatJobFailure sanitizes invalid or XSS-like error_code values while keeping detail as plain text', () => {
    for (const badCode of ['<script>alert(1)</script>', 'context_limit', 'A', 'A'.repeat(65), 'ERR CODE', 'ERR-1', 123, null, {}]) {
        const result = formatJobFailure({ state: 'failed', error_code: badCode, error: '<img src=x onerror=alert(1)>' });
        assert.equal(result.code, '', `unexpected accepted code: ${String(badCode)}`);
        assert.equal(result.confirmedIncomplete, false);
        assert.equal(result.detail, '<img src=x onerror=alert(1)>');
    }
    assert.equal(formatJobFailure({ state: 'failed', error_code: 'AB' }).code, 'AB');
    assert.equal(formatJobFailure({ state: 'failed', error_code: 'A1_' + 'B'.repeat(61) }).code, 'A1_' + 'B'.repeat(61));
});
