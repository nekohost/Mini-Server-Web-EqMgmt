---
artifact_id: TASK-20260916-001
work_id: WORK-20260916-BILINGUAL-COMMENT-GOVERNANCE-ADOPTION
created_at: 2026-09-16T14:25:00+09:00
related_artifacts:
  - ../../../../Plans/2026/09/16/002_Bilingual_Comment_Governance_Adoption_Plan.md
  - ../../../../Reports/2026/09/16/002_HTCE_Bilingual_Comment_Governance_Verification_Report.md
---
# 이중언어 주석·한국어 Git 정책 도입 Task

- [x] HTCE 외부 참조 실사 및 Gemini 교차검증 근거 확인
- [x] Mini-Server 현재 Rule/code-comments/Gemini capability 확인
- [x] 기존 다른 작업자 변경과 Git 기준점 확인
- [x] Staging 다중언어 comment-sync parser 작성
- [x] Staging Gemini diff guard 작성
- [x] Python/JavaScript/HTML fixture 및 source-hash 회귀 검증
- [x] Rule 1-3, 4-3 계열 개정안 작성 및 sync-plan 확인
- [x] `engineering.code-comments` 및 traceability/manifest 동기화
- [x] GEMINI/AGENTS/CHATGPT 역할 진입점 갱신
- [x] 핵심 백엔드 1개 파일 파일럿 EN rev.1 / 기존 KO rev.0 인계 적용
- [x] 파일럿 실제 소스/EN 감사 후 KO 동기화 및 최초 baseline 생성 — 이번 사용자 승인·dedicated 경로의 Codex가 수행, EN/KO rev.2. Gemini 수행으로 기록하지 않음
- [x] governance validate + comment-sync + Git guard 회귀 검증
- [x] Report/색인/커밋 정책 적용 및 Git 반영 (`51a482613f4cb305508e5840a3ce00719bb479ef`)

다른 작업자의 미커밋 파일은 이 작업의 대상이 아니며 덮어쓰거나 stage하지 않는다.

## 최종 검토 보완

- [x] 기존 검사기의 누락 재현 및 baseline/revision/parser/index/경로/commit 검사 보완
- [x] 실제 sync-plan 신규 섹션 매핑 함수의 성공·실패·원본 보존 회귀 추가
- [x] 파일럿 KO-only guard, 최초 baseline 및 Linux 격리 계약 21건·실행 AST 불변 확인
- [x] Rule·traceability 동기화 및 dedicated/legacy 선택 계약 유지 확인
- [x] 최종 검토 보고서·규격·기능 문서·보고서 색인 동기화

상세 증거 및 Git 최종 결과: [후속 검토 보고서](../../../../Reports/2026/09/16/004_Bilingual_Comment_Governance_Final_Review_Report.md).
