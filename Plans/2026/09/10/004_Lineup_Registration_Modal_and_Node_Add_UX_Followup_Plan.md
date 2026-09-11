---
artifact_id: PLAN-20260910-004
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-10T19:54:00.000+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/007_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Task.md
  - ../../../../Reports/2026/09/10/014_Lineup_Registration_UX_Followup_Validation_Report.md
  - ../../../../Reports/2026/09/10/015_Lineup_Registration_UX_Followup_Staging_Report.md
  - ../../../../Reports/2026/09/10/016_Lineup_Registration_UX_Followup_Review_Report.md
---
# [계획서] 장비등록 모달 및 노드 추가 UX 후속 보완

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP`
- 선행 제안: **[제안-047]** 장비등록 라인업 노드 추가 및 관리자 노드 관리
- 상태: **완료 — Review 016 보완 반영 및 Windows 운영 소스 병합 완료 / Git·Linux 적용 별도**

## 1. 배경

제안 047 운영 반영 후 장비등록 모달에 동적 노드 계층이 추가되면서 콘텐츠 높이가 기존보다 크게 늘어날 수 있다. 현재 모달 panel에는 viewport 기준 최대 높이가 없고 form 전체가 함께 늘어나므로 낮은 화면에서는 상단 닫기 또는 하단 저장 버튼에 접근하기 어려울 수 있다.

또한 `renderChildNodes()`가 노드 select를 만들 때 생성 panel도 즉시 mount하여, 사용자가 기존 노드를 고르려는 시점에도 “노드 추가” UI가 함께 노출된다. 이는 기존 항목 선택과 신규 생성이라는 서로 다른 동작을 한 화면에서 동시에 강조하여 혼동을 유발한다.
## 2. 구현 범위

1. 장비등록 모달 높이·스크롤 구조
   - modal panel을 viewport(`100dvh`, `100vh` fallback) 안에 제한한다.
   - header와 footer는 항상 보이는 `shrink-0` 영역으로 둔다.
   - 가운데 입력 본문만 `min-h-0 flex-1 overflow-y-auto`로 스크롤한다.
   - 기존 X, 취소, 임시저장, 정식 저장 동작은 유지한다.
2. 노드 추가 진입 UX
   - 루트/하위 node select에 `➕ 노드 추가` sentinel 항목을 추가한다.
   - sentinel을 선택한 경우에만 해당 parent/depth의 생성 panel을 표시·mount한다.
   - 빈 값 또는 기존 node 선택 시 생성 panel은 숨기고 내용을 제거한다.
   - 기존 node 선택 시 하위 탐색과 현재 node 옵션 선택 동작은 유지한다.
3. 생성 후 재선택
   - APPROVED 생성 결과는 현재 캐시 갱신 후 생성된 경로를 기존 방식으로 자동 재선택한다.
   - 일반 사용자 PENDING 결과는 기존 승인 대기 정책을 유지한다.
4. Staging 회귀
   - 운영 `templates/index.html`의 사본을 Staging 후보로 만들고 후보에서만 수정한다.
   - Node 기반 DOM 상태 전이 시험과 정적 modal 구조 검사를 추가한다.

## 3. 비범위

- 운영 `templates/index.html`, `static/js/lineup_registration.js`, `app.py` 직접 수정
- 운영 DB 또는 Linux 서비스 접근·변경
- `/api/lineup_node` 승인 정책 및 서비스 로직 변경
- 관리자 `lineup_management.html` CRUD 구조 변경
- Proposal 047의 다른 잔여 기능 또는 Proposal 013 시험
## 4. 수용 기준

- 768px 이하를 포함한 낮은 viewport에서 modal panel이 화면 높이를 넘지 않는다.
- header의 X 버튼과 footer의 취소/저장 계열 버튼이 body 스크롤 위치와 무관하게 보인다.
- 입력 필드와 동적 노드/옵션 영역만 독립적으로 세로 스크롤된다.
- 카테고리·제조사 선택 직후에는 노드 생성 입력 panel이 보이지 않는다.
- node select에서 `➕ 노드 추가`를 선택한 경우에만 생성 panel이 나타난다.
- 기존 node를 선택하면 생성 panel이 숨고 기존 하위 탐색·옵션 선택이 유지된다.
- 하위 단계에서도 같은 sentinel UX를 적용하며 생성 요청의 parent_id/depth가 정확하다.
- APPROVED 생성 후 생성된 node 경로 자동 재선택이 유지된다.
- 후보 테스트는 운영 DB·운영 Flask 서비스 없이 통과해야 한다.
- 노드가 0개인 조합에서는 기본 선택 문구가 빈 상태임을 명확히 알리고 `➕ 노드 추가` 선택을 유도한다.
- 장비등록 모달을 열 때마다 `equipmentModalBody.scrollTop`을 0으로 초기화하여 이전 열기의 스크롤 위치가 남지 않는다.

## 5. 검증 계획

Validation 1~8로 사용자 의도, 기존 API 비변경, modal 접근성, node select 상태 전이, rollback, 운영 영향과 AI 메타 경계를 확인한다. Staging 구현 후 `node --test` 기반 후보 회귀와 HTML/JS 정적 계약 검사를 수행하고 Mini-Server governance `validate`/`sync-status`를 재확인한다.

## 6. 롤백 및 다음 단계

Staging 후보는 `Staging/Lineup_Registration_UX_Followup/`에만 둔다. 실패 시 해당 디렉터리와 이번 Plan/Task/Report만 제거하면 되며 운영 소스는 원복할 필요가 없다. Staging 검증 통과 후에도 운영 병합은 별도 사용자 승인 전에는 수행하지 않는다.
## 7. Review 016 타당성 검토 반영

검토 보고서 016의 권고 중 (1) 노드 0개 조합 안내 강화와 (2) 모달 재오픈 시 body scrollTop 초기화는 현재 Staging 후보에 실제로 누락되어 있고 사용성 개선 효과가 명확하므로 운영 병합 전 필수 보완으로 채택한다.

(3) 생성 패널 내부 취소/닫기 버튼은 사용성 제안으로는 타당하지만 `static/js/lineup_registration.js` 비변경이라는 이번 작업 경계와 직접 충돌할 수 있고, 현재 select에서 sentinel 이외 항목을 선택하면 패널을 닫을 수 있으므로 이번 필수 보완에서는 제외한다. 향후 별도 UX 개선 후보로 남긴다.

Staging 보완 후 기존 6개 회귀에 빈 노드 안내 문구와 모달 재오픈 scroll reset 검증을 추가하고, governance validate/sync-status 및 운영 소스 비변경을 재확인한 뒤에만 운영 병합 승인 요청 상태로 복귀한다.
