#!/usr/bin/env node
/**
 * @file artifact-manager.mjs
 * @description Plan·Task·Report 문서 보관 구조(Plans/, Tasks/, Reports/)의 순번 할당, 유효성 검증, 색인 생성 및 원자적 마이그레이션 도구.
 * @license Private
 */

import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import YAML from 'yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const DOC_TYPES = {
  plan: { dir: 'Plans', suffix: 'Plan.md' },
  task: { dir: 'Tasks', suffix: 'Task.md' },
  report: { dir: 'Reports', suffix: 'Report.md' }
};

export const LOCK_REL_PATH = '.agent-governance/.state/artifact-manager.lock';
export const PATH_MAP_REL_PATH = 'docs/artifact-path-map.yaml';

/**
 * KST 기준 오늘 날짜 문자열 YYYY-MM-DD 반환
 */
export function getKSTDateString(date = new Date()) {
  const kstOffset = 9 * 60 * 60 * 1000;
  const kstDate = new Date(date.getTime() + kstOffset);
  const y = kstDate.getUTCFullYear();
  const m = String(kstDate.getUTCMonth() + 1).padStart(2, '0');
  const d = String(kstDate.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function getKSTTimestamp(date = new Date()) {
  const kst = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  const iso = kst.toISOString().replace('Z', '+09:00');
  return iso;
}

export function assertValidDate(dateStr) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    throw new Error(`잘못된 날짜 형식: ${dateStr} (필요 형식: YYYY-MM-DD)`);
  }
  const [year, month, day] = dateStr.split('-').map(Number);
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (candidate.getUTCFullYear() !== year || candidate.getUTCMonth() !== month - 1 || candidate.getUTCDate() !== day) {
    throw new Error(`존재하지 않는 날짜: ${dateStr}`);
  }
  return { year: String(year).padStart(4, '0'), month: String(month).padStart(2, '0'), day: String(day).padStart(2, '0') };
}

function assertInsideWorkspace(workspaceRoot, candidate, label) {
  const root = path.resolve(workspaceRoot);
  const resolved = path.resolve(candidate);
  const relative = path.relative(root, resolved);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error(`워크스페이스 이탈: ${label}`);
  }
  return resolved;
}

function normalizeTitle(title) {
  const normalized = String(title ?? '').trim().replace(/\s+/g, '_');
  if (!normalized || normalized === '.' || normalized === '..' || /[<>:"/\\|?*\x00-\x1F]/.test(normalized) || normalized.includes('..')) {
    throw new Error(`안전하지 않은 문서 제목: ${title}`);
  }
  return normalized;
}

function writeTextAtomic(targetPath, content) {
  fs.mkdirSync(path.dirname(targetPath), { recursive: true });
  const token = `${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const temporary = `${targetPath}.${token}.tmp`;
  const backup = `${targetPath}.${token}.bak`;
  let movedOriginal = false;
  fs.writeFileSync(temporary, content, { encoding: 'utf8', flag: 'wx' });
  try {
    if (fs.existsSync(targetPath)) {
      fs.renameSync(targetPath, backup);
      movedOriginal = true;
    }
    fs.renameSync(temporary, targetPath);
    if (movedOriginal) fs.unlinkSync(backup);
  } catch (error) {
    try { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); } catch {}
    try { if (movedOriginal && fs.existsSync(backup) && !fs.existsSync(targetPath)) fs.renameSync(backup, targetPath); } catch {}
    throw error;
  }
}

function createPathMap(plan, status = 'completed') {
  const pathMap = {
    schema_version: 1,
    status,
    updated_at: new Date().toISOString(),
    total_mappings: plan.length,
    plans_count: plan.filter(p => p.type === 'plan').length,
    tasks_count: plan.filter(p => p.type === 'task').length,
    reports_count: plan.filter(p => p.type === 'report').length,
    mappings: {},
    records: plan.map(item => ({
      source: item.source,
      destination: item.destination,
      type: item.type,
      date: item.date,
      sequence: item.seq,
      document_time: item.docTime,
      sort_basis: item.sortBasis,
      confidence: item.confidence
    }))
  };
  for (const item of plan) pathMap.mappings[item.source] = item.destination;
  return pathMap;
}

/**
 * 프로세스 생존 여부 검사 (Windows & Linux 공통)
 */
function isProcessAlive(pid) {
  if (!pid || typeof pid !== 'number') return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === 'EPERM'; // 권한 거부면 살아있는 프로세스임
  }
}

/**
 * 단순 파일 잠금 획득 (PID 생존 검증 포함)
 */
export function acquireLock(workspaceRoot, timeoutMs = 5000) {
  const lockFile = path.join(workspaceRoot, LOCK_REL_PATH);
  const lockDir = path.dirname(lockFile);
  if (!fs.existsSync(lockDir)) {
    fs.mkdirSync(lockDir, { recursive: true });
  }

  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const fd = fs.openSync(lockFile, 'wx');
      fs.writeFileSync(fd, JSON.stringify({ pid: process.pid, time: Date.now() }));
      fs.closeSync(fd);
      return () => {
        try { fs.unlinkSync(lockFile); } catch {}
      };
    } catch (err) {
      if (err.code === 'EEXIST') {
        // stale lock 확인 (PID 생존 여부 검사)
        try {
          const raw = fs.readFileSync(lockFile, 'utf8');
          const lockData = JSON.parse(raw);
          if (!isProcessAlive(lockData.pid)) {
            // 소유 프로세스가 죽어 있으면 회수
            try { fs.unlinkSync(lockFile); } catch {}
            continue;
          }
        } catch {}

        // 잠시 대기 (busy wait 방지)
        const waitTill = Date.now() + 50;
        while (Date.now() < waitTill) {}
      } else {
        throw err;
      }
    }
  }
  throw new Error(`잠금 획득 실패 (타임아웃 ${timeoutMs}ms): ${lockFile}`);
}

/**
 * Git 최초 추가 commit 시각 조회 (없으면 null)
 */
export function getGitFirstAddedDate(filePath, workspaceRoot) {
  try {
    const rel = path.relative(workspaceRoot, filePath).replace(/\\/g, '/');
    const out = execFileSync('git', ['log', '--diff-filter=A', '--format=%aI', '-1', '--', rel], {
      cwd: workspaceRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore']
    }).trim();
    if (out) return out;
  } catch {}
  return null;
}

/**
 * 특정 일자 폴더 내 기존 파일들의 최대 3자리 순번 조회 후 다음 순번(3자리 문자열) 반환
 */
export function getNextSequence(workspaceRoot, type, dateStr) {
  const typeConfig = DOC_TYPES[type.toLowerCase()];
  if (!typeConfig) {
    throw new Error(`알 수 없는 문서 종류: ${type} (가능한 종류: plan, task, report)`);
  }

  const { year: y, month: m, day: d } = assertValidDate(dateStr);

  const targetDir = path.join(workspaceRoot, typeConfig.dir, y, m, d);
  if (!fs.existsSync(targetDir)) {
    return '001';
  }

  const files = fs.readdirSync(targetDir);
  let maxSeq = 0;
  for (const f of files) {
    if (f.endsWith('.md') && f !== 'index.md' && f !== 'README.md') {
      const match = f.match(/^(\d{3})_/);
      if (match) {
        const num = parseInt(match[1], 10);
        if (num > maxSeq) maxSeq = num;
      }
    }
  }

  if (maxSeq >= 999) throw new Error(`일자별 문서 순번 한도 초과: ${type} ${dateStr}`);
  return String(maxSeq + 1).padStart(3, '0');
}

/**
 * 날짜별 index.md 생성 (실제 작성 시각순 정렬)
 */
export function generateIndex(workspaceRoot, type, dateStr) {
  const typeConfig = DOC_TYPES[type.toLowerCase()];
  if (!typeConfig) throw new Error(`지원하지 않는 문서 종류: ${type}`);
  const { year: y, month: m, day: d } = assertValidDate(dateStr);
  const targetDir = path.join(workspaceRoot, typeConfig.dir, y, m, d);
  if (!fs.existsSync(targetDir)) return null;

  const files = fs.readdirSync(targetDir)
    .filter(f => f.endsWith('.md') && f !== 'index.md' && f !== 'README.md');

  const fileMetaList = [];
  for (const f of files) {
    const fullPath = path.join(targetDir, f);
    const content = fs.readFileSync(fullPath, 'utf8');
    const titleMatch = content.match(/^#\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1].trim() : f;
    const seqMatch = f.match(/^(\d{3})/);
    const seq = seqMatch ? seqMatch[1] : '-';

    let workId = '-';
    let createdAt = '-';
    let sortTime = '';

    const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (fmMatch) {
      try {
        const parsed = YAML.parse(fmMatch[1]);
        if (parsed.work_id) workId = parsed.work_id;
        if (parsed.created_at) {
          createdAt = parsed.created_at;
          sortTime = parsed.created_at;
        }
      } catch {}
    }

    if (!sortTime) {
      const timeMatch = content.match(/(?:작성일|검증일):\s*(\d{4}-\d{2}-\d{2}(?:\s+[0-9:]+)?)/);
      if (timeMatch) {
        createdAt = timeMatch[1];
        sortTime = timeMatch[1];
      }
    }

    fileMetaList.push({
      file: f,
      title,
      seq,
      workId,
      createdAt: createdAt !== '-' ? createdAt : `${dateStr} (미지정)`,
      sortTime: sortTime || f
    });
  }

  // 실제 작성 시각 오름차순 -> 순번 오름차순 정렬
  fileMetaList.sort((a, b) => {
    if (a.sortTime !== b.sortTime) return a.sortTime.localeCompare(b.sortTime);
    return a.seq.localeCompare(b.seq);
  });

  const rows = fileMetaList.map(item =>
    `| ${item.seq} | [${item.title}](./${item.file}) | \`${item.workId}\` | ${item.createdAt} |`
  );

  const indexContent = `# [Index] ${typeConfig.dir} ${y}-${m}-${d}

총 ${files.length}건의 문서가 등록되어 있습니다.

| 순번 | 문서 제목 | 작업 ID (\`work_id\`) | 작성 시각 (KST) |
| :---: | :--- | :---: | :---: |
${rows.join('\n')}
`;

  const indexPath = path.join(targetDir, 'index.md');
  writeTextAtomic(indexPath, indexContent);
  return indexPath;
}

/**
 * 기존 flat 문서 전수 동적 스캔 및 마이그레이션 매핑 산출
 */
export function planMigration(workspaceRoot) {
  const plansDir = path.join(workspaceRoot, 'Plans');
  const reportDir = path.join(workspaceRoot, 'Report');

  const items = [];

  // 1. Plans/ 동적 스캔
  if (fs.existsSync(plansDir)) {
    const files = fs.readdirSync(plansDir).filter(f => f.endsWith('.md') && f !== 'README.md' && f !== 'index.md');
    for (const f of files) {
      const fullPath = path.join(plansDir, f);
      const isTask = f.includes('_Task.md');
      const docType = isTask ? 'task' : 'plan';

      // 1순위: 문서 본문 내 작성 시각
      const content = fs.readFileSync(fullPath, 'utf8');
      const timeMatch = content.match(/작성일:\s*(\d{4}-\d{2}-\d{2}(?:[T\s]+[0-9:]+(?:\+[0-9:]+)?)?)/);

      // 날짜 접두사 추출
      const dateMatch = f.match(/^(\d{4})-(\d{2})-(\d{2})_(.+)$/);
      let dateStr, nameWithoutDate;
      if (dateMatch) {
        dateStr = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
        nameWithoutDate = dateMatch[4];
      } else {
        dateStr = getKSTDateString(fs.statSync(fullPath).mtime);
        nameWithoutDate = f;
      }
      assertValidDate(dateStr);

      const hasExplicitTime = timeMatch && timeMatch[1] && timeMatch[1].includes(':');
      let docTime = '';
      let sortBasis = '';
      let confidence = 'low';

      if (hasExplicitTime) {
        docTime = timeMatch[1].trim();
        sortBasis = 'document_timestamp';
        confidence = 'high';
      } else {
        // 2순위: Git 최초 추가 commit 시각
        const gitTime = getGitFirstAddedDate(fullPath, workspaceRoot);
        if (gitTime) {
          docTime = gitTime;
          sortBasis = 'git_first_added';
          confidence = 'medium';
        } else if (timeMatch && timeMatch[1]) {
          docTime = `${timeMatch[1].trim()} 23:59:59`;
          sortBasis = 'document_timestamp';
          confidence = 'high';
        } else {
          // 3순위: 파일명 사전순 fallback (시각 미지정 문서는 당일 말단 배치)
          docTime = `${dateStr} 23:59:59`;
          sortBasis = 'filename_fallback';
          confidence = 'low';
        }
      }

      items.push({
        sourceRel: path.posix.join('Plans', f),
        sourceAbs: fullPath,
        docType,
        dateStr,
        nameWithoutDate,
        docTime,
        sortBasis,
        confidence,
        fileName: f
      });
    }
  }

  // 2. Report/ 동적 스캔
  if (fs.existsSync(reportDir)) {
    const files = fs.readdirSync(reportDir).filter(f => f.endsWith('.md') && f !== 'README.md' && f !== 'index.md');
    for (const f of files) {
      const fullPath = path.join(reportDir, f);
      const docType = 'report';

      const content = fs.readFileSync(fullPath, 'utf8');
      const timeMatch = content.match(/(?:작성일|검증일):\s*(\d{4}-\d{2}-\d{2}(?:[T\s]+[0-9:]+(?:\+[0-9:]+)?)?)/);

      const dateMatch = f.match(/^(\d{4})-(\d{2})-(\d{2})_(.+)$/);
      let dateStr, nameWithoutDate;
      if (dateMatch) {
        dateStr = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
        nameWithoutDate = dateMatch[4];
      } else {
        // 날짜 없는 파일의 경우 Git 최초 추가 시각 또는 mtime으로 날짜 동적 결정
        const gitTime = getGitFirstAddedDate(fullPath, workspaceRoot);
        if (gitTime) {
          dateStr = gitTime.slice(0, 10);
        } else {
          dateStr = getKSTDateString(fs.statSync(fullPath).mtime);
        }
        nameWithoutDate = f;
      }
      assertValidDate(dateStr);

      const hasExplicitTime = timeMatch && timeMatch[1] && timeMatch[1].includes(':');
      let docTime = '';
      let sortBasis = '';
      let confidence = 'low';

      if (hasExplicitTime) {
        docTime = timeMatch[1].trim();
        sortBasis = 'document_timestamp';
        confidence = 'high';
      } else {
        const gitTime = getGitFirstAddedDate(fullPath, workspaceRoot);
        if (gitTime) {
          docTime = gitTime;
          sortBasis = 'git_first_added';
          confidence = 'medium';
        } else if (timeMatch && timeMatch[1]) {
          docTime = `${timeMatch[1].trim()} 23:59:59`;
          sortBasis = 'document_timestamp';
          confidence = 'high';
        } else {
          docTime = `${dateStr} 23:59:59`;
          sortBasis = 'filename_fallback';
          confidence = 'low';
        }
      }

      items.push({
        sourceRel: path.posix.join('Report', f),
        sourceAbs: fullPath,
        docType,
        dateStr,
        nameWithoutDate,
        docTime,
        sortBasis,
        confidence,
        fileName: f
      });
    }
  }

  // 일자별 및 타입별 정렬 후 순번 부여
  const groups = new Map();
  for (const item of items) {
    const key = `${item.docType}:${item.dateStr}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }

  const migrationPlan = [];
  const destinationSet = new Set();
  let conflicts = 0;

  for (const [key, groupItems] of groups.entries()) {
    const [docType, dateStr] = key.split(':');
    const [y, m, d] = dateStr.split('-');

    // 정렬: docTime 오름차순 -> fileName 사전순
    groupItems.sort((a, b) => {
      if (a.docTime !== b.docTime) return a.docTime.localeCompare(b.docTime);
      return a.fileName.localeCompare(b.fileName);
    });

    let seq = 1;
    for (const item of groupItems) {
      const seqStr = String(seq).padStart(3, '0');
      const targetDirRel = path.posix.join(DOC_TYPES[docType].dir, y, m, d);
      const targetFileName = `${seqStr}_${item.nameWithoutDate}`;
      const targetRel = path.posix.join(targetDirRel, targetFileName);
      const targetAbs = path.join(workspaceRoot, targetRel);

      // 실제 디스크상 목적지 존재 여부 검사
      const existsOnDisk = fs.existsSync(targetAbs);
      const duplicateInPlan = destinationSet.has(targetRel);
      if (existsOnDisk || duplicateInPlan) {
        conflicts++;
      }
      destinationSet.add(targetRel);

      migrationPlan.push({
        source: item.sourceRel,
        destination: targetRel,
        type: item.docType,
        date: dateStr,
        seq: seqStr,
        docTime: item.docTime,
        sortBasis: item.sortBasis,
        confidence: item.confidence,
        conflict: existsOnDisk || duplicateInPlan
      });
      seq++;
    }
  }

  migrationPlan.conflicts = conflicts;
  return migrationPlan;
}

function collectActiveMarkdownFiles(workspaceRoot) {
  const files = [];
  const visit = (candidate, relativeRoot = '') => {
    if (!fs.existsSync(candidate)) return;
    for (const entry of fs.readdirSync(candidate, { withFileTypes: true })) {
      const relative = path.posix.join(relativeRoot, entry.name);
      if (entry.isDirectory()) {
        if (['.git', '.venv', 'venv', 'node_modules', 'Chat', 'Staging', 'scratch'].includes(entry.name) || relative === '.agent-governance/legacy-sources' || relative === '.agent-governance/.state') continue;
        visit(path.join(candidate, entry.name), relative);
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        files.push(path.join(candidate, entry.name));
      }
    }
  };
  visit(workspaceRoot);
  return files;
}

function rewriteActiveReferences(workspaceRoot, plan, snapshot) {
  let changed = 0;
  for (const file of collectActiveMarkdownFiles(workspaceRoot)) {
    let content = fs.readFileSync(file, 'utf8');
    let next = content;
    for (const item of plan) {
      next = next.replaceAll(item.source, item.destination);
      next = next.replaceAll(item.source.replaceAll('/', '\\'), item.destination.replaceAll('/', '\\'));
    }
    if (next !== content) {
      snapshot(file);
      writeTextAtomic(file, next);
      changed++;
    }
  }
  return changed;
}

/**
 * 마이그레이션 실행 (원자적 트랜잭션 및 롤백 보장)
 */
export function executeMigration(workspaceRoot, plan) {
  if (plan.conflicts > 0) {
    throw new Error(`마이그레이션 중단: 목적지 경로 충돌이 ${plan.conflicts}건 존재합니다.`);
  }

  // Preflight 1: 전체 소스 존재 및 경로 이탈 검증
  for (const item of plan) {
    const srcAbs = assertInsideWorkspace(workspaceRoot, path.join(workspaceRoot, item.source), item.source);
    const dstAbs = assertInsideWorkspace(workspaceRoot, path.join(workspaceRoot, item.destination), item.destination);

    if (!fs.existsSync(srcAbs)) {
      throw new Error(`Preflight 실패 - 소스 파일 부재: ${item.source}`);
    }

    if (fs.existsSync(dstAbs)) {
      throw new Error(`Preflight 실패 - 목적지 경로 존재: ${item.destination}`);
    }
  }

  const movedFiles = [];
  const auxiliarySnapshots = [];

  const snapshot = (targetPath) => {
    if (auxiliarySnapshots.some(item => item.path === targetPath)) return;
    auxiliarySnapshots.push({ path: targetPath, existed: fs.existsSync(targetPath), content: fs.existsSync(targetPath) ? fs.readFileSync(targetPath, 'utf8') : null });
  };

  try {
    // 이동 단계
    for (const item of plan) {
      const srcAbs = path.join(workspaceRoot, item.source);
      const dstAbs = path.join(workspaceRoot, item.destination);
      const dstDir = path.dirname(dstAbs);

      if (!fs.existsSync(dstDir)) {
        fs.mkdirSync(dstDir, { recursive: true });
      }

      fs.renameSync(srcAbs, dstAbs);
      movedFiles.push({ src: srcAbs, dst: dstAbs });
    }

    // path map 저장
    const pathMap = createPathMap(plan, 'completed');

    const mapAbs = path.join(workspaceRoot, PATH_MAP_REL_PATH);
    snapshot(mapAbs);
    writeTextAtomic(mapAbs, YAML.stringify(pathMap));

    // index.md 생성
    const datesByType = new Map();
    for (const item of plan) {
      const key = `${item.type}:${item.date}`;
      datesByType.set(key, true);
    }
    for (const key of datesByType.keys()) {
      const [t, d] = key.split(':');
      const cfg = DOC_TYPES[t];
      const { year, month, day } = assertValidDate(d);
      snapshot(path.join(workspaceRoot, cfg.dir, year, month, day, 'index.md'));
      generateIndex(workspaceRoot, t, d);
    }

    const referencesUpdated = rewriteActiveReferences(workspaceRoot, plan, snapshot);

    // 기존 빈 디렉터리 정리 (옵션)
    return {
      status: 'success',
      totalMigrated: movedFiles.length,
      pathMapFile: PATH_MAP_REL_PATH,
      referencesUpdated
    };
  } catch (err) {
    const rollbackErrors = [];
    for (let i = auxiliarySnapshots.length - 1; i >= 0; i--) {
      const item = auxiliarySnapshots[i];
      try {
        if (item.existed) writeTextAtomic(item.path, item.content);
        else if (fs.existsSync(item.path)) fs.unlinkSync(item.path);
      } catch (rErr) {
        rollbackErrors.push(`보조 파일 롤백 실패 (${item.path}): ${rErr.message}`);
      }
    }
    // 롤백 단계: 실패 시 이미 이동된 파일들을 즉시 원위치로 복구
    for (let i = movedFiles.length - 1; i >= 0; i--) {
      const m = movedFiles[i];
      try {
        if (fs.existsSync(m.dst)) {
          fs.renameSync(m.dst, m.src);
        }
      } catch (rErr) {
        rollbackErrors.push(`롤백 실패 (${m.dst} -> ${m.src}): ${rErr.message}`);
      }
    }

    const failureMsg = `마이그레이션 실패로 전체 롤백 수행 (이동 시도 ${movedFiles.length}건 원복 완료). 원인: ${err.message}` +
      (rollbackErrors.length > 0 ? `\n치명적 롤백 에러:\n${rollbackErrors.join('\n')}` : '');
    throw new Error(failureMsg);
  }
}

/**
 * 구조 및 메타데이터 정밀 검증
 */
export function validateArchive(workspaceRoot) {
  const errors = [];
  const dirs = ['Plans', 'Tasks', 'Reports'];
  const mapAbs = path.join(workspaceRoot, PATH_MAP_REL_PATH);
  let mapData = null;
  if (fs.existsSync(mapAbs)) {
    try { mapData = YAML.parse(fs.readFileSync(mapAbs, 'utf8')); }
    catch (error) { errors.push(`path-map 파싱 실패: ${error.message}`); }
  }
  const legacyDestinations = new Set(Object.values(mapData?.mappings ?? {}).map(value => String(value).replace(/\\/g, '/')));

  const foundSeqsByDate = new Map(); // `${type}:${date}` -> Set(seq)
  const foundArtifactIds = new Set();

  for (const d of dirs) {
    const dirAbs = path.join(workspaceRoot, d);
    if (!fs.existsSync(dirAbs)) continue;

    const scan = (current) => {
      const entries = fs.readdirSync(current, { withFileTypes: true });
      for (const e of entries) {
        const full = path.join(current, e.name);
        if (e.isDirectory()) {
          scan(full);
        } else if (e.name.endsWith('.md')) {
          if (e.name === 'index.md' || e.name === 'README.md') continue;
          const rel = path.relative(workspaceRoot, full).replace(/\\/g, '/');

          // 1. 경로 및 파일명 정규식 검사
          const match = rel.match(/^(Plans|Tasks|Reports)\/(\d{4})\/(\d{2})\/(\d{2})\/(\d{3})_(.+)\.md$/);
          if (!match) {
            errors.push(`경로/파일명 규격 위반: ${rel} (예: Plans/YYYY/MM/DD/NNN_<Title>_Plan.md)`);
            continue;
          }

          const [, docTypeDir, y, m, day, seqStr, title] = match;

          // 2. 날짜 유효성 검사
          try {
            assertValidDate(`${y}-${m}-${day}`);
          } catch {
            errors.push(`비정상적인 날짜: ${rel}`);
          }

          const expectedSuffix = docTypeDir === 'Plans' ? '_Plan' : docTypeDir === 'Tasks' ? '_Task' : '_Report';
          if (!title.endsWith(expectedSuffix)) {
            errors.push(`문서 종류와 파일 접미사 불일치: ${rel}`);
          }

          // 3. 일자 폴더 내 순번 중복 검사
          const dateKey = `${docTypeDir}:${y}-${m}-${day}`;
          if (!foundSeqsByDate.has(dateKey)) foundSeqsByDate.set(dateKey, new Set());
          const seqSet = foundSeqsByDate.get(dateKey);
          if (seqSet.has(seqStr)) {
            errors.push(`순번 중복 감지 (${dateKey}): 순번 ${seqStr} (${rel})`);
          }
          seqSet.add(seqStr);

          // 4. front matter 검사 (존재하는 경우)
          const content = fs.readFileSync(full, 'utf8');
          const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
          if (fmMatch) {
            try {
              const meta = YAML.parse(fmMatch[1]);
              for (const required of ['artifact_id', 'work_id', 'created_at', 'related_artifacts']) {
                if (meta?.[required] === undefined || meta?.[required] === null) errors.push(`필수 front matter 누락 (${required}): ${rel}`);
              }
              if (meta?.created_at && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+09:00$/.test(String(meta.created_at))) {
                errors.push(`created_at KST 형식 위반: ${rel}`);
              }
              if (meta?.related_artifacts !== undefined && !Array.isArray(meta.related_artifacts)) errors.push(`related_artifacts 배열 형식 위반: ${rel}`);
              if (meta.artifact_id) {
                if (foundArtifactIds.has(meta.artifact_id)) {
                  errors.push(`artifact_id 중복: ${meta.artifact_id} in ${rel}`);
                }
                foundArtifactIds.add(meta.artifact_id);
              }

              // related_artifacts 상대 링크 유효성 검사
              if (Array.isArray(meta.related_artifacts)) {
                for (const link of meta.related_artifacts) {
                  const targetAbs = path.resolve(path.dirname(full), link);
                  try { assertInsideWorkspace(workspaceRoot, targetAbs, `${rel} -> ${link}`); } catch { errors.push(`관련 문서 링크의 워크스페이스 이탈: ${link} in ${rel}`); continue; }
                  if (!fs.existsSync(targetAbs)) {
                    errors.push(`깨진 관련 문서 링크: ${link} in ${rel}`);
                  }
                }
              }
            } catch (err) {
              errors.push(`front matter YAML 파싱 오류: ${rel} (${err.message})`);
            }
          } else if (!legacyDestinations.has(rel)) {
            errors.push(`신규 문서 front matter 누락: ${rel}`);
          }
        }
      }
    };
    scan(dirAbs);
  }

  // 5. artifact-path-map.yaml 무결성 검증 (존재하는 경우)
  if (mapData?.mappings) {
        const entries = Object.entries(mapData.mappings);
        if (mapData.total_mappings !== entries.length) errors.push(`path-map 수량 불일치: 선언 ${mapData.total_mappings}, 실제 ${entries.length}`);
        if (!Array.isArray(mapData.records) || mapData.records.length !== entries.length) errors.push('path-map migration records 수량 불일치');
        for (const [oldPath, newPath] of entries) {
          const newAbs = path.join(workspaceRoot, newPath);
          if (!fs.existsSync(newAbs)) {
            errors.push(`path-map 목적지 파일 누락: ${newPath} (from ${oldPath})`);
          }
        }
        for (const file of collectActiveMarkdownFiles(workspaceRoot)) {
          const rel = path.relative(workspaceRoot, file).replace(/\\/g, '/');
          const content = fs.readFileSync(file, 'utf8');
          for (const oldPath of Object.keys(mapData.mappings)) {
            if (content.includes(oldPath) || content.includes(oldPath.replaceAll('/', '\\'))) {
              errors.push(`활성 문서에 과거 경로 잔존: ${oldPath} in ${rel}`);
            }
          }
        }
  }

  return {
    valid: errors.length === 0,
    errorsCount: errors.length,
    errors
  };
}

/**
 * CLI 진입점
 */
export async function main(args = process.argv.slice(2)) {
  let workspaceRoot = process.cwd();
  const cmd = args[0];

  // --workspace 인자 탐색
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--workspace' && args[i + 1]) {
      workspaceRoot = path.resolve(args[i + 1]);
      break;
    }
  }

  if (!cmd || cmd === '--help' || cmd === '-h') {
    console.log(`
사용법: node artifact-manager.mjs <command> [options]

명령어:
  next --type <plan|task|report> [--date YYYY-MM-DD] [--workspace <dir>] [--touch <title>] [--work-id <id>] [--related <path>]
                                                        다음 3자리 순번 발급 (옵션: 파일 즉시 생성)
  validate [--workspace <dir>]                         문서 보관 구조, 중복, 링크 무결성 검증
  index [--type <plan|task|report>] [--date YYYY-MM-DD] [--workspace <dir>]
                                                        일자별 index.md 생성
  migrate [--dry-run] [--execute] [--export-map] [--workspace <dir>]
                                                        원자적 마이그레이션 및 매핑 생성
  resolve <historical-path> [--workspace <dir>]         과거 경로의 새 경로 조회
`);
    return 0;
  }

  if (cmd === 'next') {
    let type = 'plan';
    let dateStr = getKSTDateString();
    let touchTitle = null;
    let workId = null;
    const relatedArtifacts = [];

    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--type' && args[i + 1]) type = args[++i];
      if (args[i] === '--date' && args[i + 1]) dateStr = args[++i];
      if (args[i] === '--touch' && args[i + 1]) touchTitle = args[++i];
      if (args[i] === '--work-id' && args[i + 1]) workId = args[++i];
      if (args[i] === '--related' && args[i + 1]) relatedArtifacts.push(args[++i]);
    }

    const release = acquireLock(workspaceRoot);
    try {
      const nextSeq = getNextSequence(workspaceRoot, type, dateStr);
      let createdFile = null;

      if (touchTitle) {
        const typeConfig = DOC_TYPES[type.toLowerCase()];
        const { year: y, month: m, day: d } = assertValidDate(dateStr);
        const targetDir = path.join(workspaceRoot, typeConfig.dir, y, m, d);
        if (!fs.existsSync(targetDir)) fs.mkdirSync(targetDir, { recursive: true });

        const safeTitle = normalizeTitle(touchTitle);
        const fileName = `${nextSeq}_${safeTitle}_${typeConfig.suffix}`;
        const targetPath = assertInsideWorkspace(workspaceRoot, path.join(targetDir, fileName), fileName);
        if (!fs.existsSync(targetPath)) {
          const typePrefix = type.toUpperCase();
          const artifactId = `${typePrefix}-${dateStr.replaceAll('-', '')}-${nextSeq}`;
          const resolvedWorkId = workId ?? `WORK-${dateStr.replaceAll('-', '')}-${nextSeq}`;
          if (!/^[A-Za-z0-9._-]+$/.test(resolvedWorkId)) throw new Error(`잘못된 work_id: ${resolvedWorkId}`);
          const metadata = {
            artifact_id: artifactId,
            work_id: resolvedWorkId,
            created_at: getKSTTimestamp(),
            related_artifacts: relatedArtifacts
          };
          const body = `---\n${YAML.stringify(metadata)}---\n# [${typeConfig.dir.slice(0, -1)}] ${safeTitle}\n`;
          fs.writeFileSync(targetPath, body, { encoding: 'utf8', flag: 'wx' });
          createdFile = path.relative(workspaceRoot, targetPath).replace(/\\/g, '/');
        }
      }

      console.log(JSON.stringify({ type, date: dateStr, nextSeq, createdFile }));
    } finally {
      release();
    }
    return 0;
  }

  if (cmd === 'migrate') {
    const isExportMap = args.includes('--export-map');
    const isExecute = args.includes('--execute');
    const isDryRun = !isExecute && !isExportMap;

    const plan = planMigration(workspaceRoot);

    if (isExportMap) {
      if (plan.conflicts > 0) throw new Error(`경로 맵 생성 중단: 목적지 충돌 ${plan.conflicts}건`);
      const pathMap = createPathMap(plan, 'planned');
      const mapAbs = path.join(workspaceRoot, PATH_MAP_REL_PATH);
      const release = acquireLock(workspaceRoot);
      try { writeTextAtomic(mapAbs, YAML.stringify(pathMap)); } finally { release(); }
      console.log(JSON.stringify({ status: 'planned', totalMappings: plan.length, mapFile: PATH_MAP_REL_PATH }));
      return 0;
    }

    if (isDryRun && !isExecute) {
      console.log(JSON.stringify({
        mode: 'dry-run',
        totalDocuments: plan.length,
        plans: plan.filter(p => p.type === 'plan').length,
        tasks: plan.filter(p => p.type === 'task').length,
        reports: plan.filter(p => p.type === 'report').length,
        conflicts: plan.conflicts,
        sample: plan.slice(0, 5)
      }, null, 2));
      return plan.conflicts === 0 ? 0 : 1;
    }

    if (isExecute) {
      const release = acquireLock(workspaceRoot);
      try {
        const result = executeMigration(workspaceRoot, plan);
        console.log(JSON.stringify(result, null, 2));
      } finally {
        release();
      }
      return 0;
    }
  }

  if (cmd === 'index') {
    let type = 'plan';
    let dateStr = getKSTDateString();
    for (let i = 1; i < args.length; i++) {
      if (args[i] === '--type' && args[i + 1]) type = args[++i];
      if (args[i] === '--date' && args[i + 1]) dateStr = args[++i];
    }

    const release = acquireLock(workspaceRoot);
    try {
      const indexFile = generateIndex(workspaceRoot, type, dateStr);
      console.log(JSON.stringify({ type, date: dateStr, indexFile }));
      return indexFile ? 0 : 1;
    } finally {
      release();
    }
  }

  if (cmd === 'resolve') {
    const lookupPath = args[1];
    if (!lookupPath) {
      console.error('조회할 경로를 입력하세요.');
      return 1;
    }

    const mapAbs = path.join(workspaceRoot, PATH_MAP_REL_PATH);
    if (!fs.existsSync(mapAbs)) {
      console.error(`경로 맵 파일이 없습니다: ${PATH_MAP_REL_PATH}`);
      return 1;
    }

    const mapData = YAML.parse(fs.readFileSync(mapAbs, 'utf8'));
    const normalized = lookupPath.replace(/\\/g, '/');

    // 1. 과거 경로 -> 새 경로 조회
    let resolved = mapData.mappings?.[normalized] || null;

    // 2. 새 경로 -> 과거 경로 역방향 조회도 지원
    if (!resolved && mapData.mappings) {
      for (const [k, v] of Object.entries(mapData.mappings)) {
        if (v === normalized) {
          resolved = k;
          break;
        }
      }
    }

    console.log(JSON.stringify({ query: lookupPath, resolved }));
    return resolved ? 0 : 1;
  }

  if (cmd === 'validate') {
    const res = validateArchive(workspaceRoot);
    console.log(JSON.stringify(res, null, 2));
    return res.valid ? 0 : 1;
  }

  console.error(`알 수 없는 명령어: ${cmd}`);
  return 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main()
    .then(code => { process.exitCode = code; })
    .catch(err => {
      console.error(err);
      process.exitCode = 1;
    });
}
