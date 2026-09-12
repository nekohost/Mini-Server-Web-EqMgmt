---
artifact_id: REPORT-20260912-006
work_id: WORK-20260912-OFFICIAL-MODEL-NAME
created_at: 2026-09-12T18:13:49.907+09:00
related_artifacts:
  - ../../../../Plans/2026/09/12/003_Official_Model_Name_Plan.md
  - ../../../../Tasks/2026/09/12/005_Official_Model_Name_Task.md
---

# 공식 모델명 Staging 검토

## 변경 전 Validation 1~8

1. 거버넌스: ensure와 1.6.0 validate 오류/경고 0. 모든 관련 intent·대상·참고 경로의 context 성공 및 전체 노드 읽기. 기존 실패의 허위 원본 경로 추가 없이 진행한다.
2. 의도: 09/12 16:32·17:21 합의의 노드별 공식명, 기존 경로 폴백, 비상속을 승계한다. 기존 경로 기능을 지우지 않고 047 후속 보완으로 독립 작업 문서에 기록한다.
3. 논리: 현재 공통 add_full_model_names의 1회 노드 조회에 공식명 필드를 포함해 N+1을 만들지 않는다. 빈값/누락/자식/손상 계층과 세 API 소비자를 확인한다. 앱 동작은 Windows에서 실행하지 않는다.
4. 영향: 관리자 전용 필드와 스키마 v2를 한 후보로 관리한다. 부분 병합 금지, 구버전 백업의 직접 복원 거부가 필요하다. 기존 IDs와 ModelName/FullModelName 의미는 보존한다.
5. 보안: 관리 권한·CSRF·바인딩 SQL·문자열 길이/제어문자 검사·HTML 이스케이프를 유지한다. 감사와 수정이 같은 트랜잭션이어야 한다. 일반 사용자가 공식명을 승인 없이 등록하지 못하게 한다.
6. 복구: 실제 데이터는 변경하지 않는다. migration은 사전 사본·원자성·반복 검사를 포함한다. down은 새 필드 값이 존재하면 거부하므로 운영 중 새 값 유실을 묵인하지 않는다.
7. 휴먼 에러: 공식명은 전체 제품명 입력임을 안내하고 제조사 중복 표시를 피한다. 공유 영향과 빈값 해제 안내, 취소·재시도·긴 입력·모달 높이 제한을 점검한다.
8. AI 메타: 현재 작업자는 Codex, 승인 범위는 Staging이다. 정적 검사와 실제 Linux/브라우저 통과를 구분한다. 기존 운영·거버넌스·대화 원문은 수정하지 않는다.

## 구현·검증 결과

Staging 구현·정적 검증을 완료했다. 운영 소스 기준선은 `541d6b83e24350eaa514de16b78c3e7322c50761`이다.

### 구현 후보

- 관리자 노드 생성·수정에 공식명 입력과 공유 범위·해제·비상속 안내를 추가했다. 긴 이름 및 모바일 모달 스크롤을 고려했다.
- 관리자는 지정·수정·해제할 수 있고 일반 사용자는 공식명 필드를 직접 지정할 수 없다. 기존 사용자 노드 결재 흐름은 유지한다.
- 같은 노드의 장비에 OfficialModelName·DisplayModelName을 제공한다. FullModelName·ModelName·ID는 유지하며 조상 이름은 상속하지 않는다. 기존 1회 노드 조회만 사용한다.
- 내/공개/임시 목록과 대시보드에서 공식명을 우선 표시하고 분류 경로를 보조 표시한다. 제조사 중복 접두 표시를 피했다. WebMCP 읽기 검색도 공식명·분류 경로 양쪽으로 검색하고 같은 모델명을 반환한다.
- BEGIN IMMEDIATE·사전 private_snapshot·원자 ALTER·v1/v2 이력·버전·컬럼 CHECK/값·인덱스 교차 검사를 포함한 v2 migration 후보를 작성했다. 실제 DB에는 실행하지 않았다.
- 백업 호환성 비교는 v1 원본을 자동 변환하지 않는다. v2 구조와 명명 이력까지 대조한다. v2→1 down은 공식명 값이 존재하면 거부하고 NULL뿐인 경우만 사전 백업 후 허용한다.
- 기존 배포 사본 검사도 추가 컬럼을 오판하지 않게 기존 컬럼 지문·새 값 무단 채움 차단·조건부 down/up·최종 행 보존 재검사로 조정했다.

### 수행한 검사

| 검사 | 결과 |
|---|---|
| governance validate / recorder ensure | 오류 없음, governance 경고 0 |
| Python AST 및 compile 구문 검사 | 12개 파일 통과, Python 3.12.3 |
| JavaScript 구문 검사 | inline/일반 JS 7개 블록, ESM 2개 통과 |
| 정적 연결 계약 | 관리자 전용 입력·빈값 처리·비상속·쿼리 확장·세 API·이스케이프·사전 백업·down 차단 확인 |
| 원본 보존 | 운영 원본 14개 내용이 작업 시작 기준선과 동일 |
| 신규 동작 테스트 작성 | Python 14건, JavaScript 2건; 실행하지 않음 |

병합 전에 사용한 정적 검사 명령은 `node Staging/Official_Model_Name_20260912/tools/check_official_model_static.mjs`였다. 병합 완료 후 Staging 임시 검사 도구는 정리했다.

로컬에서 확인된 Python 명령이 WindowsApps 별칭뿐이어서 백업 서버의 Python 표준 AST 파서에 소스를 SSH stdin으로 전달했다. 서버에 후보 파일을 저장하거나 앱을 import/exec하지 않았고 DB도 열지 않았다. Python 테스트 정의 61개가 파싱됐지만 이는 동작 테스트 통과 건수가 아니다. JavaScript 또한 VM Script 생성/--check만 수행했다.

### 변경 후 Validation 1~8

1. 거버넌스: Staging 우선과 승인 경계를 유지했다. 운영 Rule·거버넌스·앱 파일은 수정하지 않았다. 전체 pack 및 추가 실행 제한 노드를 따랐다.
2. 의도: 분류 경로가 실제 제품명과 다를 수 있다는 요구에 맞게 두 정보를 분리했다. 노드별 한 번 지정·직접 연결 공유·비상속·미지정 폴백을 유지했다.
3. 논리: 추가 컬럼 때문에 기존 tuple의 분류 비교가 변하지 않도록 category/manufacturer 범위를 고정했다. 기존 fixture의 위치 INSERT를 명시 컬럼으로 고쳤고 v1 전용 회귀를 버전 전이와 분리했다. 실제 SQL 동작은 Linux에서 추가 확인해야 한다.
4. 영향: 신규 helper·서비스·Blueprint 감사·앱 backup validator·템플릿·검색·배포 검사·fixture를 하나의 후보로 관리했다. 신규 설치와 기존 DB 모두 init_db 이후 같은 ALTER를 거친다. 운영 부분 병합은 금지한다.
5. 보안: 관리자·CSRF 경로를 유지하고 SQL 바인딩 및 textContent/escapeHtml을 사용한다. 감사 실패 회귀는 이미 바인딩된 callback을 잘못 mock하지 않고 fixture의 실제 감사 INSERT를 trigger로 실패시키도록 작성했다. 아직 실행한 검증은 아니다.
6. 복구: 원본 14개를 변경하지 않았다. 사전 백업 실패와 ALTER 이후 실패의 rollback, 값이 있는 down 차단의 회귀를 준비했다. 실제 운영에 새 값이 생기면 과거 DB 덮어쓰기로 복구하지 않는다.
7. UX: 공식명 입력 예시, 공유 장비 건수, 해제 안내, 분류 보조 정보, 제조사 중복 제거, 모바일 스크롤을 정적으로 확인했다. 실제 브라우저 조작·레이아웃은 미검증이다.
8. AI 메타: Staging 후보와 운영 완료, 파싱과 실행 테스트를 구분한다. 기존 대화·이력을 보존하고 새 제안 번호를 만들지 않았다. Git commit/push·SSH 서비스 배포·실제 DB 변경은 하지 않았다.

## 전달물·남은 실행 검증

병합 전 후보 안내·SHA 원장·원본 대비 diff를 Staging에서 검토했으며, 운영 병합 완료 후 임시 산출물은 거버넌스 절차에 따라 정리한다. 영구 근거는 이 Plan·Task·Report와 운영 diff에 보존한다.

운영 병합 후보 17개는 기존 파일 14개와 신규 helper/회귀 3개다. Staging 전용 README·manifest·diff·정적 검사 도구는 운영에 함께 복사하지 않는다. 후속 승인 시 원본 SHA를 다시 확인한다.

Linux에서 기존 회귀와 신규 Python 14건/JavaScript 2건 실행, 실제 이력 사본의 0/1→2·반복·down/up·행 보존·백업 호환성 확인, 관리자 및 내/공개/임시 목록의 브라우저 확인이 남아 있다. 이번 승인 범위 밖이므로 수행하지 않았다.

## 후속 운영 소스 병합 결과

사용자가 Staging 구현물의 운영 반영을 승인했다. 병합 직전 HEAD `541d6b83e24350eaa514de16b78c3e7322c50761`와 manifest 기준 commit이 일치했고, 기존 운영 파일 14개의 baseline SHA와 후보 17개의 candidate SHA가 모두 일치했으며 신규 3개 운영 경로가 존재하지 않음을 확인했다.

운영 대상 17개만 병합했다. 기존 14개는 candidate SHA와 바이트 단위로 일치한다. 신규 3개는 편집 API가 마지막 빈 줄 하나를 정규화했으며 코드 내용 diff는 없다. Staging 전용 README·manifest·review.diff·정적 검사 도구는 운영 소스에 포함하지 않았다.

병합 후 정적 검사에서 Python 12개 파일의 AST/compile, 테스트 정의 61개, JavaScript 블록 7개, ESM 2개가 통과했다. `node --test tests/test_release_frontend.mjs`는 10/10 통과했다. 이 결과는 Flask/SQLite 동작 검증을 뜻하지 않는다.

### 운영 병합 후 Validation 1~8

1. 거버넌스: recorder와 governance validate를 선행했고 운영 병합 context가 schema·frontend·security·staging-merge 경로를 모두 선택했다.
2. 의도: 공식 모델명 우선, 분류 경로 폴백·보조 표시, 노드 직접 연결 공유, 조상 비상속 계약을 그대로 병합했다.
3. 논리: helper·서비스·API·템플릿·검색·migration·백업 호환성·회귀를 함께 병합해 부분 반영을 피했다. 정적 및 JavaScript 검사는 통과했고 Python 동작은 미검증이다.
4. 운영 영향: DB 계약은 v2가 되지만 이번 작업에서 실제 DB를 열거나 migration하지 않았다. 서버 배포 전 전체 파일을 같은 commit으로 전달해야 한다.
5. 보안: 관리자 권한·CSRF·바인딩 SQL·입력 검증·이스케이프 경로를 유지했다. 민감 정보나 실제 DB는 검사 출력에 포함하지 않았다.
6. 복구: 소스 변경은 diff로 되돌릴 수 있다. 운영 DB migration 전 private snapshot을 만들고, 공식명 값이 있으면 2→1 down을 거부하는 계약을 유지한다.
7. 휴먼 에러: 빈값 해제·공유 범위·비상속·긴 이름 UI 안내를 포함했다. 실제 화면 조작은 후속 검증 대상이다.
8. AI 메타: Windows 운영 소스 병합 완료와 Linux 서비스 적용 완료를 구분했다. Git commit/push, 서버 pull·재시작, 실제 DB 변경은 수행하지 않았다.

## Linux 배포 및 실제 DB 적용

- 구현 commit `f5b37690939c9c255500114cde87a477e5452e4d`을 origin/main에 push하고 백업 Linux 서버 저장소를 fast-forward했다. 서버의 기존 미추적 백업과 불완전 가상환경 디렉터리는 변경하지 않았다.
- `.venv/bin/python -m unittest discover` 전체 69건이 통과했다. 의도된 실패 경로의 ERROR 로그가 출력됐지만 최종 unittest 결과는 `OK`다. 서버에 Node.js가 없어 JavaScript 재실행은 불가했으며, 동일 commit의 Windows Node 회귀 10/10과 governance validate 오류·경고 0 결과를 사용했다.
- 실제 DB는 읽기 전용으로 열고 private snapshot에서 v1→v2 migration, 행 지문 보존, 조건부 2→1 및 1→0 down, 0→2 재적용, 멱등성, 인덱스 조회 계획을 검증했다. 결과는 `copy_check=pass`, `rows_preserved`, `rollback=pass`, `schema_version=2`다.
- 기존 PID 48811의 저장소 경로·실행 파일·포트 소유를 확인한 후 SIGTERM으로 그 프로세스만 종료했다. 운영 전 사본 `production-before-20260912T094756Z-f1197750379d4b8e92e01b6cf743c5bc.db`를 권한 600으로 생성한 뒤 새 PID 51642를 시작했다.
- 실제 DB는 v2, `official_model_name TEXT` nullable 컬럼과 `official_model_name_v2` 이력을 갖는다. 무결성은 `ok`, FK 위반 0이며 노드 12·옵션 1·장비 1이 보존됐다. 기존 공식명은 추측 채움 없이 0건이다.
- Windows와 서버에서 `https://nekohost.org/login` 200 및 TLS 검증 성공을 확인했고, 비인증 `/api/check_session` 401도 정상이다.

주 서버는 현재 제공된 SSH 키로 인증되지 않아 변경하지 않았다. 이번 대화에서 실제 검증 대상으로 사용해 온 백업 Linux 서버에만 적용했다. 브라우저 자동화 표면이 제공되지 않아 인증된 관리자 공식명 입력·해제와 내/공개/임시 목록의 화면 확인은 수행하지 못했다. 이는 남은 사용자 검증 항목이며 서비스·DB 배포 실패는 아니다.
