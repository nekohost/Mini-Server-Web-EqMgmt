import assert from 'node:assert/strict';
import test from 'node:test';
import { processStartMatchesRecord } from './process-identity-candidate.mjs';

test('같은 프로세스 시작 시각은 owner로 인정한다', () => {
  assert.equal(processStartMatchesRecord(
    { processStartedAt: '2026-09-09T10:00:00.000Z', createdAt: '2026-09-09T10:01:00.000Z' },
    '2026-09-09T10:00:00.500Z',
  ), true);
});
test('레코드 이후 시작한 동일 PID 프로세스는 PID 재사용으로 판정한다', () => {
  assert.equal(processStartMatchesRecord(
    { pid: 20216, createdAt: '2026-09-09T10:19:51.344Z' },
    '2026-09-09T10:22:17.368Z',
  ), false);
});

test('프로세스 시작 시각을 확인할 수 없으면 판정을 유보한다', () => {
  assert.equal(processStartMatchesRecord({ pid: 20216 }, null), null);
});
