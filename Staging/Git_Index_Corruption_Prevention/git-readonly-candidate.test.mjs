import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createReadOnlyGitEnvironment,
  validateReadOnlyArguments
} from './git-readonly-candidate.mjs';

const candidatePath = fileURLToPath(new URL('./git-readonly-candidate.mjs', import.meta.url));

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, encoding: 'utf8', windowsHide: true });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result;
}

function sha256(filePath) {
  return createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

test('read-only 환경은 optional lock을 항상 비활성화한다', () => {
  const environment = createReadOnlyGitEnvironment({ GIT_OPTIONAL_LOCKS: '1', SAMPLE: 'kept' });
  assert.equal(environment.GIT_OPTIONAL_LOCKS, '0');
  assert.equal(environment.SAMPLE, 'kept');
});

test('조회 명령만 허용하고 출력 파일·외부 diff 인자는 거부한다', () => {
  assert.deepEqual(validateReadOnlyArguments(['--', 'status', '--short']), ['status', '--short']);
  assert.throws(() => validateReadOnlyArguments(['add', '.']), /허용되지 않은/);
  assert.throws(() => validateReadOnlyArguments(['diff', '--output=result.patch']), /허용되지 않은 인자/);
  assert.throws(() => validateReadOnlyArguments(['diff', '--ext-diff']), /허용되지 않은 인자/);
});

test('임시 저장소의 status probe는 index 바이트와 mtime을 변경하지 않는다', () => {
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'git-readonly-candidate-'));
  try {
    run('git', ['init', '--quiet'], workspace);
    run('git', ['config', 'user.name', 'Governance Test'], workspace);
    run('git', ['config', 'user.email', 'governance@example.invalid'], workspace);
    fs.writeFileSync(path.join(workspace, 'tracked.txt'), 'base\n', 'utf8');
    run('git', ['add', 'tracked.txt'], workspace);
    run('git', ['commit', '--quiet', '-m', 'fixture'], workspace);
    fs.writeFileSync(path.join(workspace, 'tracked.txt'), 'changed\n', 'utf8');

    const indexPath = path.join(workspace, '.git', 'index');
    const before = fs.statSync(indexPath);
    const beforeHash = sha256(indexPath);
    const result = spawnSync(process.execPath, [candidatePath, '--', 'status', '--short'], {
      cwd: workspace,
      encoding: 'utf8',
      windowsHide: true
    });
    assert.equal(result.status, 0, result.stderr || result.stdout);

    const after = fs.statSync(indexPath);
    assert.equal(sha256(indexPath), beforeHash);
    assert.equal(after.size, before.size);
    assert.equal(after.mtimeMs, before.mtimeMs);
    assert.match(result.stdout, /tracked\.txt/);
  } finally {
    fs.rmSync(workspace, { recursive: true, force: true });
  }
});
