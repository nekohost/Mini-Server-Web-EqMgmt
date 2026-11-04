---
artifact_id: TASK-20261104-007
work_id: REVIEW-20261104-HERMES-STYLE-AI-PLAN
created_at: 2026-11-04
owner: Codex
mode: comparison-review
status: completed
related_artifacts: [PLAN-20261104-006, REPORT-20261104-007]
---

# Hermes 방식과 기존 확장 계획 비교

사용자가 원하는 Hermes식 세션 유지·프로바이더 endpoint 커스터마이징과 006 계획의 실제 상세를 대조한다. 판단/설명만 수행하며 006 원문, Staging·운영 소스, Hermes 소스/설정/세션 DB는 수정하지 않는다. 사용자 인증정보 파일은 열지 않는다. 새로운 기능을 구현하거나 현재 다른 AI의 평가 결과를 덮어쓰지 않는다.

- [x] recorder/profile/validate/context 확인. legacy(runtime-session-mismatch), validate 오류/경고 0.
- [x] 006 계획과 Hermes 공식 문서·설치된 문서/세션 경로 복원 소스 읽기 확인.
- [x] 핵심 부합·상세 보완·범위 차이를 분리하여 비교.
- [x] Validation 1~8 순서와 교차 시나리오를 보고서에 기록.
- [x] 006·Staging 합계 17개 파일의 SHA-256 동일 확인 및 한국어 보고 준비.

판정: 핵심 방향 부합. 세션 재개 시 선택 복원·목록 API 없는 서버의 수동 모델 등록·허용된 endpoint 고급 설정의 명세는 보완이 필요하다. 006 원문이나 코드·설정은 수정하지 않았다.
