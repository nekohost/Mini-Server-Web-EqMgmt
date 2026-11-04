---
artifact_id: PLAN-20261104-005
work_id: REVIEW-20261104-USER-AI-POST-CORRECTION-STATIC
created_at: 2026-11-04
owner: Antigravity
mode: static-review-plan
status: completed
related_artifacts: [TASK-20261104-005, REPORT-20261104-005]
---

# 장비관리 AI 결함 수정 후 Staging 정적검사 계획

## 1. 목적과 범위

`004_User_AI_Assistant_Corrections_Report.md`와 `user-ai-assistant-corrections-validation.json`에 기록된 결함 수정(사용자 지시 1~7, D01 정책 정정 반영 및 D02~D06 수정, D07 보류 기록)이 반영된 `Staging/20261104-user-ai-assistant/` 후보 코드 전체를 정적 검사한다.

기존 35개 목표 기준(기능 F01~F12, 품질 Q01~Q15, 자원 제한 L01~L08)과 사용자 지시 1~7이 실제 코드 경로에서 충족되었는지, 수정 과정에서 새로운 논리·보안·경합·UX 결함이 유입되지 않았는지 확인한다. 필요한 추가 조치가 있을 경우 표 형태로 정리하여 보고한다.

## 2. 검사 방법과 제약

1. Task(`TASK-20261104-005`)를 생성하고 Validation 1~8단계를 순서대로 수행한다.
2. `user-ai-assistant-corrections-validation.json`에 명시된 후보 파일 16개(overlay 15개 + README 1개)와 보존 대상 파일의 SHA-256 해시 정합성, Python AST 파싱(10개), JavaScript 구문 검사(2개)를 확인한다.
3. Staging 후보 소스 전체(`app.py`, `utils/ai_assistant/*.py`, `static/js/*.js`, `static/css/equipment_ai.css`, `templates/equipment_ai.html`, `tests/*.py`)와 루트 호출 계약(`utils/roadmap_validation.py`, `utils/roadmap_equipment.py`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md` 등)을 전수 대조한다.
4. Windows 로컬 구동 금지 규칙(`operations.staging`)을 준수하며, 앱 구동·운영 DB 접근·모델 호출·코드 수정·운영 병합은 수행하지 않는다.
5. 판정은 `정적 충족`, `부분 충족`, `미충족`, `사용자 지시 보류`로 구분하고, 필요한 조치 사항을 표 형태로 정리한다.
