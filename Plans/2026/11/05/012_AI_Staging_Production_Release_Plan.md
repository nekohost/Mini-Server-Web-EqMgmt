---
artifact_id: PLAN-20261105-012
work_id: RELEASE-20261105-AI-CSV-LAYOUT
owner: Codex
status: approved-for-release
---

# 검증된 AI Staging 운영 배포

사용자는007 CSV 팝업·009 화면 높이/scrollbar·010 모델 선택 접기까지 현재 Staging 전체의 실제 운영 반영을 승인했다. 신규011 상단 아이콘/상태 색상·메뉴 두 줄은 미실현 계획으로만 보존한다.

1. 현재 후보11개 source/보조와13개 원문 ZIP·55화면/3543개 검사 증거를 확인하고, 기존 root11개 SHA/서버 commit·프로세스·진행 job을 재확인한다. 기존 다른 dirty9개는 보존한다.
2. 신규 미실현 계획은011 및 PROPOSALS/UNIMPLEMENTED_PROPOSALS에 함께 남긴다. 현재 배포 기능은 FEATURES/ROADMAP/PROPOSALS에 별도 이력으로 기록한다. 기존 미구현/보류 항목을 완료로 바꾸지 않는다.
3. 검증된 overlay11개만 Windows root에 구조화 병합하고 정적 문법/원문 일치를 검사한다. 검토 ZIP과 해시를 영구 보존한 뒤 해당 Staging13개 파일만 구조화 삭제한다. 다른 Staging은 보존한다.
4. 이번 변경만 한국어 Conventional Commit으로 commit/push한다. 원래 dirty 원장의 기존 변경은 index에 섞지 않고 이번 추가 단락만 분리한다. 비밀/운영 DB·환경 파일은 Git에 포함하지 않는다.
5. 기존 운영 host/user/정확한 idle web PID와 자체 worker를 확인한다. private release 백업을 보존하고 기존 검토된 deploy_ai_ux_release의 admission gate/정상 종료 경로를 사용한다. 진행 작업이 있으면 종료될 때까지 기다리며 정상 생성 요청을 끊지 않는다.
6. 서버를 정확한 Git commit으로 fast-forward pull하고 Linux 격리 회귀와 실제 업무/AI DB 사본 기동·행 보존을 확인한다. 기존 환경/키·DB 경로·epoch·worker/retention unit을 유지한다. 스키마 변경은 없다.
7. 같은 명령/환경의 웹과 자체 worker를 재기동하고 health·익명 경계·정적 파일 해시·실제 로그인 화면의 모델 접기/새로고침·높이/CSV 팝업을 검증한다. 장비·신청 확정이나 공유 모델/타 서비스를 조작하지 않는다.
8. 원래 DB/설정·코드 commit과 새 결과를 보존하고 운영 보고서/스크린샷을 남긴다. 실패 시 서버에서 즉석 코드 수정하지 않으며 Windows 후보를 거친다. 최신 데이터 위로 과거 DB를 덮는 복구는 수행하지 않는다.

운영 전환 중에는 기존 점검 모드가 잠시 유지될 수 있다. 현재 배포는011의 상태 색상·상단 레이아웃이나 보류 web_search를 구현하는 승인이 아니다.
