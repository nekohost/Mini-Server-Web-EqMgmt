---
artifact_id: REPORT-20260910-016
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-10T20:22:00+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md
  - ../../../../Tasks/2026/09/10/007_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Task.md
  - ../../../../Reports/2026/09/10/014_Lineup_Registration_UX_Followup_Validation_Report.md
  - ../../../../Reports/2026/09/10/015_Lineup_Registration_UX_Followup_Staging_Report.md
---
# [검토 보고서] 장비등록 모달 및 노드 추가 UX 후속 보완 구현물 검토

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP`
- 검토 대상:
  - 계획서: `Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md`
  - Staging 후보: `Staging/Lineup_Registration_UX_Followup/templates/index.html`
  - 회귀 테스트: `Staging/Lineup_Registration_UX_Followup/tests/test_lineup_registration_ux.mjs`
- 판정: **조건부 승인 가능 (Ready with Minor Enhancements) — 기능·안전성 검증 통과 / 세부 사용성 보완 권장사항 3건 제시**

---

## 1. 검토 목적 및 배경

제안 047(장비등록 라인업 노드 추가 및 관리자 노드 관리)의 운영 반영 후 발생한 장비등록 모달의 높이 과다 및 노드 생성 패널 상시 노출 혼선 문제를 해결하기 위해 수립된 후속 계획(Plan 004)과 Staging 구현물을 검토한다.
본 검토는 (1) 계획서 의도대로 구현되었는지, (2) 미흡한 점은 없는지, (3) 운영 반영 시 장애나 부작용 위험은 없는지를 중점적으로 판단한다.

---

## 2. 계획 대비 구현 정합성 검토 (의도 부합성)

Plan 004에 정의된 핵심 요구사항 2건과 세부 수용 기준이 Staging 후보에 정확히 반영되었음을 확인했다.

1. **장비등록 모달 Viewport 고정 및 스크롤 구조**:
   - `equipmentModalPanel`에 `max-height: calc(100vh - 2rem); max-height: calc(100dvh - 2rem);` 적용 확인.
   - `equipmentModalHeader`와 `equipmentModalFooter`에 `shrink-0` 적용으로 화면 상단 닫기(X) 버튼 및 하단 취소/저장 버튼 상시 노출 확인.
   - `equipmentModalBody`에 `min-h-0 flex-1 overflow-y-auto p-6` 적용으로 긴 입력 폼 본문만 독립적으로 세로 스크롤되도록 분리 완료.
2. **노드 추가 진입 UX 개선 (조건부 마운트)**:
   - 카테고리/제조사 선택 직후에는 노드 생성 패널이 노출되지 않도록 차단(`panel.className = 'hidden'`).
   - 루트/하위 드롭다운에 `➕ 새 최상위 노드 추가` / `➕ 새 하위 노드 추가` sentinel(`__add_node__`) 추가.
   - 사용자가 해당 sentinel을 명시적으로 선택한 경우에만 `nodeRegistration.mount()`가 실행되고 패널이 노출됨.
   - 기존 노드를 선택하거나 빈 선택으로 돌아갈 경우 `hideNodePanel()`을 통해 패널을 즉시 숨기고 DOM 자식 요소를 안전하게 정리(`replaceChildren()`)함.
3. **승인 후 자동 재선택 및 회귀 테스트**:
   - 노드 생성 승인(APPROVED) 후 기존 캐시 갱신 및 경로 재선택 로직(`onApproved`)이 정상 연동됨.
   - Staging DOM/정적 회귀 테스트(`test_lineup_registration_ux.mjs`) 6/6 통과 확인.

---

## 3. 식별된 미흡점 및 개선 권장사항

치명적인 기능 버그나 회귀 오류는 없으나, 세부 사용성(UX) 및 방어적 코드 관점에서 다음 3건의 미흡점이 식별되었다.

1. **미흡점 1 (노드가 0개인 카테고리/제조사 선택 시 안내 부족)**:
   - 특정 분류에 등록된 모델이 0개인 경우, 드롭다운에 `[ -- 모델 선택 -- ]`과 `[ ➕ 새 최상위 노드 추가 ]`만 포함됨.
   - 사용자가 드롭다운을 직접 열어보기 전에는 모델이 없는 상태인지, 데이터 로딩 중인지 시각적으로 구별하기 어려움.
   - *권장*: `nodes.length === 0`일 때 드롭다운 기본 텍스트를 `-- 등록된 모델 없음 (➕ 모델 추가 선택) --` 등으로 표시하여 사용자의 능동적 선택을 유도.
2. **미흡점 2 (모달 재오픈 시 스크롤 위치 리셋 누락)**:
   - `openModal()` 함수에서 `form.reset()`과 dynamicTreeContainer 초기화를 수행하지만, 분리된 스크롤 컨테이너인 `equipmentModalBody`의 `scrollTop = 0` 초기화 코드가 없음.
   - 긴 장비 정보를 조회/수정한 뒤 모달을 닫고 다시 신규 등록 모달을 열 때, 브라우저 렌더링 타이밍에 따라 이전 스크롤 위치가 잔존할 가능성이 있음.
   - *권장*: `openModal()` 실행 시점에 `const body = document.getElementById('equipmentModalBody'); if (body) body.scrollTop = 0;` 명시적 리셋 추가.
3. **미흡점 3 (생성 패널 내부의 취소/닫기 버튼 부재)**:
   - 사용자가 `➕ 새 노드 추가`를 선택하여 생성 패널이 열린 후 마음이 바뀌었을 때, 패널 내부에는 `[ 노드 추가 ]` 버튼만 존재함.
   - 패널을 닫으려면 상단 드롭다운을 다시 열어 다른 항목을 선택해야 하므로 직관성이 다소 떨어짐. (단, 본 과제의 비범위가 `static/js/lineup_registration.js` 미수정이므로 이번 병합을 차단할 사유는 아니며 향후 개선 과제로 권장).

---

## 4. 운영 반영 시 리스크 및 호환성 판단

- **백엔드 무결성 (Zero Risk)**:
  - Python 백엔드(`app.py`, `utils/lineup_routes.py`, `utils/lineup_node_service.py`), SQLite DB 스키마, 결재 승인 정책 변경이 전혀 없음.
  - `__add_node__`는 프론트엔드 전용 상태값이며, 서버로 제출되지 않고 `getSelectedOptionData()`에서 차단되므로 유효하지 않은 데이터가 서버에 인입될 위험 없음.
- **기존 프론트엔드 호환성 (안전)**:
  - 기존 폼 필드 ID(`equipmentModal`, `equipmentForm`, `EquipmentId`, `Name` 등)가 100% 보존됨.
  - 모달 열기/닫기, 임시저장 토글, 정식 저장 검증 로직과의 충돌 없음.
  - 신규 적용된 CSS 유틸리티(`shrink-0`, `min-h-0`, `flex-1`, `overflow-y-auto`)는 프로젝트 내 Tailwind CSS 설정과 완벽히 호환됨.
- **배포 및 롤백 용이성 (우수)**:
  - 운영 반영 대상은 `templates/index.html` 단 1개 파일로 국한됨.
  - 문제 발생 시 `git checkout templates/index.html`로 즉각적인 무손실 롤백 가능.

---

## 5. Validation 1~8 종합 판정

| 단계 | 검증 영역 | 결과 | 비고 |
| :---: | :--- | :---: | :--- |
| **1** | 거버넌스 준수성 | **통과** | Staging 격리 검증 완료, 운영 소스 직접 수정 없음 |
| **2** | 사용자 의도 부합성 | **통과** | 모달 스크롤 제약 해소 및 명시적 노드 추가 동선 충족 |
| **3** | 정적 논리 완결성 | **양호** | Flexbox 분리 및 DOM cleanup 완결 (스크롤 리셋 보완 권장) |
| **4** | 운영 영향 및 호환성 | **통과** | API·DB 비변경, 기존 등록·수정 스크립트 충돌 없음 |
| **5** | 보안 및 예외 처리 | **통과** | Sentinel 격리, 미선택 시 저장 차단, XSS 방어 유지 |
| **6** | 롤백 및 가역성 | **통과** | 단일 템플릿 파일 변경으로 즉시 원복 가능 |
| **7** | 휴먼 에러 및 UX | **양호** | 혼선 유발 패널 차단 (노드 0개 안내 보완 권장) |
| **8** | AI 메타 거버넌스 | **통과** | Mock DOM 테스트 범위 명시, 실브라우저 렌더링 한계 정직 기술 |

---

## 6. 결론 및 향후 처리 방안

본 Staging 구현물은 운영 시스템에 악영향을 주지 않으며, 제기되었던 모달 스크롤 및 노드 추가 혼선 문제를 효과적으로 해결한다.

- **권장 조치**:
  운영 병합 전, Staging 후보(`Staging/Lineup_Registration_UX_Followup/templates/index.html`)에 **(1) `openModal()` 스크롤 초기화(`scrollTop = 0`)** 및 **(2) `nodes.length === 0`일 때의 드롭다운 안내 문구 보강**을 추가 적용한 후 최종 운영 반영을 진행하는 것을 권장한다.
- **운영 병합**: 사용자 명시 승인 후 `Staging/.../templates/index.html`을 `templates/index.html`로 반영한다.

