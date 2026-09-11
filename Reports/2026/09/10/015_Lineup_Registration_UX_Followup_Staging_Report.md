---
artifact_id: REPORT-20260910-015
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-10T20:02:00.000+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md
  - ../../../../Tasks/2026/09/10/007_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Task.md
  - ../../../../Reports/2026/09/10/014_Lineup_Registration_UX_Followup_Validation_Report.md
---
# [Staging 보고서] 장비등록 모달 및 노드 추가 UX 후속 보완

- `work_id`: `WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP`
- 상태: **Staging 구현·격리 검증 완료**
- 운영 병합: **미수행 — 별도 승인 필요**

## 1. Staging 산출물

- `Staging/Lineup_Registration_UX_Followup/templates/index.html`
- `Staging/Lineup_Registration_UX_Followup/tests/test_lineup_registration_ux.mjs`
- `Staging/Lineup_Registration_UX_Followup/README.md`

운영 `templates/index.html` 사본을 기준으로 두 UX 변경만 후보에 적용했으며 `app.py`, lineup service/routes, `static/js/lineup_registration.js`는 수정하지 않았다.
## 2. 구현 결과

### 2-1. Viewport 대응 modal

- modal panel에 `100vh` fallback과 `100dvh` 기준 최대 높이를 적용했다.
- panel/form을 flex column으로 구성했다.
- `equipmentModalHeader`와 `equipmentModalFooter`는 `shrink-0`로 유지한다.
- `equipmentModalBody`만 `min-h-0 flex-1 overflow-y-auto`로 스크롤한다.
- 따라서 X/취소/임시저장/저장 버튼은 body 콘텐츠 길이와 독립적으로 접근 가능하다.

### 2-2. 명시적 node add 선택

- 각 root/child select의 마지막에 `__add_node__` sentinel을 추가했다.
- 카테고리·제조사 선택 직후 또는 기존 node 선택 시 생성 panel은 mount하지 않는다.
- `➕ 새 최상위 노드 추가` 또는 `➕ 새 하위 노드 추가`를 선택한 경우에만 해당 parent/depth의 panel을 mount한다.
- sentinel에서 벗어나면 panel을 숨기고 내부 입력을 제거한다.
- 기존 node 선택 시 하위 탐색, parent node의 기존 옵션 선택, 생성 후 자동 재선택은 유지한다.
## 3. 검증

Staging DOM/정적 회귀는 **6/6 PASS**했다.

1. modal header/footer 고정 및 body-only scroll 구조
2. 카테고리·제조사 선택만으로 add panel 미노출
3. root add sentinel 선택 시 root panel 표시
4. 기존 node 선택 시 panel 미노출 및 child sentinel의 정확한 parent/depth
5. APPROVED 생성 후 생성 node 자동 재선택 및 신규 option 귀속
6. 자식이 있는 node의 기존 option 선택과 root 변경 초기화 회귀

Mini-Server governance는 `1.4.0`, errors `0`, warnings `0`, `inSync=true`를 유지했다. 운영 주요 파일 `app.py`, `templates/index.html`, `static/js/lineup_registration.js`, `utils/lineup_routes.py`, `utils/lineup_node_service.py`에는 tracked diff가 없다.

## 4. 한계 및 다음 단계

이번 결과는 Windows Staging의 격리 DOM/정적 검증이다. 실제 브라우저의 다양한 viewport, Linux 서비스 및 운영 DB를 검증한 결과로 간주하지 않는다. 운영 소스 병합은 사용자 별도 승인 후 Plan 004 후보와 운영 파일의 diff를 다시 확인하여 진행한다.