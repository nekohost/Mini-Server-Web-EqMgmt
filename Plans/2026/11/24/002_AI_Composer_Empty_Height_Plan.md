---
artifact_id: PLAN-20261124-002
work_id: FIX-20261124-AI-COMPOSER-EMPTY-HEIGHT
owner: Claude
status: completed
approval: user-explicit-approval-through-production-deployment
---

# AI 도우미 빈 입력창 높이 복원 계획

## 1. 요청과 승인 범위

- 요청: 입력창이 비어 있으면 직전 입력 길이와 무관하게 세로 폭을 기본값으로 되돌린다.
- 승인: 사용자가 이번 개선을 운영 반영까지 막힘없이 진행하도록 명시 승인했다.
- 범위 밖: 입력 최대 높이(160px), 전송·초안 보존 계약, 서버 API, DB, 예시 프롬프트 버튼 동작.

## 2. 원인

`static/js/equipment_ai.js`는 `input` 이벤트에서만 textarea 높이를 계산한다. 전송 성공 시 코드가 `value = ''`로 입력값을 비우면 `input` 이벤트가 발생하지 않아, 긴 입력으로 늘어난 인라인 `height`가 그대로 남는다.

## 3. 변경 설계

1. `fitInputHeight(input)` 공용 함수를 추가한다. 인라인 높이를 먼저 제거하고, 값이 있을 때만 `min(scrollHeight, 160px)`을 적용한다. 값이 없으면 CSS 기본 높이(`rows=2`, `min-height:52px`)로 돌아간다.
2. 사용자 입력 이벤트, 전송 성공 후 입력값 비움, 모바일 줄바꿈 편집 복원에서 이 함수를 호출한다.
3. 전송 중 새로 입력한 초안은 기존처럼 비우지 않으므로 높이도 유지한다.
4. `tests/test_ai_input_preferences.js`에 삭제·전송·모바일 복원 경로의 회귀 검사를 추가한다.

## 4. 대상 파일

- `static/js/equipment_ai.js`
- `tests/test_ai_input_preferences.js`
- 본 작업의 Plan·Task·Report

## 5. 검증과 반영 절차

1. `Staging/20261124-ai-composer-height/`에 변경 패치를 작성하고, 깨끗한 `HEAD` 임시 사본에 적용한다.
2. 임시 사본 기준 정적 보안 검사와 Linux Chromium 입력 설정·전송 hitbox·Fold7·viewport 브라우저 검사를 수행한다.
3. 운영 소스에 구조화 편집으로 병합하고 임시 사본과 해시를 대조한 뒤, 본 작업 Staging 폴더만 삭제한다.
4. 본 작업 파일만 commit·push한다. 작업 트리의 기존 미커밋 변경은 포함하지 않는다.
5. `eqmgmt-backup`에 `tools/deploy_ai_ux_release.py`의 `pause → pull → check-copy → activate` 절차로 반영하고 라이브 상태와 배포 자산을 확인한다.

## 6. 롤백

DB·설정 변경이 없으므로 해당 commit을 `git revert`한 뒤 같은 배포 절차를 수행하면 복구된다. 배포 도구가 `pause` 단계에서 두 DB의 일관 스냅샷을 릴리스 디렉터리에 보존한다.
