---
artifact_id: REPORT-20260910-017
work_id: WORK-20260910-LINEUP-REGISTRATION-UX-FOLLOWUP
created_at: 2026-09-10T20:32:42.000+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/004_Lineup_Registration_Modal_and_Node_Add_UX_Followup_Plan.md
  - ../../../../Tasks/2026/09/10/008_Lineup_Registration_UX_Followup_Production_Merge_Task.md
  - ../../../../Reports/2026/09/10/016_Lineup_Registration_UX_Followup_Review_Report.md
---
# [운영 반영 보고서] 장비등록 모달 및 노드 추가 UX 후속 보완

- 작성일: 2026-09-10
- 판정: **Windows 운영 소스 반영 완료**
- Git commit/push: 미수행
- Linux 서비스 적용/실브라우저 검증: 미수행

## 1. Review 016 반영

Review 016의 권고 중 빈 노드 조합 안내 강화와 모달 재오픈 시 `equipmentModalBody.scrollTop = 0` 초기화를 필수 보완으로 채택했다. 생성 패널 내부 취소 버튼은 유효한 후속 UX 아이디어이나 이번 필수 범위에서는 제외했다.

보완 후 Staging 회귀는 **8/8 PASS**했다.## 2. 운영 반영 범위

운영 `templates/index.html`을 검증된 Staging 후보와 동일하게 반영했다. 함께 갱신한 `tests/test_proposal047_registration.mjs`는 새 modal/sentinel UX 계약을 검증하는 8개 테스트로 확장했다.

운영 템플릿과 Staging 후보의 SHA-256은 반영 직후 동일했다.

- 운영/후보 template: `0A59BAFDD2EA7E2E12FB3F0177C7576DD360344C3925B8B56B99B2454CF4C886`
- 운영/후보 UI test: `1D3809C4959A04D88B15C627132AC60AEDB3CA82AF4635349C0B84B4112A562E`

## 3. 검증 결과

- 운영 UI Node 회귀: **8/8 PASS**
- Mini-Server governance: `1.4.0`
- governance errors: `0`
- governance warnings: `0`
- `inSync=true`

Python backend 회귀는 Windows PC에 실제 Python runtime이 설치되어 있지 않고 WindowsApps stub만 존재하여 실행하지 못했다. 이번 변경은 Python/API/DB 파일을 수정하지 않았으며 Linux 기능 검증은 별도 서버 적용 단계에서 수행한다.
## 4. Cleanup 후 최종 게이트

운영 반영 완료 후 `Staging/Lineup_Registration_UX_Followup/` 후보를 제거했다. 작업용 rollback과 일회성 helper도 제거했다.

Cleanup 이후 운영 `tests/test_proposal047_registration.mjs`를 다시 실행하여 **8/8 PASS**를 확인했다. `governance-tool validate`와 `sync-status`는 각각 errors/warnings 0, `inSync=true`였고 `git diff --check`도 통과했다.

현재 변경 범위는 이번 Plan/Task/Report/index와 운영 `templates/index.html`, 동반 UI 회귀 테스트로 한정된다. Git commit/push와 Linux 서비스 적용은 수행하지 않았다.