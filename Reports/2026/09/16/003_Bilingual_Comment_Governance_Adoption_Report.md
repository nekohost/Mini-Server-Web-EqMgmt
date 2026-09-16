---
artifact_id: REPORT-20260916-003
work_id: WORK-20260916-BILINGUAL-COMMENT-GOVERNANCE-ADOPTION
created_at: 2026-09-16T14:25:00+09:00
related_artifacts:
  - ../../../../Plans/2026/09/16/002_Bilingual_Comment_Governance_Adoption_Plan.md
  - ../../../../Tasks/2026/09/16/001_Bilingual_Comment_Governance_Adoption_Task.md
  - 002_HTCE_Bilingual_Comment_Governance_Verification_Report.md
---
# 이중언어 주석·한국어 Git 정책 도입 보고서

## 코드 작성 전 Validation 1~8
1. **거버넌스**: 현재 Rule hash와 manifest가 일치하고 validate가 통과했다. Staging 우선, 기존 다른 작업자의 미커밋 파일은 비대상으로 보존한다.
2. **사용자 의도**: ChatGPT/Codex의 기술 구현 강점과 Gemini의 한국어·감사 강점을 분리한다. HTCE 전체 coordination 체계는 복제하지 않는다.
3. **정적 논리**: Comment ID·EN/KO rev·EN/KO/source hash를 검사하고, 명시적 블록만 추적해 기존 주석을 오탐하지 않게 한다.
4. **운영 영향**: DB·서비스·API 계약은 변경하지 않는다. Rule/노드/진입점과 검사 도구만 추가·개정하며 파일럿은 한 파일로 제한한다.
5. **보안·엣지**: Gemini는 KO 본문/KO rev/용어집/comment-sync 상태·보고서 외 실행 코드·EN·스키마·설정을 수정하지 않는다. diff guard는 fail-closed다.
6. **롤백**: Staging 후보는 삭제 가능하며 운영 반영 후에도 Git revert와 baseline 제거로 복구 가능하다. baseline만 고쳐 경고를 숨기는 행위를 금지한다.
7. **휴먼 에러**: source 변경 후 EN rev 누락, EN/KO 본문 변경 후 rev 누락, KO ahead, 중복 ID, 삭제 ID를 각각 다른 상태로 보고한다.
8. **AI 메타**: Gemini의 역할은 기술 주석 감사+한국어 동기화이며 일반 구현 권한으로 확대하지 않는다. ChatGPT/Codex도 KO를 대신 동기화하지 않는다.

사전 판정: Staging 도구·규격 구현을 진행할 수 있다. Rule 병합은 후보 검증 후 별도의 sync-plan/validate를 통과해야 한다.

## Staging 후보 검증
- `comment-sync.mjs`: Python `#`/triple quote, JavaScript `//`/block, HTML comment의 명시적 `MINI-COMMENT` 블록을 지원한다.
- `gemini-diff-guard.mjs`: 감사 전 snapshot으로 기존 dirty 파일을 보존하고, 같은 HEAD에서 KO-only delta만 허용한다.
- `commit-message-check.mjs`: Conventional Commit type + 한국어 제목을 검사하고 자동 merge/revert는 분리한다.
- baseline은 `--accept-audited` 없이는 갱신되지 않는다.
- source hash는 초기에는 다음 추적 블록 또는 EOF까지 보수적으로 계산해 누락보다 재감사를 우선한다.

실행 결과: 임시 Python/JS/HTML 및 임시 Git 저장소 기반 **27개 회귀 케이스 전부 통과**. 운영 저장소/DB/서비스는 검증 과정에서 수정하지 않았다.
검증 항목에는 source 변경 rev 누락, EN/KO rev 누락, KO ahead, 중복/삭제 ID, legacy inventory, 신규 EN-only 정상 인계, KO-only 허용, 실행 코드·EN 변경 차단, 선행 dirty 변경 보존, HEAD 변경 snapshot 무효화, 한국어 commit 메시지 규칙이 포함된다.
## 운영 반영 결과
- 거버넌스 버전을 `1.8.0`으로 갱신하고 Rule 4-3-5/4-3-6/7-4-4/7-5-5를 기존 노드에 연결했다.
- `sync-plan --map-section <new-section>=<existing-node-id>`를 추가해 신규 Rule 섹션도 자동 추론 없이 기존 노드에 명시 연결할 수 있게 했다.
- 신규 source_rule 반영 시 `traceability/rule-map.yaml`도 필수 동기화 대상으로 포함하도록 `sync-plan` 계약을 보완했다.
- Rule·human-rule-map·rule-map·section baseline·manifest·execution profile package hash를 같은 변경 단위로 봉인했다.
- `GEMINI.md`, `AGENTS.md`, `CHATGPT.md`에 역할별 주석 책임과 한국어 commit 정책을 연결하고 Gemini capability에 KO-only 감사 경계를 명시했다.
- Rule 유지보수의 공통 base가 약 4,052 tokens이고 `governance.human-reference + governance.rule-sync`가 약 1,650 tokens이므로, 규칙을 제거하지 않는 small-model 분할 계약을 유지하기 위해 예산을 5,000에서 6,000으로 최소 조정했다.

## 파일럿 상태
- `utils/lineup_node_service.py::_required_int()`에 `LINEUP.NODE.REQUIRED_INT`를 파일럿 적용했다.
- ChatGPT는 EN rev.1을 작성했고 기존 한국어 메타 주석은 문구를 바꾸지 않은 채 KO rev.0으로 이전했다.
- 실제 검사 결과는 `TRANSLATION-PENDING + NEW-UNBASELINED`이며, `baseline --accept-audited`는 의도대로 거부됐다.
- Python AST 검사는 `PY_AST_PASS`다.
- 이 상태는 실패가 아니라 Gemini의 실제 소스/EN 감사가 필요한 정식 인계 상태다. Gemini가 KO를 rev.1로 감사·동기화한 뒤 diff guard를 통과해야 최초 baseline을 생성할 수 있다.

## 최종 회귀
- `governance-tool.test.mjs`: 17/17 통과.
- `execution-profile.test.mjs`: 33/33 통과.
- `comment-sync.test.mjs`: 27/27 통과.
- `governance-tool validate`: errors 0, warnings 0.
- `sync-status`: `inSync=true`, Rule SHA `9DC100A665B2EE74D1D2CE1FC2E016BD5F617ED858DBF1786B06B90112180420`.

종합 판정: 이중언어 주석 동기화 기반과 한국어 Git 기록 정책의 도입은 완료되었다. 최초 파일럿 baseline만 역할 분리 원칙에 따라 Gemini 감사 후속 단계로 남긴다.

## Git 반영
- 구현 commit: `51a482613f4cb305508e5840a3ce00719bb479ef`
- 제목: `feat: 이중언어 주석 동기화 거버넌스 도입`
- `HEAD`, `origin/main`, 원격 `main`이 모두 동일한 SHA로 확인됐다.
- 다른 작업자의 `Reports/2026/09/10/016_Lineup_Registration_UX_Followup_Review_Report.md` 미커밋 변경은 stage/commit하지 않고 그대로 보존했다.
- 본 변경은 거버넌스·도구·주석 메타데이터 도입이며 Flask 실행 동작이나 DB 스키마를 변경하지 않으므로 서버 서비스 재시작·배포는 수행하지 않았다.
