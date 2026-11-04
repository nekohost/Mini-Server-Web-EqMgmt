---
artifact_id: TASK-20261104-009
work_id: IMPLEMENT-20261104-MULTI-PROVIDER-AI
created_at: 2026-11-04
owner: Codex
mode: staging-implementation
status: completed-staging
related_artifacts: [PLAN-20261104-006, PLAN-20261104-009, REPORT-20261104-008, REPORT-20261104-009]
---

# 다중 프로바이더 AI Staging 구현

사용자 승인: “좋습니다 그러면 이제 계획사항을 staging에 반영하십시오.”
기존 `Staging/20261104-user-ai-assistant/overlay`에 006 확장 계획과 008에서 대조한 S01~S04를 구현한다. 운영 루트·운영 DB·서비스·다른 프로젝트는 변경하지 않는다. Git commit/push 및 운영 병합은 범위 밖이다. 고급 endpoint 설정과 AI-TECHDEBT-001 일괄 주석 작업은 보류한다.

- [x] recorder/profile/validate/context 확인. legacy, runtime-session-mismatch 경로이며 전용 모델 확인을 주장하지 않는다.
- [x] Plan 작성 후 사전 Validation 1~8 순차 검토.
- [x] S01~S04 및 기존 회귀 경계 보완.
- [x] 연결 registry/암호화/허용 목적지/모델 발견과 검증/관리자 화면.
- [x] 가산 migration/그룹별 슬롯/불변 요청 라우팅/동시 dispatcher.
- [x] 사용자 선택·세션 복원·업무 인계와 초안/요약 포함 저장 예산.
- [x] Linux 합성 backend 106개/Chromium 83개 통과. Python AST 14개/JS syntax 3개.
- [x] 후속 Validation 1~8, 실제 근거·제한·설치/복구 절차와 manifest 기록.

검증은 운영과 분리된 Linux 임시 DB/가짜 provider에서 실행한다. Windows에서는 앱/행동 시험을 실행하지 않는다. 추가 암호화 의존성은 006에서 승인된 표준 Fernet이며, 무의존 대안은 기존 보호 환경변수 참조이다. 운영 venv에는 설치하지 않는다.
