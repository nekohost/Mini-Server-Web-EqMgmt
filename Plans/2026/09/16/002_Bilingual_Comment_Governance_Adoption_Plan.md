---
artifact_id: PLAN-20260916-002
work_id: WORK-20260916-BILINGUAL-COMMENT-GOVERNANCE-ADOPTION
created_at: 2026-09-16T14:25:00+09:00
related_artifacts:
  - ../../../../Reports/2026/09/16/002_HTCE_Bilingual_Comment_Governance_Verification_Report.md
  - ../../../../Tasks/2026/09/16/001_Bilingual_Comment_Governance_Adoption_Task.md
---
# 이중언어 주석·한국어 Git 정책 도입 계획

## 목표
- HTCE의 Comment ID + EN/KO revision + source hash 체계를 Mini-Server 기존 거버넌스에 중복 없이 결합한다.
- 기존 `[역할]`·`[의존성 관계]`·`[변경 시 영향도]` 의미를 EN/KO 블록 안에서 보존한다.
- Python·JavaScript·HTML의 명시적 추적 블록을 검사하는 다중언어 comment-sync 도구를 추가한다.
- Gemini의 감사·한국어 동기화 후 Git diff guard로 실행 코드·EN 기준 주석의 비인가 변경을 차단한다.
- Git commit은 Conventional Commit type을 유지하고 제목·본문 설명은 한국어를 기본으로 한다.

## 범위
1. Staging에서 규격 문서·parser·diff guard와 파일럿 fixture를 검증한다.
2. Rule 1-3 및 4-3 계열과 `engineering.code-comments`를 같은 의미로 동기화한다.
3. Gemini 진입점/capability에 감사 역할과 guard 절차를 연결한다.
4. 파일럿은 핵심 백엔드 1개 파일부터 시작하며 전 저장소 일괄 변환은 하지 않는다.
5. HTCE coordination 체계는 복제하지 않고 기존 Plans/Tasks/Reports 및 `.agent-governance`를 SSOT로 유지한다.

## 최종 교차검토 반영 (2026-09-16)

사용자의 추가 승인 없는 보완·종료 지시에 따라 현재 runtime이 선택한 독립 노드에서 Codex가 검토와 잔여 감사를 수행한다. Gemini가 실행한 것으로 기록하지 않으며 legacy 역할 분담은 변경하지 않는다.

- 기준선 갱신의 이전 상태 비교, revision 회귀·재감사 누락 및 잘못된 marker를 차단한다.
- 공유 주석 판독기, Git index와 NUL 경로 검사, snapshot 보존, 최초 KO 추가를 보강한다.
- commit 제목/본문 언어 검사와 실제 sync-plan 신규 섹션 매핑 회귀를 추가한다.
- 파일럿 EN 의존 방향/입력 범위를 정정하여 EN/KO rev.2로 감사하고 최초 baseline에 실제 감사자를 기록한다.
- 소스 의미는 Linux의 메모리 내 격리 fixture로 검증하며 앱/DB/서비스는 변경하지 않는다.
- [최종 검토 보고서](../../../../Reports/2026/09/16/004_Bilingual_Comment_Governance_Final_Review_Report.md)에 검증 범위와 한계를 남기고 관련 변경만 commit/push한다.
