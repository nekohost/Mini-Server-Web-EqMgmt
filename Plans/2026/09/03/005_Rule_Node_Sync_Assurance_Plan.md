# Rule↔노드 동기화 보증 강화 계획

## 목적

사용자용 `Staging/Rule.md`의 변경을 모든 AI가 같은 절차로 노드에 반영하고, 반영 누락·섹션 삭제·번호 변경·동시 수정 충돌을 활성화 전에 차단한다.

## 구현 범위

1. Rule 섹션의 승인 기준선 해시를 `traceability/rule-section-baseline.yaml`에 보관한다.
2. `sync-status` 명령으로 현재 Rule과 기준선을 비교해 변경·추가·삭제 섹션과 영향 노드를 출력한다.
3. 각 노드 front matter에 연결 Rule 섹션의 집계 digest를 추가하고, `validate`가 최신 기준선과 대조한다.
4. `sync-plan`에 기준 Rule SHA-256 precondition을 추가해 stale 계획을 차단하고, 섹션·노드 digest 갱신값을 출력한다.
5. 세 제품 진입점과 `governance.rule-sync`를 Staging 루트 기준의 공통 명령·순서로 통일한다.
6. 변경·삭제·번호 변경·해시만 갱신한 누락·플랫폼 지시서 정합성의 회귀 테스트를 추가한다.

## 비범위

- 정책 의미를 자동 생성하거나 노드 본문을 자동 덮어쓰지 않는다.
- 운영 루트, 실제 DB, 운영 서버는 변경하지 않는다.
- Gemini·Claude 런타임을 이 PC에서 실제 호출하지 않는다. 대신 각 진입점과 필요한 Node/npm 준비 조건을 정적 smoke 검사한다.

## 안전 원칙

- `sync-status`가 변경을 보고하면 모든 변경 섹션을 포함한 `sync-plan`만 허용한다.
- 새·삭제·번호 변경 섹션이 기존 mapping만으로 결정되지 않으면 fail-closed 한다.
- `validate --expected-rule-sha`는 계획 수립 뒤 Rule이 바뀐 stale 작업을 차단한다.
- 기준선 및 node digest 갱신은 대상 노드 본문·human map·manifest와 동일한 구조화 편집 변경 단위로만 수행한다.
