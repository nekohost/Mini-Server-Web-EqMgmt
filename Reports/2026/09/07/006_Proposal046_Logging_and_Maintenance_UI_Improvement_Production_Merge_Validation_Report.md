# 제안-046 로그 운영 및 점검 화면 개선 운영 병합 검증 보고서

- 작성일: 2026-09-07
- 범위: Staging 검증본의 운영 소스 병합과 systemd 운영 산출물
- 판정: 로컬 운영 소스 병합 통과, 서버 런타임 검증 대기

## 병합 결과

| 운영 대상 | 결과 |
| --- | --- |
| app.py | Staging/app.py와 동일하게 병합 |
| templates/maintenance_admin.html | Staging 검증본과 동일하게 병합 |
| templates/login.html | Staging 검증본과 동일하게 병합 |
| templates/maintenance.html | Staging 검증본과 동일하게 병합 |
| static/js/session_timer.js | 운영본과 Staging이 이미 동일하여 변경 없음 |
| systemd/mini-server-eqmgmt.service | 실제 서비스 경로와 .venv를 반영하고 기동 전 경로 검사 추가 |
| docs/systemd-operation.md | 실제 경로 확인 절차와 대상 PID 종료 절차 반영 |

## Validation 1~8

1. 거버넌스: manifest 및 40개 노드 검증에서 오류 0, 경고 0으로 통과했다.
2. 사용자 의도: 상태별 단일 동작, 한글 확인 문구, 날짜·시간 분리 입력, journald 로그 운영 요구를 유지했다.
3. 정적 논리: 운영 파일 4개가 Staging 검증본과 동일하다. session_timer.js와 관리자 화면 인라인 JavaScript 구문 검사를 통과했다.
4. 운영 영향: DB 스키마 변경은 없다. NORMAL 상태의 기존 요청 흐름은 유지된다.
5. 보안·예외: 관리자 권한, 현재 비밀번호 재인증, CSRF 검증, 서버 측 일시 검증을 유지했다.
6. 롤백: 코드 변경은 직전 Git 커밋으로 복귀할 수 있고, systemd는 disable 및 유닛 제거 후 수동 Gunicorn 방식으로 복귀할 수 있다.
7. 사용자 오류 방지: NORMAL/DRAINING·RECOVERY/RESTORING 상태별로 가능한 동작만 표시한다. 날짜·시간 부분 입력과 잘못된 시간 형식을 차단한다.
8. AI 메타 검증: Staging 전체 디렉터리를 운영 디렉터리에 덮어쓰지 않고 검증된 개별 파일만 병합했다. 병합을 마친 임시 복사본은 정리하고 systemd 유닛과 가이드는 영구 경로로 이동했다. 관련 없는 기존 작업물은 변경하지 않았다.

## 실행한 검사

- governance-tool.mjs validate: 통과
- 운영본과 Staging 대상 4개 파일 동일성 검사: 통과
- node --check static/js/session_timer.js: 통과
- maintenance_admin.html 인라인 JavaScript 파싱: 통과
- git diff --check: 통과
- 이전 서버 경로 및 pkill -f gunicorn 잔존 검사: 0건

## 서버에서 남은 검증

Windows 로컬 환경에는 실제 Python 런타임과 systemd가 없다. 서버에서 pull한 뒤 Python 컴파일, systemd 유닛 검증·등록, 포트 5000 기동, journald 로그, 점검 활성화·해제를 순서대로 확인해야 운영 배포가 완료된다.
