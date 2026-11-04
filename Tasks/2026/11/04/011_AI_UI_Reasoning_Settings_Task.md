---
artifact_id: TASK-20261104-011
work_id: FIX-20261104-AI-UI-REASONING-SETTINGS
owner: Codex
created_at: 2026-11-04
status: completed-staging
---

# AI 화면 글자색·추론 설정·가독성 보완

사용자 승인 범위는 현재 Staging 후보의 세 항목 수정이다. 배경 테마를 보존하고 관리자 글자색을 보완한다. 표준 추론 off/low/medium/high/xhigh/max를 표시하고 모델별 실제 지원·관리자 허용 범위 밖의 항목은 보이되 비활성으로 둔다. 관리자 모델 설정과 Qwen3.8 Flash Next 사전 설정을 구현하고 모바일 안내문을 적절하게 키운다. 운영 반영·실모델 생성·타 서비스 변경은 포함하지 않는다.

- [x] recorder/profile/validate/context 및 필수 노드 확인(legacy/runtime-session-mismatch).
- [x] 010 결함 근거·현재 코드·Qwen 공식 자료 확인, Plan/사전 Validation 작성.
- [x] 글자색만 변경하고 안내문 12px·줄바꿈 조정.
- [x] 표준 추론 계약·기존 대화/접수 작업 의미 보존·모델별 서버 검증 구현.
- [x] 관리자 허용 단계/기본값과 Qwen 사전 설정, 사용자 비활성 선택지·출처 표시 구현.
- [x] 영향 회귀·Linux 합성 backend 112/browser 93 통과, 수정 후 화면 18장 캡처·전수 시각 확인.
- [x] 이전 009/010 자료·운영 소스 보존, 새 원장과 후속 Validation/보고서 작성.

011 Report와 `011_AI_UI_Reasoning_Screens/`의 갤러리·manifest·verification에서 최종 결과를 확인한다. 실제 운영 반영·실모델 생성·타 서비스 설정 변경은 하지 않았다.
