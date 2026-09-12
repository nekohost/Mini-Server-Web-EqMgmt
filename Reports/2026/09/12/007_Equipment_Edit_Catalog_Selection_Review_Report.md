---
artifact_id: REPORT-20260912-007
work_id: WORK-20260912-EQUIPMENT-EDIT-CATALOG-SELECTION
created_at: 2026-09-12T18:58:20.357+09:00
related_artifacts:
  - ../../../../Plans/2026/09/12/004_Equipment_Edit_Catalog_Selection_Plan.md
  - ../../../../Tasks/2026/09/12/006_Equipment_Edit_Catalog_Selection_Task.md
---

# 장비 수정 카탈로그 선택 복원 검토

## 근거

- `GET /api/equipment`는 장비별 `CategoryId`, `ManufacturerId`, `LineupNodeId`, `OptionId`와 표시명을 반환한다.
- `openModal(id)`는 `LineupApp.init(true)` 후 폼과 동적 선택기를 비우고 장비 일반 필드만 복원한다.
- 카탈로그 위치에는 실제 복원 코드 대신 `기존 장비 수정 모드 트리 바인딩은 별도 제공 예정입니다.` 경고가 있다.
- `LineupApp`의 `selectedNodeId`와 캐시는 IIFE 내부 상태이며 공개 API에는 복원 함수가 없다.
- PUT API는 `OptionData`가 없으면 transaction에서 읽은 기존 `option_id`를 유지하므로, 미변경 저장 시 이를 재전송할 필요가 없다.

## Validation 1~8

1. 거버넌스: recorder ensure와 governance 1.6.0 validate가 통과했고 implement/fix/frontend/ui/ux context의 전체 pack을 읽었다. 이번 범위는 Staging 후보만 수정하고 운영 코드는 수정하지 않는다.
2. 사용자 의도: 수정 화면에 현재 장비의 실제 추종 카탈로그를 순서대로 표시하는 것을 목표로 한다. 단일 모델명 표시가 아니라 카테고리·제조사·전체 노드 경로·옵션의 편집 상태를 복원한다.
3. 논리: 기존 한 번의 트리 덤프와 목록 응답만 사용하므로 정상 장비에는 추가 네트워크 호출이나 N+1 쿼리가 없다. 부모 역추적은 순환 집합과 깊이 50으로 종료한다. 목록과 트리 사이의 갱신 경쟁은 미변경 `OptionData` 생략으로 완화한다.
4. 운영 영향: 기본 구현은 `templates/index.html`과 회귀 테스트에 한정된다. API·DB·라우트 우선순위는 바꾸지 않는다. 승인 상태가 아닌 기존 연결을 승인 트리에 억지로 삽입하지 않는다.
5. 보안: 장비 수정 권한·CSRF·서버의 `require_equipment_option` 검사를 그대로 사용한다. DOM 표시는 `Option`/`textContent` 또는 기존 escape 경로를 사용하고, 클라이언트 ID는 권한 근거로 신뢰하지 않는다.
6. 복구: DB 변경이 없고 미변경 저장은 기존 option 연결을 보존한다. 복원 실패 시 다른 옵션으로 자동 치환하지 않으며, 코드 롤백도 데이터 역변환 없이 가능하다.
7. 휴먼 에러: 복원 중 이벤트와 실제 사용자 변경을 분리한다. 사용자가 변경을 시작한 뒤 불완전한 경로는 저장 차단하며, 현재 연결을 불러오지 못한 경우 원인·보존 여부·재시도를 화면에 안내한다.
8. AI 메타: 현재 작업자는 Codex이며 계획에 따라 Staging 후보와 자동 검증을 작성했다. 증상을 공식 모델명 기능이나 DB 결함으로 과장하지 않았고 신규 제안 번호를 만들지 않았다.

## 결론

이 결함은 제안 047 구현 당시 의도적으로 남겨진 수정 모달 바인딩 공백이다. 기존 공식 모델명 계획과 병합하면 원인과 완료 기준이 흐려지므로 제안 047의 별도 후속 버그 계획으로 기록하는 것이 적절하다. 정상 승인 데이터는 프런트엔드 복원만으로 해결할 수 있고 DB migration은 필요 없다. 다만 임시·승인대기·손상 연결을 자동 대체하지 않는 보존 경로와 미변경 option 재전송 방지가 함께 구현되어야 한다.

## Staging 구현 및 검증 결과

2026-09-12T19:10:56.314+09:00에 `Staging/Equipment_Edit_Catalog_Selection_20260912/` 후보를 완성했다.

- `templates/index.html`: 카테고리·제조사·가변 깊이 노드 경로·옵션 복원, 사용자 변경 추적, 복원 실패 시 기존 연결 보존, 수정 중 신규 루트 선택 차단, 접근 가능한 상태 안내를 구현했다.
- `tests/test_proposal047_registration.mjs`: 기존 8건에 복원·중간 노드 옵션·변경 payload·누락/불일치 보존·순환 차단·모달 연결 6건을 추가했다.
- `tools/check_equipment_edit_catalog_static.mjs`: 인라인 JavaScript 구문과 복원/제출/깊이 제한/접근성 연결 계약을 검사한다.
- `node --test Staging/Equipment_Edit_Catalog_Selection_20260912/tests/test_proposal047_registration.mjs`: 14/14 통과.
- `node Staging/Equipment_Edit_Catalog_Selection_20260912/tools/check_equipment_edit_catalog_static.mjs`: 통과, 인라인 스크립트 1개 구문 정상.
- 운영 `app.py`의 목록 쿼리는 네 ID를 반환하고, PUT은 `OptionData`가 없으면 transaction에서 읽은 기존 `option_id`를 유지하는 계약임을 재확인했다. 백엔드 변경은 필요하지 않았다.
- 운영 원본 `templates/index.html`과 `tests/test_proposal047_registration.mjs`의 SHA-256은 각각 `8CB66729694E04C47BE457A8006B9A5E715AB5ACB5278C6BC08510ABA11F706E`, `12BC31BF71C38EB21634644AB1021B0BA479AB49045C854889455B32E36D5A3C`로 작업 전 기준과 동일하다.

결론은 **Staging 적합**이다. 다음 단계는 사용자 승인 후 운영 원본 병합, 운영 소스 정적 재검증, Linux Python 통합 회귀와 실제 수정 화면 확인이다.

## 운영 소스 병합 및 릴리스 결과

2026-09-12T20:23:47.021+09:00에 사용자의 명시적 승인에 따라 Staging 후보를 운영 `templates/index.html`과 `tests/test_proposal047_registration.mjs`에 병합했다.

- 병합 직후 두 운영 파일의 SHA-256이 각 Staging 후보와 일치함을 확인했다.
- 운영 경로의 장비 수정 복원 회귀는 14/14 통과했다.
- `tests/*.mjs` 전체 회귀는 31/31 통과했고 변경된 인라인 JavaScript 구문도 정상이다.
- `git diff --check`는 오류 없이 통과했다. 출력된 LF/CRLF 문구는 저장소의 Windows checkout 변환 예고이며 공백 오류가 아니다.
- DB 스키마, API 라우트, 서버 환경설정, 장비 데이터는 변경하지 않았다.
- 승인된 후보의 운영 병합 후 `Staging/Equipment_Edit_Catalog_Selection_20260912/` 임시 파일을 정리했다.
- 초기 context에서 Git 메타데이터를 일반 파일 대상 `.git/**`로 선언해 `INVALID_PATH`가 발생했다. catalog 근거에 따라 일반 대상에서만 제거한 뒤 validate와 전체 context를 다시 통과했고, 규칙 노드를 수동 축소하지 않았다.

Validation 1~8의 기존 결론은 운영 병합 후에도 유지된다. Linux 서비스 pull·Python 통합 회귀·인증 브라우저 확인은 이 Git 원격 반영 이후의 별도 실행 검증이며, 현재 릴리스는 Windows 운영 소스와 원격 저장소 반영까지를 완료 범위로 한다.
