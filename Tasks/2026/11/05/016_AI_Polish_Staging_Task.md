---
artifact_id: TASK-20261105-016
work_id: STAGING-20261105-AI-POLISH
owner: Codex
status: completed-staging
scope: staging-only
---

# AI 화면 개선1~10 Staging 구현·검증

- [x] 사용자 승인 범위·기존 미실현011/013/014/015와 현재 운영 기준을 확인한다.
- [x] 통합 계획016과 구현 전 Validation1~8을 작성한다.
- [x] 운영 기준 원문과 해시를 보존한 Staging 후보를 준비한다.
- [x] 레이아웃/포털, rename/일괄 휴지통, 부드러운 출력의 세 하위 작업을 병렬 수행한다.
- [x] 실제 선택 프로바이더/자체 큐 상태 API와 화면을 통합한다.
- [x] Python AST/JavaScript 정적검사·합성 backend/Node 회귀를 수행한다.
- [x] Linux 격리 browser fixture에서 두 테마·좁은/넓은 화면·상태/휴지통/출력을 검증하고 스크린샷을 직접 검토한다.
- [x] 결함 수정 후 영향 검증·운영 소스 보존 확인·관련 계획/원장 상태와 최종 보고를 갱신한다.

운영 코드 병합·Git commit/push·서버 배포·운영 DB 처리·실제 모델 요청은 이번 승인 범위에 없다. Linux 합성 검사는 별도 임시 경로와 가짜 계정/모델 데이터만 사용한다.
