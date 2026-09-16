#!/usr/bin/env node
// [역할] AI가 만드는 Git commit 제목이 Conventional Commit type + 한국어 설명 규칙을 따르는지 검사합니다.
// [의존성 관계] Git hook 자체를 설치하지 않고 commit 직전 명시 실행하는 보조 도구입니다.
// [변경 시 영향도] 허용 type이나 예외 변경은 저장소 이력의 가독성과 자동화 호환성에 영향을 줍니다.
const message = process.argv.slice(2).join(' ').trim(); // 전달된 commit 제목을 그대로 합칩니다.
const allowedTypes = new Set(['feat', 'fix', 'docs', 'test', 'refactor', 'perf', 'style', 'build', 'ci', 'chore', 'revert']); // 표준 type allowlist입니다.

if (!message) { // 제목 누락을 먼저 거부합니다.
  console.error('COMMIT-MESSAGE: missing subject'); // 사람이 이해할 수 있는 오류입니다.
  process.exitCode = 2; // 사용 오류로 종료합니다.
} else if (/^(Merge|Revert ")/.test(message)) { // Git 자동 merge/revert 형식은 별도 예외입니다.
  console.log('COMMIT-MESSAGE: AUTO-GENERATED-EXCEPTION'); // 수동 한국어 규칙과 구분합니다.
} else { // 일반 AI 작성 commit을 검사합니다.
  const match = message.match(/^([a-z]+)(?:\([^)]+\))?!?:\s+(.+)$/); // Conventional Commit 기본 형식입니다.
  if (!match || !allowedTypes.has(match[1])) { // type이나 구분자가 잘못된 경우입니다.
    console.error('COMMIT-MESSAGE: invalid Conventional Commit type/format'); // 형식 오류를 표시합니다.
    process.exitCode = 1; // commit 전에 중단할 수 있게 합니다.
  } else if (!/[가-힣]/.test(match[2])) { // 사람이 읽는 설명에 한국어가 실제 포함됐는지 검사합니다.
    console.error('COMMIT-MESSAGE: Korean subject required'); // 영어-only 제목을 거부합니다.
    process.exitCode = 1; // 정책 위반입니다.
  } else { // 형식과 언어가 모두 적합합니다.
    console.log('COMMIT-MESSAGE: OK'); // 정상 판정입니다.
  }
}
