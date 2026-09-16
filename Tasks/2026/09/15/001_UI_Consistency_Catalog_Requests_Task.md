---
artifact_id: TASK-20260915-001
work_id: WORK-20260915-UI-CONSISTENCY-CATALOG-REQUESTS
created_at: 2026-09-15T14:04:01.054+09:00
related_artifacts:
  - ../../../../Plans/2026/09/15/001_UI_Consistency_Catalog_Requests_Plan.md
  - ../../../../Reports/2026/09/15/001_UI_Consistency_Catalog_Requests_Report.md
  - ../../../../Reports/2026/09/16/001_Catalog_UI_Backup_Release_Report.md
---
# UI 공통 규격·카탈로그 신청 Task — 완료

- [x] 실제 Git/원격 기준·다중 AI 변경 여부 확인
- [x] ChatGPT bootstrap·recorder·governance·전체 context 확인
- [x] 나의/공개 장비 공유 템플릿, 카드 renderer, 결재/노드 API 조사
- [x] Plan 및 Validation 1~8 선행 기록
- [x] Staging 후보: 배지/버튼 규격·포털/관리자 카드 배열
- [x] Staging 후보: 공통 카테고리·제조사·노드 신청 폼 및 서버 처리
- [x] 정적/서비스/브라우저 모의 검증 및 증거 보존
- [x] 사용자 명시 승인 후 Windows 운영 소스 병합
- [x] 운영 소스 회귀·영구 테스트·FEATURES 갱신 및 Staging 정리
- [x] 기능 commit6862c78 및 후속 기록 commit/push
- [x] PROGRAMDATA 누락 보완으로 기존 SSH agent 접속 확인(키/서버 인증 변경 없음)
- [x] 실제 Jinja 전체 브라우저26건 통과(구 포털 기대값 정정)
- [x] 서버 운영 코드·DB·Git 상태 보존 및 지정30경로 stash 유지
- [x] 백업 Linux 서버 ff-only pull 및 전체65개 운영 파일 hash 확인
- [x] Linux 격리 전체 회귀99건 및 추가 카탈로그 HTTP19건 통과
- [x] 실제 웹앱 PID91637 →119262 재시작, 실제 HTTPS/정적/API/DB 검증
- [x] 최종 Report/FEATURES 상태 조율

배포 완료: 2026-09-16. 코드 적용 SHA5b60d5b63b7f46a20b0817fa44ecfae7e6231c75. 기존 단독 Python 실행을 유지한다. 운영 사용자 신청/승인 쓰기·실기기 검증은 하지 않았으며, 서버 .venv.incomplete-20260907/와 private 복구본/stash는 보존했다.
