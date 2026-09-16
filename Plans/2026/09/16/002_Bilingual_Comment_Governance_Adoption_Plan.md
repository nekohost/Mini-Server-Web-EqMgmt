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
