---
artifact_id: TASK-20261104-010
work_id: REVIEW-20261104-AI-STAGING-SCREENS
owner: Codex
created_at: 2026-11-04
status: completed-with-findings
mode: screenshot-and-review
---

# 신규 AI 화면 샘플 캡처·검토

사용자 요청에 따라 현재 Staging 소스에서 신규 사용자 AI 화면과 관리자 연결 관리 화면을 렌더링하고 실제 스크린샷을 검토 기록으로 남긴다. 발견한 화면 문제를 사용자에게 보고한다. 이번 범위는 캡처·검토이며 기존 후보·운영 UI의 결함 수정/배포로 확대하지 않는다.

- [x] recorder/profile/validate/context 확인(legacy, runtime-session-mismatch).
- [x] 기존 009 후보·manifest와 화면 원문 확인, Plan 및 사전 Validation 1~8 기록.
- [x] 실제 후보 Jinja/JS/CSS와 로컬 공통 frame을 고정한 합성 캡처 fixture 작성.
- [x] 승인된 Linux에서 desktop/mobile·light/dark·주요 상태 캡처. 실제 DB·모델은 사용하지 않음.
- [x] 원본 PNG·캡처 조건·소스/이미지 SHA와 갤러리 보존(기본 16장+확인 카드 상세 2장).
- [x] 이미지 시각 검토 및 DOM 근거로 결함 2건(P2/P3)/가독성 개선 권고 1건 구분.
- [x] 후속 Validation 1~8, 후보/운영 소스 불변 확인 및 발견 사항 사용자 보고.

신규 생성 출력은 캡처 도구의 PNG 산출물이며 기존 파일은 덮어쓰지 않는다. 문서/fixture source는 구조화 patch로 작성한다. 기존 009 검증 결과와 source manifest는 변경하지 않는다.

최종 18장과 gallery/manifest/verification은 `Reports/2026/11/04/010_AI_Staging_Screens/`에 있다. UI-01 관리자 dark 대비, UI-02 출처 추론 값 표기, UI-I01 모바일 작은 안내문은 모두 미수정 상태이며 010 Report에서 후속 권고를 구분한다.
