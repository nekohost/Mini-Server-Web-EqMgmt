---
artifact_id: REPORT-20260913-001
work_id: WORK-20260913-MANUFACTURER-DISPLAY
created_at: 2026-09-13T00:22:35.551+09:00
related_artifacts:
  - ../../../../Plans/2026/09/13/001_Manufacturer_Name_Display_Fix_Plan.md
  - ../../../../Tasks/2026/09/13/001_Manufacturer_Name_Display_Fix_Task.md
---

# 제조사명 화면 표시 회귀 수정 보고서

## 구현 결과

- 기준 commit: `7975604e26cc5c153419c3d976126ba683071719`
- DB·API·스키마·저장 데이터 변경: 없음
- 내 장비·공개 장비·임시저장 목록은 공식명에 제조사가 없으면 `제조사 / 공식 모델명`을 표시한다.
- 공식 모델명이 한글명·영문명·기본 제조사명 중 하나로 이미 시작하면 제조사를 중복하지 않는다.
- 단순 접두어만 같은 경우에는 제조사 토큰으로 오인하지 않는다. 예: `AS`와 `ASUS`.
- 대시보드 복합 조건 결과는 사용자가 선택한 제조사 옵션의 표시값을 모델명과 결합한다.
- 결합 결과는 기존 `escapeHtml` 또는 `escapeDashboardText`를 통과한 뒤 DOM에 삽입된다.

## Staging 결과

독립 후보 모듈과 합성 데이터 테스트를 먼저 작성했다. 운영 DB에서 확인한 `삼성 + 갤럭시 S21 울트라`, 한글·영문 별칭 중복, 단순 접두어, 공식명·제조사 누락, 특수문자, 대시보드 fallback을 검증했다.

| 검사 | 결과 |
|---|---|
| Staging 후보 구문 검사 | 통과 |
| Staging 합성 시나리오 | 5/5 통과 |
| 운영 템플릿 inline JavaScript 구문 | 통과 |
| 전체 Node 테스트 | 32/32 통과 |
| `git diff --check` | 통과, 공백 오류 없음 |
| governance validate | 통과, 오류 0·경고 0 |

전체 Node 테스트의 최초 디렉터리 인자 실행은 Node 22가 `tests`를 모듈 경로로 해석하여 실패했다. `rg --files tests -g "*.mjs"`로 확인한 실제 3개 테스트 파일을 명시해 재실행했고 32/32가 통과했다. 이는 구현 결함이 아니라 잘못된 테스트 호출 방식의 교정이다.

검증 완료 후 Staging 임시 후보 파일은 삭제했다. 영구 근거는 이 Plan·Task·Report와 운영 회귀 테스트에 보존한다.

## Validation 1~8

1. 거버넌스: recorder ensure 성공, governance 1.6.0 validate 오류·경고 0, 전체 intent·대상 경로 context와 두 pack을 확인했다. 최초 `.git/**` target 입력은 실제 파일 경로가 아니라는 진단에 따라 제거하고 재검증했다.
2. 사용자 의도: 사용자가 승인한 화면 수정만 수행했다. 제조사 DB 값, 공식 모델명 값, API 계약과 편집 화면은 변경하지 않았다.
3. 정적 논리: 비교용 정규화 값만 만들고 표시 원문은 유지한다. 한글·영문·기본 별칭과 문자열 경계를 검사하며 네트워크 또는 DB 호출을 추가하지 않았다.
4. 운영 영향: 두 템플릿의 표시 문자열과 프런트엔드 테스트만 바뀐다. 인증·권한·저장·검색·migration에는 영향이 없다.
5. 보안·예외: null·공백·특수문자와 제조사/모델 누락을 검증했다. 최종 문자열은 기존 HTML 이스케이프 경로를 유지한다.
6. 복구: 데이터 변경이 없어 배포 commit 역적용만으로 복구 가능하다. 서비스 재시작 전후 commit과 HTTP 상태를 확인한다.
7. 사용자 오류: 공식명에 제조사를 포함하거나 생략해도 제조사 누락과 명백한 중복을 방지한다. 별칭이 우연히 다른 모델의 접두어인 경우는 문자열 경계 검사로 분리한다.
8. AI 메타: 작업자는 Codex이며 Mini-Server가 owner다. 기존 공식 모델명 기능의 후속 회귀 수정으로 기록했고 새 기능 제안이나 Rule 변경으로 확대하지 않았다.

## 배포 결과

- 구현 commit `f74c8bdd524577f21a5f915a7ad9a042efd7b0bf`를 `origin/main`에 push했다.
- 백업 Linux 서버는 `7975604`에서 `f74c8bd`로 fast-forward 됐다.
- 서버의 기존 untracked `.venv.incomplete-20260907/`, `equipment.db.before-session-token-20260907.bak`는 이번 추적 파일과 겹치지 않아 그대로 보존했다.
- 최초 `unittest discover`는 루트 자동 탐색이 테스트 디렉터리를 찾지 못해 0건이었다. `-s tests -p 'test_*.py'`를 명시해 재실행했고 69/69가 통과했다. 의도된 실패 경로 ERROR 로그가 출력됐지만 최종 unittest 결과는 `OK`였다.
- 기존 PID 54444의 작업 디렉터리, Python 실행 파일, 포트 5000 소유를 확인한 뒤 해당 프로세스에만 SIGTERM을 보냈다.
- 새 서비스 PID는 55646이며 `.venv/bin/python -u app.py`가 `0.0.0.0:5000`을 소유한다.
- `https://nekohost.org/login`은 HTTP 200, 비인증 `https://nekohost.org/api/check_session`은 예상대로 HTTP 401이다.
- Computer Use를 통한 브라우저 렌더링 검증을 시도했으나 현재 사용 가능한 브라우저 표면이 없어 수행하지 못했다. 이를 성공으로 간주하지 않았으며, 실제 운영 템플릿 함수 실행 테스트 32/32와 공개 HTTP 상태를 배포 검증 근거로 사용했다.
- 배포 결과 기록 시각: `2026-09-13T00:26:48.889+09:00`.
