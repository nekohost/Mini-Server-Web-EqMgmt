---
artifact_id: TASK-20261105-004
work_id: STAGING-20261105-AI-COMPACT-LAYOUT
parent_work_id: PLAN-20261105-AI-COMPACT-LAYOUT
owner: Codex
created_at: 2026-11-05
status: complete
---

# 기존 AI Staging에 공간 절약 배치 병합

사용자는 Plan 003의 Staging 반영과 분할 가능한 작업의 하위 에이전트 사용을 승인했다. 기존 `Staging/20261105-ai-ux-trash`에 병합하며 1~7번 기능과 기록을 폐기하지 않는다. 운영 루트·DB·서비스·Git commit/push는 대상이 아니다.

- [x] recorder/profile/context 전체 필수 노드와 승인 Plan 003을 확인한다.
- [x] 구현 전 Validation 1~8 및 후보/원본 hash를 기록한다.
- [x] 변경 전 추론 너비 W0와 본문 높이를 Linux 격리 브라우저로 측정한다.
- [x] 화면 구조·CSS와 JS 표시 상태를 독립 하위 작업자로 분담한다.
- [x] 추가 배치/반응형 회귀를 독립 하위 작업자로 작성하고 부모가 실행·통합한다.
- [x] 기존 표/추론/모델/휴지통·관리자 회귀와 신규 배치를 같은 최종 후보에서 검증한다.
- [x] 모바일/PC 화면을 직접 검토하고 문제를 수정한다.
- [x] 원본 보존·변경 파일·실제 측정/한계·최종 Validation을 영구 보고한다.

분담의 도구 지정은 `gpt-6.1-sol`, reasoning `max`, fork none이다. Fast 제어 항목은 제공되지 않아 보장을 주장하지 않는다. 재위임은 하지 않으며 공유 파일은 소유자를 나눠 충돌을 피한다.

완료: 제품 변경은 기존 후보의 template/CSS/사용자 JS3개이며 기존1~7번 기능과 backend를 보존했다. backend 고유178개 실패/오류/skip0, 최종 브라우저 기능24뷰·2657 checks 및 치수3뷰 통과다. backend 통과 후22개 backend Python hash가 최종과 같고 후속 변경은 프론트엔드/fixture를 재검증했다. 기존43개 중35개 hash 동일,8개는 승인 후속 변경(제품3/fixture3/문서2), 측정 fixture1개 추가로 최종manifest44개다. root 주요24개와 HEAD/index/기존dirty를 보존했다. 상세 근거·중간 실패·실제 폭 보정·직접 본 PNG·제한은 Report004와 validation/source-manifest JSON에 있다.
