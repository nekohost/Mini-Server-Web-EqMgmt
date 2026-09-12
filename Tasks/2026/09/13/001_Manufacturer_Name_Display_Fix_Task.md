---
artifact_id: TASK-20260913-001
work_id: WORK-20260913-MANUFACTURER-DISPLAY
created_at: 2026-09-13T00:18:49.155+09:00
related_artifacts:
  - ../../../../Plans/2026/09/13/001_Manufacturer_Name_Display_Fix_Plan.md
  - ../../../../Reports/2026/09/13/001_Manufacturer_Name_Display_Fix_Report.md
---

# 제조사명 화면 표시 회귀 수정 Task

- [x] recorder ensure와 governance validate 실행
- [x] 결함 원인 및 화면 전용 수정 범위 확정
- [x] Plan 작성과 사전 Validation 1~8 기록
- [x] Staging 표시 함수 및 합성 데이터 테스트 작성
- [x] Staging 테스트 통과 (5/5)
- [x] 운영 `templates/index.html` 병합
- [x] 운영 `templates/dashboard.html` 병합
- [x] `tests/test_release_frontend.mjs` 회귀 계약 보강
- [x] 운영 정적·회귀 테스트 및 governance validate 통과 (Node 32/32)
- [x] Staging 임시 산출물 정리
- [ ] Report에 Validation 1~8 및 배포 결과 기록
- [ ] Git 커밋 및 origin/main push
- [ ] 백업 Linux 서버 pull·테스트·서비스 재시작·HTTP 확인

## 중단 조건

- 화면 수정만으로 제조사명을 얻을 수 없는 경로가 발견됨
- 기존 XSS 방어 또는 공식 모델명 fallback을 보존할 수 없음
- Staging·운영 테스트 또는 governance validate 실패
- 백업 서버 작업 트리의 예상하지 못한 변경으로 fast-forward pull이 불가능함
