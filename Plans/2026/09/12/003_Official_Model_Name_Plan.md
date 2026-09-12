---
artifact_id: PLAN-20260912-003
work_id: WORK-20260912-OFFICIAL-MODEL-NAME
created_at: 2026-09-12T18:13:49.907+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/12/005_Official_Model_Name_Task.md
  - ../../../../Reports/2026/09/12/006_Official_Model_Name_Staging_Report.md
  - ../11/001_Lineup_Full_Model_Path_Display_Plan.md
---

# 공식 모델명 표시 후속 보완 계획

상태: Windows 운영 소스 병합, Git push, 백업 Linux 서버의 사본 검증·DB v2 migration·서비스 적용·공개 HTTP 검증 완료. 인증된 실브라우저 공식명 입력·표시 확인만 대기한다. 제안 047 및 09/11 전체 노드 경로 표시의 후속 보완이며 별도 신규 제안 번호를 만들지 않는다. 기존 계획·원본 구현 이력은 보존하고 이번 추가 스키마 변경·회귀를 독립 문서로 관리한다.

## 표시·수정 계약

- 모델을 나타내는 lineup_nodes 행에 nullable official_model_name을 추가한다. 개별 장비·옵션에 중복 저장하지 않는다.
- 관리자가 노드 생성·수정 화면에서 200자 이내로 지정한다. 공백 제거 후 빈값/null은 해제, 키 생략은 기존 값 유지다. 문자열 이외의 값과 제어문자는 거부한다. 일반 사용자 노드 등록은 기존 결재 흐름을 유지하며 공식 모델명 지정은 403으로 거부한다.
- 상위 노드의 공식명을 자식에게 자동 상속하지 않는다. 이름은 해당 노드에 직접 연결된 옵션/장비만 공유한다. 동일 이름을 가진 별도 노드도 허용한다.
- 기존 ModelName(말단명), FullModelName(분류 경로), ID는 보존한다. OfficialModelName과 DisplayModelName(공식명 → 분류 경로 → 말단명)을 추가한다.
- 나의/공개/임시 장비, v2 조회, 대시보드 및 같은 목록을 사용하는 검색 소비자를 함께 점검한다. 공식명 입력 예시는 Beelink SER8처럼 제조사를 포함한 실제 전체 제품명이다. 공식명 앞에 제조사를 자동 중복 추가하지 않는다. 분류 경로는 보조 정보로 유지한다.
- 모든 표시를 escapeHtml/textContent로 처리하고 긴 이름 줄바꿈과 모바일 모달 스크롤을 보장한다. 이름 변경 영향·해제 결과를 화면에 안내한다.

## DB·백업·복구

- 기존 init_db의 기본 테이블 생성 후 공통 migrate_contract에서 새 DB와 기존 v1 DB에 동일한 ALTER TABLE을 적용한다. 별도의 CREATE/ALTER 정의 차이를 만들지 않는다.
- 스키마 버전 2 및 official_model_name_v2 이력을 추가한다. 0→2, 1→2, 2 재실행의 버전·이력·컬럼·인덱스를 교차 확인한다. 부분 적용이나 미지 버전은 거부한다.
- BEGIN IMMEDIATE → 기존 무결성 검사 → private_snapshot 사전 백업 → 필요한 v1 인덱스/이력 및 nullable 컬럼 추가 → v2 이력/버전 → 재검사 → commit. 기존 행·ID·이름을 변환하거나 공식명을 추측해 채우지 않는다.
- v1 백업을 v2 서비스에 그대로 복원하지 않는다. 별도 사본에 승인된 migration을 수행하고 호환성을 재검사해야 한다. 업로드 원본이나 운영 DB를 자동 변환하지 않는다. v2 백업은 컬럼 제약과 v1/v2 명명 이력까지 확인한다.
- 안전한 down 후보는 2→1이다. 공식명이 하나라도 저장돼 있으면 데이터 손실을 막기 위해 거부한다. 모두 NULL인 경우에만 사전 백업 후 추가 컬럼·v2 이력·버전만 원자적으로 되돌린다. v1→0 기존 rollback과 분리하며 실제 실행은 이번 범위 밖이다.

## 검증·비범위

Windows에서는 AST/문법·정적 계약·원본 대비 diff만 검사한다. 실제 앱/SQLite 동작 테스트는 Linux 전용 회귀로 준비하되 이번에 실행하지 않는다. 이후 별도 운영 승인 및 표준 push/pull 순서의 Linux 격리 검증에서 정상/권한/CSRF/타입/XSS/감사 실패/빈값/미지정/비상속/공유 표시/행 보존/반복 migration/백업 호환/down 차단을 확인해야 한다.

후보는 Staging/Official_Model_Name_20260912에만 작성한다. 운영 소스·실제 DB·계정·프록시·서비스·Git 원격은 변경하지 않는다. 사용자 실브라우저 확인 전 이를 운영 개발 완료로 표시하지 않는다.

## Staging 완료 기록

17개 운영 병합 대상 후보(기존 14·신규 3)와 Staging 전용 문서·검사 도구를 작성했다. Python 12개 파일, JavaScript 7개 블록, ESM 2개 파일의 구문·정적 계약 검사를 통과했다. 원본 14개는 기준선과 동일하다. 실제 앱/DB 동작·브라우저 검증은 대기이며 운영 반영은 수행하지 않았다.

정적 검토에서 기존 사본 배포 검사의 SELECT * 지문과 무조건 v1 down 호출도 영향을 받는 것을 확인하여 tools/database_release.py 후보에 기존 컬럼 기준 비교·공식명 값 보존·v2 down gate·최종 행 재비교를 포함했다.

## 운영 소스 병합 기록

사용자의 후속 운영 반영 승인에 따라 기준 commit과 기존 파일 14개의 baseline SHA, 후보 17개의 candidate SHA, 신규 파일 3개의 운영 경로 부재를 재검증한 뒤 운영 소스에 병합했다. Staging 전용 README·manifest·diff·검사 도구는 운영 코드에 복사하지 않았다. Python 정적 검사와 JavaScript 회귀 10건이 통과했다. 이후 구현 commit `f5b37690939c9c255500114cde87a477e5452e4d`을 push하고 백업 Linux 서버에서 Python 69건, 실제 DB 읽기 전용 기반 사본 migration·행 보존·down/up, 운영 전 백업, DB v2 적용과 공개 HTTP를 검증했다. 인증된 실브라우저 검증은 남아 있다.
