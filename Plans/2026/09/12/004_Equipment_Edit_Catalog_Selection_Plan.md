---
artifact_id: PLAN-20260912-004
work_id: WORK-20260912-EQUIPMENT-EDIT-CATALOG-SELECTION
created_at: 2026-09-12T18:58:20.357+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/12/006_Equipment_Edit_Catalog_Selection_Task.md
  - ../../../../Reports/2026/09/12/007_Equipment_Edit_Catalog_Selection_Review_Report.md
  - ../../../../docs/proposal047-operation.md
---

# 장비 수정 카탈로그 선택 복원 계획

상태: Staging 검증·운영 소스 병합·Git 원격 반영 완료. Linux 서비스 적용과 인증 브라우저 확인은 별도 운영 단계다. 제안 047의 장비 수정 UX 결함을 다루는 별도 후속 계획이며 신규 제안 번호나 DB migration을 만들지 않는다.

## 원인과 목표

`GET /api/equipment`는 수정에 필요한 `CategoryId`, `ManufacturerId`, `LineupNodeId`, `OptionId`를 이미 반환한다. 그러나 `openModal(id)`는 기본 장비 필드만 채운 뒤 카탈로그 복원 대신 `기존 장비 수정 모드 트리 바인딩은 별도 제공 예정` 경고만 출력한다. `LineupApp`에도 외부에서 안전하게 호출할 복원 함수가 없어 카테고리·제조사·노드·옵션 선택란이 비어 있다.

수정 모달을 열면 현재 장비가 연결된 카테고리와 제조사, 루트부터 실제 대상 노드까지의 전체 경로, 최종 `OptionId`가 순서대로 선택되어야 한다. 사용자가 선택을 바꾸지 않으면 기존 연결을 그대로 보존하고, 명시적으로 카탈로그를 변경한 경우에만 새 선택을 PUT payload에 포함한다.

## 설계

1. `LineupApp`에 `restoreSelection(item)`과 현재 선택 상태 조회 기능을 추가한다. 복원 중 이벤트와 사용자 변경을 구분하는 `restoring`, `selectionDirty`, `originalOptionId`, `preserveExisting` 상태를 모달마다 초기화한다.
2. 강제 갱신된 `nodeCache_v2`에서 `LineupNodeId`의 부모를 역추적한다. 방문 ID 집합과 최대 깊이 50으로 순환·손상 계층을 차단하고, 각 노드의 카테고리·제조사가 장비의 루트 값과 일치하는지 확인한다.
3. 카테고리·제조사를 먼저 선택하고 `onRootChange()`로 첫 노드 선택기를 만든다. 계산한 경로를 루트→대상 순서로 선택하면서 각 행이 존재하고 해당 노드 옵션이 실제로 포함되는지 확인한다. 마지막에 `OptionId`를 선택하고 `onOptionChange()`와 제출 잠금 상태를 갱신한다.
4. 복원 중 발생한 change 이벤트는 `selectionDirty`를 켜지 않는다. 사용자가 카테고리·제조사·노드·옵션을 직접 변경하면 그 시점부터 기존 연결 보존 상태를 해제하고 완전한 새 선택을 요구한다.
5. 수정 저장에서 카탈로그가 변경되지 않았으면 `OptionData`를 `null`로 전송해 서버가 transaction 시점의 기존 `option_id`를 유지하게 한다. 새 옵션 또는 다른 기존 옵션을 명시적으로 선택했을 때만 현재 `OptionData`를 전송한다. 이는 오래된 목록 데이터가 더 최신의 연결을 되돌리는 것을 방지한다.
6. 승인 트리에서 현재 연결을 찾을 수 없는 임시저장·승인대기·손상 상태는 다른 항목으로 자동 대체하지 않는다. 모달에 현재 `FullModelName`·`OptionName`을 읽기 전용으로 표시하고 `preserveExisting=true`로 기본 정보 수정은 허용한다. 사용자가 카탈로그 변경을 시작하면 정상 승인 항목을 끝까지 선택하기 전에는 정식 저장을 차단한다.
7. 복원 실패와 트리 API 실패는 콘솔 경고로 끝내지 않고 모달 안에 재시도 가능한 안내를 표시한다. 이전에 열었던 장비의 선택 상태는 다음 모달에 남기지 않는다.

## 변경 예상 범위

- `templates/index.html`: 선택기 상태 모델, 경로 복원 함수, 수정 모달 연결, 현재 연결 안내 및 제출 payload 분기.
- `tests/test_proposal047_registration.mjs`: 복원 알고리즘과 상태 전이 DOM 회귀.
- `tests/test_release_api.py`: `GET /api/equipment`의 네 ID 계약과 PUT에서 `OptionData` 누락 시 기존 연결 보존 회귀. API 구현 변경은 테스트가 현재 계약의 누락을 발견할 때만 검토한다.
- Staging 후보: `Staging/Equipment_Edit_Catalog_Selection_20260912/`. 운영 원본은 Staging 검증과 사용자 승인 전 수정하지 않는다.

DB 스키마, 노드·옵션 데이터, 권한 정책, 신규 라우트와 외부 라이브러리는 변경하지 않는다.

## 검증 기준

- 1·2·3·가변 깊이 경로가 순서대로 선택되고 기존 옵션이 선택된다.
- 자식이 있는 중간 노드 자체에 연결된 옵션도 복원된다.
- 연속해서 서로 다른 장비를 열거나 수정→닫기→신규등록을 해도 상태가 섞이지 않는다.
- 같은 옵션을 유지한 기본 정보 수정은 `OptionData=null`이며 DB 연결을 바꾸지 않는다.
- 사용자가 루트·노드·옵션을 변경하면 dirty 상태가 되고 불완전 선택은 저장되지 않는다.
- 누락 노드, 누락 옵션, 다른 노드 소속 옵션, 순환, 깊이 초과, API 실패는 자동 대체 없이 안내·보존 경로로 종료된다.
- 임시저장과 승인대기 연결은 현재 값을 잃지 않으며, 정식 전환 시 승인된 완전 선택을 요구한다.
- 기존 신규 등록, 노드 추가, 공식 모델명 표시, 소유자 변경, 공개 여부 및 CSRF·권한 동작이 회귀하지 않는다.

## 완료 조건과 복구

Staging 정적 검사와 JavaScript 상태 전이 회귀를 통과하고 사용자가 결과를 승인한 뒤 운영 소스에 병합한다. Linux Python 회귀와 인증 브라우저 확인은 Git 원격 반영 후 실제 서비스 적용 단계에서 수행하며, 아직 수행되지 않았다는 이유로 승인된 운영 소스 병합과 push를 차단하지 않는다. 코드 변경은 프런트엔드와 테스트에 한정되며 DB rollback은 필요 없다. 병합 후 문제가 생기면 해당 커밋을 되돌려 기존 수정 동작으로 복귀할 수 있고 장비의 기존 `option_id`는 변경되지 않는다.
