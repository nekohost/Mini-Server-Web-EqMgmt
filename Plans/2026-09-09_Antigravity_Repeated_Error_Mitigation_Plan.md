# Antigravity 반복 오류 대응 계획

- 작성일: 2026-09-09
- 작업 모드: 스테이징 구현 및 외부 상태 복구
- 목표: 반복 권한 경고와 Windows 검색 오류를 제거하고, 대화 기록기의 유휴 상태 쓰기 부하를 줄인다.

## 범위

1. 대화 기록기는 1.5초 수집 폴링을 유지한다.
2. 상태 파일은 논리 상태가 바뀌거나 60초 heartbeat가 도래한 경우에만 원자적으로 저장한다.
3. Gemini Antigravity capability에 Windows 절대 경로 `grep_search` 회피와 다중행 영구 명령 grant 금지를 명시한다.
4. IDE watcher가 `Chat/.state`의 내부 상태 변경을 감시하지 않도록 설정한다.
5. 현재 Antigravity conversation DB를 백업한 뒤 `steps.permissions`의 비정상 명령 grant만 제거한다.
6. 단위·통합 테스트, governance 검증, DB 무결성 검사와 로그 재검사를 수행한다.

## 복구 방법

- 소스 변경은 Git diff로 되돌린다.
- conversation DB는 작업 전 생성한 백업본으로 복원할 수 있다.
- DB의 대화 본문, tool 기록, 단계 순서와 brain transcript는 수정하지 않는다.

## 완료 기준

- 새 대화 이벤트는 기존 폴링 주기 안에 기록된다.
- 입력 변화가 없는 연속 reconcile은 상태 파일을 다시 쓰지 않는다.
- 60초마다 상태 heartbeat는 보존된다.
- 비정상 명령 grant가 conversation DB에서 0건이다.
- 기록기 테스트와 governance validation이 통과한다.
