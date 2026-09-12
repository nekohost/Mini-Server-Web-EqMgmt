---
artifact_id: PLAN-20260912-002
work_id: WORK-20260912-GOVERNANCE-CONTEXT-CLARITY
created_at: 2026-09-12T17:41:35.779+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/12/004_Governance_Context_Clarity_Task.md
  - ../../../../Reports/2026/09/12/005_Governance_Context_Clarity_Report.md
  - ../../../../Reports/2026/09/12/004_Context_Routing_Diagnosis_Report.md
---

# 거버넌스 Context 명확성 개선 계획

사용자는 Rule·거버넌스 수정, Staging 검증, 운영 거버넌스 반영, commit·push를 명시 승인했다. 이번 변경은 공식 모델명 기능 구현이나 운영 DB/서비스 배포를 포함하지 않는다.

## 설계

1. migration/UI 작업의 필수 규칙은 intent로 선택한다. Staging 경로 때문에 DB/UI 보호 규칙이 누락되지 않는다.
2. 대상 경로는 독립적으로 검증한다. 일반 implement/question intent가 미분류 경로를 자동 승인하지 않는다. 등록된 프로젝트 경로 패턴 및 명시된 외부 scope를 사용한다.
3. 기존 --path는 작업 대상, 새 --reference-path는 참고·영향 대상으로 분리한다. 참고 경로를 운영 수정 권한으로 해석하지 않으며 Staging 경로를 임의로 원본으로 변환하지 않는다.
4. UNKNOWN_INTENT, INTENT_PATH_MISMATCH, UNMATCHED_PATH, EXTERNAL_SCOPE_REQUIRED, MISSING_SECTION 등 기계 판독 진단을 제공한다. 실패 시 pack을 반환하지 않고 원인/확인 수단/재개 조건을 명시한다.
5. catalog·도움말·README와 네 플랫폼 진입점에 같은 사용법을 제공한다. 입력 오류는 일반 구현을 중단한 채 읽기 전용 진단과 근거 있는 정정을 할 수 있다. validate와 새 context가 성공하고 전체 pack을 읽은 뒤 기존 승인 범위에서만 재개한다. 권한 부족·규칙 충돌·실제 미등록 작업은 자동 해소하지 않는다.
6. Rule 9-1/9-3과 대상 노드·추적성·기준선·manifest를 함께 1.6.0으로 동기화한다. 실패 메시지와 필요한 입력은 도구가 안내하되 의미 분류와 승인을 대신하지 않는다.

## 검증·반영

Staging에 전체 거버넌스 검증용 사본을 만들고 변경한다. Rule 변경 후 sync-status의 전체 섹션·hash로 sync-plan을 수행한 다음 실제 정책 본문·digest·map·manifest·기준선을 갱신한다. 정상/부정 CLI 회귀, 기존 기록기/교차 scope 회귀, YAML·해시·문서 검사를 수행한다. 검증된 변경만 루트로 병합하고 동일성·재검증 후 commit·push한다.

보존: 기존 진단 기록과 원본 대화는 유지한다. 롤백은 이번 거버넌스 변경 묶음의 Git revert로 하며 문서·노드·도구·해시를 일부만 되돌리지 않는다. Staging 검증 사본은 검증된 변경 및 diff 증거 보존 후 승인된 범위에서 정리한다.
