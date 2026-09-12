---
artifact_id: REPORT-20260912-004
work_id: WORK-20260912-CONTEXT-ROUTING-DIAGNOSIS
created_at: 2026-09-12T17:26:20.527+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/12/003_Context_Routing_Diagnosis_Task.md
---

# Context 차단 원인 비교 검토

## Validation 1~2

1. 거버넌스: ensure 정상, validate 오류/경고 0, sync-status inSync=true. Rule 기준선과 현재 해시는 동일하다. Rule·추적성·라우터와 실행 도구를 읽었다. 정책 변경은 수행하지 않는다.
2. 사용자 의도: 이번 요청은 규칙과 호출 방식의 비교·판단이며, 구현 재개를 승인받은 것으로 확대하지 않는다. 기존 공식 모델명 개선의 스테이징 범위는 유지한다.

## 조사 중 확인 사실

- router의 schema-change에 migration이 등록되어 있다.
- 해당 route는 intent 조건과 path 조건을 모두 만족해야 활성화된다.
- 실패 호출은 Staging 후보 경로와 계획/Task/보고서 경로만 포함했다. app.py 및 templates/** 등의 의미상 원본 경로는 포함하지 않았다.
- 오류 문구는 '미등록 또는 미매칭'인데 AI가 '미등록'이라고 단정했다. 이 단정은 잘못이다.

## Validation 3~8

3. 정적/논리 검증: catalog에서 migration 등록을 확인했다. createContext는 intentMatches AND pathMatches를 요구한다. 같은 세 intent(implement, migration, plan)와 기존 여섯 Staging/문서 경로를 재현하면 exit=1이다. 그 입력을 제거하지 않고 실제 원본 app.py, utils/database_contract.py, templates/lineup_management.html을 추가하면 exit=0이며 schema-change, staging-work가 함께 선택된다. 추가 교차 검증에서는 ui intent와 원본/후보 경로를 함께 선언하여 schema-evolution, data-integrity, frontend-responsive와 Validation 1~8을 모두 포함한 2개 pack이 통과했다. 이는 읽기 전용 라우팅 검증이며 앱 기능 테스트가 아니다.
4. 운영 영향: 원본 경로의 context 선언은 참고·영향 대상 식별이지 해당 파일 수정 승인이나 배포 실행이 아니다. 실제 편집 허용 범위는 여전히 Staging 후보와 승인된 기록으로 제한된다. 관련 없는 app.py 경로를 단순 통과 목적으로 추가하는 것은 허용하지 않는다. 이번 app.py와 템플릿은 이미 확인한 기동 migration 및 모델 표시 의존성이므로 실제 관련 대상이다.
5. 보안/경계: migration을 삭제하거나 일반 implement로 대체해 기술 규칙을 줄이는 방법은 채택하지 않는다. 원본 경로를 자동 추측하여 변환하지 않고 명시적으로 연결한다. 미등록·불명확한 대상, 규칙 충돌, hash 불일치는 계속 차단해야 한다. 실패 사례 재현은 현재 승인된 진단의 부정 검사이며 실패 pack으로 일반 구현을 진행하지 않았다.
6. 복구: Rule, router, 도구 및 앱/DB를 변경하지 않아 정책·운영 rollback은 필요 없다. 검토 기록만 추가한다. 기존 실패·오진 대화도 수정하거나 삭제하지 않고 이 보고서와 현재 답변으로 정정한다.
7. 휴먼 에러: 공통 오류가 '미등록 또는 미매칭'을 구분하지 않아 오진 가능성이 있다. Staging 후보와 원본의 대응 관계를 별도로 표현하는 예시도 현재 README에 명시되지 않았다. 경로 전용 schema-change는 utils/** 또는 Staging/** 단독 입력을 처리하지 않는다. 이는 사용성과 대상 포괄성의 개선 후보지만 이번 승인된 복합 작업은 실제 원본 경로를 함께 선언하면 현 정책으로 처리할 수 있다. fail-closed 자체의 폐지 근거는 아니다.
8. AI 메타: 주원인은 AI의 불완전한 경로 선언과 후속 오진이다. 'migration은 미등록'이라는 이전 설명은 사실과 달라 명시적으로 정정한다. 오류 발생 시 구현을 멈춘 것은 맞지만 원인을 확인하지 않은 설명은 잘못이다. 정책 무결성 검사 통과만으로 정책 전체가 완벽하다고 주장하지 않으며 이번 사례의 해결 방향만 판단한다.

## 대조 결과

| 입력/검사 | 관측 결과 |
|---|---|
| catalog | migration 등록, schema-change의 path 조건 확인 |
| 이전 호출 그대로 | exit 1: 미등록 또는 미매칭 intent: migration |
| 같은 intent·기존 path 유지 + 실제 관련 원본 path 추가 | exit 0: schema-change와 staging-work 선택 |
| DB·UI intent와 원본/후보 대응 경로를 함께 선언 | exit 0: 필수 DB/UI/Staging 노드 포함, 2개 pack 모두 예산 이내 |
| validate / sync-status | 오류·경고 0 / inSync=true |

## 결론과 승인할 방향

이번 차단의 직접 원인은 미등록 작업이 아니라 알려진 작업 분류와 경로의 불일치다. 안전 규칙은 필요한 DB 규칙이 로딩되지 않은 작업을 차단하여 의도대로 작동했다. 따라서 규칙을 완화하거나 migration을 신규 등록할 필요가 없다.

권고 방향은 기존 규칙을 유지하고, catalog 확인 → 관련 intent 전부 식별 → Staging 후보와 실제 원본/영향 경로 동시 선언 → 정규 context 성공 및 모든 pack 읽기 → 기존 승인 범위의 Staging 구현 순서로 재개하는 것이다. context 통과는 승인 범위를 확대하지 않는다. 실제 대응 관계가 없거나 지원되지 않는 작업은 허위 원본 경로로 통과시키지 않고 별도 규칙 검토로 남긴다.

도구의 오류 세분화, Staging 대응 경로 예시, 재진단/재시도 조건 명확화는 선택적 후속 개선으로 분리한다. 이번 검토에서는 정책·도구 변경과 공식 모델명 구현을 실행하지 않았다. 사용자가 판단 방향을 승인한 뒤 스테이징 작업을 재개한다.

## 근거 위치

- AGENTS.md:12–13 및 21: 모든 intent/path 전달, 실패 시 수동 노드 축소 금지.
- .agent-governance/router.yaml:61–64: schema-change의 등록 intent와 원본 path 패턴.
- .agent-governance/tooling/governance-tool.mjs:485–489 및 537: AND 매칭 및 합쳐진 오류 문구.
- .agent-governance/tooling/README.md:27: catalog 사용 안내.
- Rule.md 제9장 및 제11장: 승인 경계·객관적 검토·정합성 차단.

## 후속 기록

위 분석·경로·행 번호는 1.5.1 검토 당시의 근거이며 원문을 보존한다. 이후 사용자는 규칙 완화가 아닌 오해 방지 설계 개선을 명시 승인했다. 이에 Rule 9-1·9-3과 입력 역할·오류 진단·재개 계약을 1.6.0으로 개선했다. 현재 사용법과 검증 결과는 [후속 보고서 005](./005_Governance_Context_Clarity_Report.md)를 따른다. 이전 권고를 현재의 유일한 경로 선언 방식으로 해석하지 않는다.
