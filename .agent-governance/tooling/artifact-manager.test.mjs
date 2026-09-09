import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import YAML from 'yaml';
import {
  DOC_TYPES,
  LOCK_REL_PATH,
  PATH_MAP_REL_PATH,
  getKSTDateString,
  getNextSequence,
  acquireLock,
  planMigration,
  executeMigration,
  validateArchive,
  generateIndex,
  main
} from './artifact-manager.mjs';

test('1. getKSTDateString() returns valid YYYY-MM-DD format', () => {
  const dateStr = getKSTDateString(new Date('2026-09-09T00:00:00Z'));
  assert.match(dateStr, /^\d{4}-\d{2}-\d{2}$/);
});

test('2. getNextSequence() returns 001 for empty directory and increments appropriately', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-test-'));
  try {
    const seq1 = getNextSequence(tempDir, 'plan', '2026-09-09');
    assert.equal(seq1, '001');

    const targetDir = path.join(tempDir, 'Plans', '2026', '09', '09');
    fs.mkdirSync(targetDir, { recursive: true });
    fs.writeFileSync(path.join(targetDir, '001_Test_Plan.md'), '# Test', 'utf8');

    const seq2 = getNextSequence(tempDir, 'plan', '2026-09-09');
    assert.equal(seq2, '002');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('3. acquireLock() creates and releases lock file properly', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-lock-test-'));
  try {
    const release = acquireLock(tempDir, 1000);
    const lockFile = path.join(tempDir, LOCK_REL_PATH);
    assert.equal(fs.existsSync(lockFile), true);
    release();
    assert.equal(fs.existsSync(lockFile), false);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('4. acquireLock() automatically recovers from stale lock with dead PID', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-stale-lock-'));
  try {
    const lockFile = path.join(tempDir, LOCK_REL_PATH);
    fs.mkdirSync(path.dirname(lockFile), { recursive: true });
    // 존재하지 않는 가상의 PID (99999999) 기록
    fs.writeFileSync(lockFile, JSON.stringify({ pid: 99999999, time: Date.now() - 60000 }));

    // stale lock 상태에서 acquireLock 호출 시 자가 치유 후 잠금 획득해야 함
    const release = acquireLock(tempDir, 2000);
    assert.equal(fs.existsSync(lockFile), true);
    const data = JSON.parse(fs.readFileSync(lockFile, 'utf8'));
    assert.equal(data.pid, process.pid);
    release();
    assert.equal(fs.existsSync(lockFile), false);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('5. planMigration() dynamically scans workspace without hardcoding and detects valid destinations', () => {
  const workspaceRoot = process.cwd();
  const plansDir = path.join(workspaceRoot, 'Plans');
  const reportDir = path.join(workspaceRoot, 'Report');

  const pCount = fs.existsSync(plansDir)
    ? fs.readdirSync(plansDir).filter(f => f.endsWith('.md') && f !== 'README.md' && f !== 'index.md').length
    : 0;
  const rCount = fs.existsSync(reportDir)
    ? fs.readdirSync(reportDir).filter(f => f.endsWith('.md') && f !== 'README.md' && f !== 'index.md').length
    : 0;
  const expectedTotal = pCount + rCount;

  const plan = planMigration(workspaceRoot);
  // 고정 수량(92) 검증 대신 실제 동적 스캔 수량과 100% 일치하는지 검증
  assert.equal(plan.length, expectedTotal, `동적 스캔 수량 불일치: 계획 ${plan.length} != 실제 ${expectedTotal}`);
  assert.equal(plan.conflicts, 0, '실제 운영 트리에 사전 충돌이 없어야 함');

  const destSet = new Set();
  for (const item of plan) {
    assert.equal(destSet.has(item.destination), false, `중복된 목적지 경로: ${item.destination}`);
    destSet.add(item.destination);
    assert.match(item.destination, /^(Plans|Tasks|Reports)\/\d{4}\/\d{2}\/\d{2}\/\d{3}_/);
    assert.ok(['high', 'medium', 'low'].includes(item.confidence), `유효하지 않은 신뢰도: ${item.confidence}`);
    assert.ok(['document_timestamp', 'git_first_added', 'filename_fallback'].includes(item.sortBasis));
  }
});

test('6. planMigration() sorting criteria & confidence levels prioritize document timestamp', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-sort-test-'));
  try {
    const plansDir = path.join(tempDir, 'Plans');
    fs.mkdirSync(plansDir, { recursive: true });

    // 파일 3개 생성: 
    // - A_Plan.md: 본문 시각 14:00 (파일명은 A지만 늦은 시각)
    // - B_Plan.md: 본문 시각 10:00 (파일명은 B지만 빠른 시각)
    // - C_Plan.md: 본문 시각 없음 (파일명 fallback)
    fs.writeFileSync(path.join(plansDir, '2026-09-09_A_Plan.md'), '# Plan A\n\n작성일: 2026-09-09 14:00:00\n');
    fs.writeFileSync(path.join(plansDir, '2026-09-09_B_Plan.md'), '# Plan B\n\n작성일: 2026-09-09 10:00:00\n');
    fs.writeFileSync(path.join(plansDir, '2026-09-09_C_Plan.md'), '# Plan C\n\n(날짜 없음)\n');

    const plan = planMigration(tempDir);
    assert.equal(plan.length, 3);

    // B_Plan(10:00)이 001, A_Plan(14:00)이 002, C_Plan이 003이어야 함
    const bItem = plan.find(p => p.source.includes('B_Plan.md'));
    const aItem = plan.find(p => p.source.includes('A_Plan.md'));
    const cItem = plan.find(p => p.source.includes('C_Plan.md'));

    assert.equal(bItem.seq, '001');
    assert.equal(bItem.confidence, 'high');
    assert.equal(bItem.sortBasis, 'document_timestamp');

    assert.equal(aItem.seq, '002');
    assert.equal(aItem.confidence, 'high');
    assert.equal(aItem.sortBasis, 'document_timestamp');

    assert.equal(cItem.seq, '003');
    assert.equal(cItem.confidence, 'low');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('7. planMigration() correctly detects destination collisions and fail-closed', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-collision-test-'));
  try {
    const plansDir = path.join(tempDir, 'Plans');
    fs.mkdirSync(plansDir, { recursive: true });
    fs.writeFileSync(path.join(plansDir, '2026-09-09_Colliding_Plan.md'), '# Test\n');

    // 목적지 경로에 이미 동일한 파일 생성 (충돌 유도)
    const destDir = path.join(tempDir, 'Plans', '2026', '09', '09');
    fs.mkdirSync(destDir, { recursive: true });
    fs.writeFileSync(path.join(destDir, '001_Colliding_Plan.md'), '# Existing\n');

    const plan = planMigration(tempDir);
    assert.equal(plan.conflicts, 1, '충돌이 정확히 1건 감지되어야 함');
    assert.equal(plan[0].conflict, true);

    // 충돌 상태에서 executeMigration 실행 시 fail-closed 예외 발생 검증
    assert.throws(() => {
      executeMigration(tempDir, plan);
    }, /마이그레이션 중단: 목적지 경로 충돌이 1건 존재합니다/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('8. executeMigration() moves files, creates index and path map with full rollback on failure', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-exec-test-'));
  try {
    const plansDir = path.join(tempDir, 'Plans');
    const reportDir = path.join(tempDir, 'Report');
    fs.mkdirSync(plansDir, { recursive: true });
    fs.mkdirSync(reportDir, { recursive: true });

    fs.writeFileSync(path.join(plansDir, '2026-09-09_Feature_Plan.md'), '# Feature Plan\n작성일: 2026-09-09 10:00:00\n');
    fs.writeFileSync(path.join(reportDir, '2026-09-09_Review_Report.md'), '# Review Report\n검증일: 2026-09-09 11:00:00\n');
    fs.writeFileSync(path.join(tempDir, 'PROPOSALS.md'), 'See Plans/2026-09-09_Feature_Plan.md\n');

    const plan = planMigration(tempDir);
    const result = executeMigration(tempDir, plan);
    assert.equal(result.status, 'success');
    assert.equal(result.totalMigrated, 2);

    // 원본 위치에서 삭제 확인
    assert.equal(fs.existsSync(path.join(plansDir, '2026-09-09_Feature_Plan.md')), false);
    assert.equal(fs.existsSync(path.join(reportDir, '2026-09-09_Review_Report.md')), false);

    // 대상 위치에 생성 확인
    const targetPlan = path.join(tempDir, 'Plans', '2026', '09', '09', '001_Feature_Plan.md');
    const targetReport = path.join(tempDir, 'Reports', '2026', '09', '09', '001_Review_Report.md');
    assert.equal(fs.existsSync(targetPlan), true);
    assert.equal(fs.existsSync(targetReport), true);

    // index.md 생성 확인
    assert.equal(fs.existsSync(path.join(tempDir, 'Plans', '2026', '09', '09', 'index.md')), true);
    assert.equal(fs.existsSync(path.join(tempDir, 'Reports', '2026', '09', '09', 'index.md')), true);

    // path map 파일 검증
    const mapAbs = path.join(tempDir, PATH_MAP_REL_PATH);
    assert.equal(fs.existsSync(mapAbs), true);
    const map = YAML.parse(fs.readFileSync(mapAbs, 'utf8'));
    assert.equal(map.status, 'completed');
    assert.equal(map.records.length, 2);
    assert.equal(map.records[0].sort_basis, 'document_timestamp');
    assert.match(fs.readFileSync(path.join(tempDir, 'PROPOSALS.md'), 'utf8'), /Plans\/2026\/09\/09\/001_Feature_Plan\.md/);

    // --- 롤백 시뮬레이션 ---
    // 새로운 파일 2개 준비 후, 2번째 파일 이동 시 에러가 발생하도록 유도
    const testRollbackDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-rollback-'));
    try {
      const pDir = path.join(testRollbackDir, 'Plans');
      fs.mkdirSync(pDir, { recursive: true });
      const f1 = path.join(pDir, '2026-09-09_Roll1_Plan.md');
      const f2 = path.join(pDir, '2026-09-09_Roll2_Plan.md');
      fs.writeFileSync(f1, 'Content 1');
      fs.writeFileSync(f2, 'Content 2');

      const rPlan = [
        {
          source: 'Plans/2026-09-09_Roll1_Plan.md',
          destination: 'Plans/2026/09/09/001_Roll1_Plan.md',
          type: 'plan',
          date: '2026-09-09'
        },
        {
          source: 'Plans/2026-09-09_Roll2_Plan.md',
          // 고의로 디렉터리가 될 수 없는 경로(파일을 디렉터리로 덮어쓰기 유도 등) 설정
          destination: 'Plans/2026/09/09/invalid_dir/002_Roll2_Plan.md',
          type: 'plan',
          date: '2026-09-09'
        }
      ];
      rPlan.conflicts = 0;

      // invalid_dir 위치에 일반 파일을 만들어 mkdirSync를 실패하게 만듦
      const conflictFile = path.join(testRollbackDir, 'Plans', '2026', '09', '09', 'invalid_dir');
      fs.mkdirSync(path.dirname(conflictFile), { recursive: true });
      fs.writeFileSync(conflictFile, 'I am a file, cannot become a directory');

      // 마이그레이션 실행 -> 2번째 파일에서 오류 발생 -> 1번째 파일 롤백 검증
      assert.throws(() => {
        executeMigration(testRollbackDir, rPlan);
      }, /마이그레이션 실패로 전체 롤백 수행/);

      // 롤백 결과 f1, f2 모두 원래 위치에 온전히 복원되어 있어야 함
      assert.equal(fs.existsSync(f1), true, '첫 번째 파일이 원래 위치로 롤백되어야 함');
      assert.equal(fs.readFileSync(f1, 'utf8'), 'Content 1');
      assert.equal(fs.existsSync(f2), true, '두 번째 파일이 원래 위치에 보존되어야 함');
      assert.equal(fs.existsSync(path.join(testRollbackDir, 'Plans/2026/09/09/001_Roll1_Plan.md')), false, '목적지 파일은 정리되어야 함');

      const lateFailureSource = path.join(pDir, '2026-09-09_LateFailure_Plan.md');
      fs.writeFileSync(lateFailureSource, 'Late failure');
      const previousMap = 'schema_version: 1\nstatus: previous\n';
      const priorMapPath = path.join(testRollbackDir, PATH_MAP_REL_PATH);
      fs.mkdirSync(path.dirname(priorMapPath), { recursive: true });
      fs.writeFileSync(priorMapPath, previousMap);
      const latePlan = [{ source: 'Plans/2026-09-09_LateFailure_Plan.md', destination: 'Plans/2026/09/09/003_LateFailure_Plan.md', type: 'unknown', date: '2026-09-09', seq: '003' }];
      latePlan.conflicts = 0;
      assert.throws(() => executeMigration(testRollbackDir, latePlan), /전체 롤백/);
      assert.equal(fs.existsSync(lateFailureSource), true);
      assert.equal(fs.readFileSync(priorMapPath, 'utf8'), previousMap);
    } finally {
      fs.rmSync(testRollbackDir, { recursive: true, force: true });
    }

  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('9. validateArchive() verifies sequence duplicates, artifact_id duplicates, and broken links', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-val-test-'));
  try {
    const plansDir = path.join(tempDir, 'Plans', '2026', '09', '09');
    fs.mkdirSync(plansDir, { recursive: true });

    // 정상 상태 검증
    const frontMatter = (id, related = []) => `---\nartifact_id: ${id}\nwork_id: WORK-001\ncreated_at: 2026-09-09T10:00:00.000+09:00\n${related.length ? `related_artifacts:\n${related.map(link => `  - ${link}\n`).join('')}` : 'related_artifacts: []\n'}---\n# Title\n`;
    fs.writeFileSync(path.join(plansDir, '001_Normal_Plan.md'), frontMatter('ART-001'));
    let res = validateArchive(tempDir);
    assert.equal(res.valid, true);
    assert.equal(res.errorsCount, 0);

    // 1. 순번 중복 에러 유발 (동일 날짜 폴더에 001_ 중복)
    fs.writeFileSync(path.join(plansDir, '001_Dupe_Plan.md'), frontMatter('ART-002'));
    res = validateArchive(tempDir);
    assert.equal(res.valid, false);
    assert.ok(res.errors.some(e => e.includes('순번 중복 감지')));
    fs.unlinkSync(path.join(plansDir, '001_Dupe_Plan.md'));

    // 2. artifact_id 중복 에러 유발
    fs.writeFileSync(path.join(plansDir, '002_DupeId_Plan.md'), frontMatter('ART-001'));
    res = validateArchive(tempDir);
    assert.equal(res.valid, false);
    assert.ok(res.errors.some(e => e.includes('artifact_id 중복: ART-001')));
    fs.unlinkSync(path.join(plansDir, '002_DupeId_Plan.md'));

    // 3. 깨진 상대 링크 에러 유발
    fs.writeFileSync(path.join(plansDir, '002_BrokenLink_Plan.md'), frontMatter('ART-002', ['./missing_file.md']));
    res = validateArchive(tempDir);
    assert.equal(res.valid, false);
    assert.ok(res.errors.some(e => e.includes('깨진 관련 문서 링크')));

    fs.unlinkSync(path.join(plansDir, '002_BrokenLink_Plan.md'));
    const invalidDateDir = path.join(tempDir, 'Tasks', '2026', '02', '31');
    fs.mkdirSync(invalidDateDir, { recursive: true });
    fs.writeFileSync(path.join(invalidDateDir, '001_Wrong_Plan.md'), frontMatter('ART-003'));
    res = validateArchive(tempDir);
    assert.ok(res.errors.some(e => e.includes('비정상적인 날짜')));
    assert.ok(res.errors.some(e => e.includes('접미사 불일치')));
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('10. next with --touch allocates atomic placeholder and increments on successive calls', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-touch-test-'));
  try {
    const code1 = await main(['next', '--type', 'task', '--date', '2026-09-09', '--workspace', tempDir, '--touch', 'FirstTask']);
    assert.equal(code1, 0);
    const file1 = path.join(tempDir, 'Tasks', '2026', '09', '09', '001_FirstTask_Task.md');
    assert.equal(fs.existsSync(file1), true);
    const firstContent = fs.readFileSync(file1, 'utf8');
    assert.match(firstContent, /artifact_id: TASK-20260909-001/);
    assert.match(firstContent, /work_id: WORK-20260909-001/);
    assert.match(firstContent, /created_at: 2026-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+09:00/);

    const code2 = await main(['next', '--type', 'task', '--date', '2026-09-09', '--workspace', tempDir, '--touch', 'SecondTask']);
    assert.equal(code2, 0);
    const file2 = path.join(tempDir, 'Tasks', '2026', '09', '09', '002_SecondTask_Task.md');
    assert.equal(fs.existsSync(file2), true);
    await assert.rejects(() => main(['next', '--type', 'task', '--date', '2026-02-31', '--workspace', tempDir, '--touch', 'Bad']), /존재하지 않는 날짜/);
    await assert.rejects(() => main(['next', '--type', 'task', '--date', '2026-09-09', '--workspace', tempDir, '--touch', '../escape']), /안전하지 않은 문서 제목/);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('11. generateIndex() creates chronological index sorted by actual document creation timestamp', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-idx-test-'));
  try {
    const targetDir = path.join(tempDir, 'Plans', '2026', '09', '09');
    fs.mkdirSync(targetDir, { recursive: true });

    // 001번 파일은 14:00 작성, 002번 파일은 10:00 작성
    fs.writeFileSync(path.join(targetDir, '001_Afternoon_Plan.md'), '---\nwork_id: W-001\ncreated_at: 2026-09-09 14:00:00\n---\n# Afternoon Plan\n');
    fs.writeFileSync(path.join(targetDir, '002_Morning_Plan.md'), '---\nwork_id: W-002\ncreated_at: 2026-09-09 10:00:00\n---\n# Morning Plan\n');

    generateIndex(tempDir, 'plan', '2026-09-09');
    const idxContent = fs.readFileSync(path.join(targetDir, 'index.md'), 'utf8');

    // Morning Plan(10:00)이 Afternoon Plan(14:00)보다 먼저 나와야 함
    const morningIdx = idxContent.indexOf('Morning Plan');
    const afternoonIdx = idxContent.indexOf('Afternoon Plan');
    assert.ok(morningIdx < afternoonIdx, '실제 작성 시각 순서대로 인덱스가 정렬되어야 함');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});

test('12. index CLI creates the requested index and unknown commands return failure', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'artifact-mgr-index-cli-test-'));
  try {
    const targetDir = path.join(tempDir, 'Reports', '2026', '09', '09');
    fs.mkdirSync(targetDir, { recursive: true });
    fs.writeFileSync(path.join(targetDir, '001_Result_Report.md'), '# Result\n', 'utf8');

    const code = await main(['index', '--type', 'report', '--date', '2026-09-09', '--workspace', tempDir]);
    assert.equal(code, 0);
    assert.equal(fs.existsSync(path.join(targetDir, 'index.md')), true);
    assert.equal(await main(['unknown-command', '--workspace', tempDir]), 1);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
