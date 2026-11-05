---
artifact_id: TASK-20261105-002
work_id: STAGING-20261105-AI-UX-TRASH
parent_work_id: REVIEW-20261105-AI-UX-RETIREMENT
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 1~7번 개선 Staging 구현

승인 근거: 사용자가 기존 001 Plan의 1~7번 Staging 반영과 분담 가능한 작업의 하위 에이전트 사용을 지시했다. 모든 변경 후보는 `Staging/20261105-ai-ux-trash/overlay`에 둔다. 운영 root 소스와 실제 DB/서비스는 변경하지 않는다.

- [x] recorder/profile/manifest/context와 전체 적용 노드를 확인한다.
- [x] 기존 승인 Plan과 현재 소스 기준을 읽고 구현 전 Validation 1~8을 기록한다.
- [x] 사용자 채팅 화면: 표 renderer·짧은 모델명·휴지통/복구/영구삭제 UX.
- [x] 관리자 화면: 공통 처리 modal·메뉴 이전·기존 Strata UI/gateway 회수 후보.
- [x] 저장소: v4·휴지통·시간/멱등/권한·점유 분리·종속/원장 삭제·만료 timer.
- [x] 조회 인자 공통 정규화·probe 문맥 분리와 lifecycle API/worker 통합.
- [x] 하위 산출물 교차 검토·원본 보존·정적 검사·허용된 Linux 격리 회귀/화면 검증.
- [x] 최종 Validation 1~8·재현 절차·한계·후속 운영 절차를 보고한다.

분담: 사용자 UI, 관리자 UX/메뉴/옛 UI 정리, 저장소/worker lifecycle을 독립 파일로 맡긴다. 부모는 조회/문맥/API 통합·검증과 공유 문서를 담당한다. 하위 요청 모델은 `gpt-6.1-sol`, reasoning `max`이며 도구가 Fast 설정/검증 항목을 제공하지 않는 한 Fast 보장을 주장하지 않는다. 추가 하위 재위임은 하지 않는다.

완료: 고정 후보의 Linux 고유 backend 178개(실패/오류/skip 0), 실제 Chromium 16뷰·803 checks 통과. Python AST 25개, JS 구문 4개, Linux Jinja 3개와 5분 calendar parser도 통과했다. 주요 원본 24개 SHA와 기존 HEAD/dirty 9개/index를 보존했다. 상세 설계는 001을 승계하고 실행 단계 색인 Plan 002와 같은 work_id로 연결했다. 실제 운영 소스 병합·배포·DB migration/삭제·timer 설치·실모델 검증은 수행하지 않았다.
