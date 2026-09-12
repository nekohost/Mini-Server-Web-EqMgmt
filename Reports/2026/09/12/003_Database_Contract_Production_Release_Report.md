---
artifact_id: REPORT-20260912-003
work_id: WORK-20260912-DATABASE-CONTRACT-INTEGRITY-HARDENING
created_at: 2026-09-12T16:00:19.073+09:00
related_artifacts:
  - ../../../../Plans/2026/09/12/001_Database_Contract_and_Integrity_Hardening_Plan.md
  - ../../../../Tasks/2026/09/12/002_Database_Contract_and_Integrity_Hardening_Task.md
  - ./002_Database_Contract_and_Integrity_Hardening_Review_Report.md
  - ../11/006_Five_Plan_Production_Release_Report.md
---

# DB 계약 개선 및 중단 작업 운영 반영 결과

## 적용 결과

- DB 개선 소스와 테스트를 main에 commit/push하고 사용자 지정 백업 서버에 pull·기동했다.
- 실행 코드 commit: 87e28bc4b2a4183ad16368f7af907f7c5396ad0b. 프로세스: PID 48811, 가상환경 Python 3.12.3, 기존 app.py 수동 실행 방식.
- 대상 DB: /home/nekohost/services/Mini-Server-Web-EqMgmt/equipment.db.
- 실제 DB의 user_version은 0 → 1, integrity_check는 ok, foreign_key_check는 0건이다.
- DB 구조는 17개 테이블을 보존하고 명시적 인덱스 4개를 추가했다. 레거시 equipment와 독립 장비 감사 로그를 삭제하지 않았다.
- 09/11부터 남아 있던 DRAINING 상태(예상 종료 2026-09-11T10:00)는 사본을 남긴 뒤 배포 완료 시 NORMAL로 전환했다. 변경 주체는 deployment-ssh로 감사에 기록했다.
- 주 서버 192.168.0.166은 제공된 키로 SSH 인증이 거절되며 해당 포트 5000도 접속 거절이다. 이 서버의 pull·DB 변경·재시작은 수행하지 못했다. 백업 서버 적용을 주 서버 적용으로 간주하지 않는다.

## 구현

1. 모든 정상 DB 연결에 FK ON과 제한된 busy_timeout을 적용하고 설정 실패 시 연결과 계수를 정확히 반환한다.
2. 단건·일괄 마스터 삭제는 노드/옵션/장비/레거시/대기 승인 참조를 검사하고 409와 참조 수를 반환한다. NULL로 관계를 끊는 코드는 제거했다.
3. 기존 마스터 병합 UI/API는 승인 상태·자기 선택·중복 ID·루트 충돌을 검사하고 계층 이동·원본 삭제·감사를 한 transaction에서 처리한다.
4. 관리자 목록의 참조 집계와 삭제 안내를 보강하고 명칭의 HTML 렌더링을 이스케이프했다.
5. user_version=1과 database_contract_v1 이력, 의미 기반 스키마 지문 v2를 도입했다. 물리적 컬럼 순서만 다른 DB는 동등하게 비교하고 CHECK·FK·COLLATE·생성 컬럼·인덱스 정의는 보존한다.
6. 현재 16개 필수 업무 테이블을 정의하고 빈 equipment는 백업 호환성의 선택적 전환 대상으로 두었다. 버전이 적용된 DB에서는 역사 1-Tier 재변환을 중복 실행하지 않는다.
7. 사용자 영구 삭제 시 password_resets도 정리하고, 참조가 남아 있는 노드/옵션의 결재 반려 삭제는 409와 rollback으로 대기 상태를 보존한다.
8. 독립 migration/rollback과 운영 사본 검사·기동 CLI를 추가했다.

## 검증 증거

| 검증 | 결과 |
|---|---|
| Linux 기존 릴리스 기준선 | 39/39 통과 |
| DB 계약·마스터·사용자·승인 포함 Linux 통합 회귀 | 55/55 통과 |
| 등록 화면·WebMCP·수신 AI Node 회귀 | 23/23 통과 |
| 거버넌스 tooling 회귀 | 54/54 통과 |
| Staging Python AST / 관리자 inline JS 파싱 | 통과 |
| 실제 운영 이력 사본 기동·migration | 통과 |
| 새 DB ↔ 실제 운영 이력 DB 스키마 호환성 | 양방향 통과 |
| 사본 down → up → 재실행 | 통과, 재실행 applied=false |
| 운영 적용 전후 기존 데이터 지문 | 기존 16개 업무 테이블 보존; 실제 기동 후 access_logs 신규 접속 기록만 정상 증가 |
| 운영 DB 검사 | integrity=ok / FK 위반 0 / schema version=1 |
| 백업 서버 localhost 및 LAN IP HTTP | /login 200, WebMCP manifest 200, 비인증 세션·관리자 API 401 |

고의 DB/감사 오류와 잘못된 관리자 비밀번호를 주입한 rollback 테스트에서 ERROR 로그가 출력된다. 이 로그는 실패 경로가 동작한 증거이며 테스트 결과는 통과다.

## 인덱스 채택

실제 DB 사본의 동일 조건 100회 평균과 EXPLAIN을 비교했다. 현재 장비가 1건이므로 미세 시간 차이를 대규모 성능 향상으로 주장하지 않는다.

| 조회 | 적용 전 | 적용 후 | 평균 ms 전 → 후 |
|---|---|---|---|
| 내 장비 | 테이블 SCAN | owner index SEARCH | 0.0092 → 0.0098 |
| 공개 장비 | 테이블 SCAN | 공개 장비 부분 index SCAN | 0.0080 → 0.0088 |
| 최신 재설정 요청 | SCAN + 임시 정렬 | covering index SEARCH | 0.0123 → 0.0078 |
| 대기 승인 | 테이블 SCAN | 종류·상태 index SEARCH | 0.0080 → 0.0084 |

채택 인덱스는 idx_contract_equipment_owner(user_id,id DESC), idx_contract_equipment_public(공개·비임시 부분 인덱스), idx_contract_password_latest(UserId,ExpiresAt DESC), idx_contract_approval_pending(RequestType,Status)다. 실제 목록의 OR NULL 조건 때문에 owner 인덱스에 is_draft를 중간 키로 넣지 않았다. 감사 rowid의 중복 인덱스와 JSON 표현식 인덱스는 추가하지 않았다. 현재 쓰기 회귀는 기능 테스트에서 통과했으며 대량 데이터의 정량적인 쓰기 부하 시험은 수행하지 않았다.

## Git 배포 문제와 조치

서버 remote.origin.fetch가 특정 backup-deploy 태그 하나로 제한되어 있었다. 따라서 git pull은 최신이라고 표시하면서도 main은 1f19fd3에 머물렀다. 기존 태그 refspec을 유지하고 +refs/heads/main:refs/remotes/origin/main을 추가했으며 main upstream을 origin/main으로 지정했다. 이후 fast-forward와 실제 HEAD 일치를 확인했다. 이 Git 설정 변경은 해당 백업 서버 저장소의 .git/config만 대상이며, 필요 시 추가한 refspec과 branch.main의 upstream 두 키를 원래 미설정 상태로 되돌릴 수 있다.

첫 기동 점검은 비인증 /api/check_session의 정상 401을 실패로 오판해 새로 만든 앱 프로세스만 종료했다. 점검 경로를 공개 /login으로 수정하고, 종료 후 TIME_WAIT를 listener로 오인하지 않도록 포트 검사에 SO_REUSEADDR을 적용했다. 수정은 Windows Staging → commit/push → Linux pull 순서로 재적용했다.

## 데이터 보존과 복구

- 최초 운영 변경 전 사본: /home/nekohost/.local/share/mini-server-eqmgmt/release-20260912/production-before-20260912T065441Z-0170270962db48c5a33bfeb88df412a3.db (schema version 0).
- migration 직전 사본과 SHA·스키마·행 수 증거는 instance/database-operations/migration-backups에 보존한다.
- 점검 상태 복구 사본: 같은 release-20260912 디렉터리의 maintenance-before-completion.json.
- DB 사본은 0600, 상위 전용 디렉터리는 0700이며 Git에 포함하지 않았다.
- 실패 시 업무 테이블 초기화 없이 transaction rollback한다. 추가된 인덱스·버전은 rollback_contract로 되돌릴 수 있다. 이미 새 업무 쓰기가 발생한 뒤 과거 DB 파일을 덮어쓰는 복구는 사용하지 않는다.

## Validation 1~8 최종 판정

1. 거버넌스: 정규 context와 validator 통과, Staging 우선 변경, 기존 dirty 문서 보존 후 중단 Task 범위에서 완결.
2. 의도: 새 DB 계획의 1차 구현과 기존 릴리스 Linux 검증·백업 서버 적용, 중단된 전체 로드맵 상세 계획 작성을 수행했다. 15개 로드맵 기능 전체를 신규 구현했다는 뜻은 아니다.
3. 정적/실행 논리: 연결 계수, 원자 삭제/병합, 충돌, 승인, 사용자 삭제, 버전/이력, 보존 지문과 실제 query plan을 검증했다.
4. 운영 영향: 백업 서버의 실행 중인 앱과 포트가 없음을 확인한 뒤 사본과 migration을 적용했다. 주 서버의 접속 한계는 별도로 남긴다.
5. 보안/경계: 기존 관리자/CSRF와 접근 로그 정책 유지, 파라미터/ID/HTML 검사, 비인증 HTTP 401, 사본 권한 확인.
6. 복구: 실제 이력 사본의 down/up을 통과하고 원본 업무 행 지문을 보존했다. 서비스 health 실패 시 이번 호출의 프로세스만 종료했다.
7. 사람의 오류: 참조 건수·삭제 사유·병합 충돌 안내, 잘못된 대상·일괄 입력·JSON 검증을 확인했다.
8. AI 메타: 소스/자동 검증/백업 서비스/주 서버 적용 상태를 구분했다. 실제 기동 검사 두 건의 오류와 수정도 기록했다.

최종 상태: 백업 서버 적용 완료, 중단 문서 작업 완료, 주 서버 적용은 SSH 인증 불가로 미완료.

## 문서와 Staging 정리

이전 릴리스 후보 25개는 Git 5acf978의 파일과 일치했고, 새 후보 8개는 현재 commit과 동일했다(새 helper 2개는 파일 끝의 빈 줄 1개만 차이). 검증 후 해당 33개 복사본을 Staging에서 제거했다. 이전 overlay 검사 스크립트는 scratch/release-20260912-recovery/validate_release_governance.mjs에 복구 사본을 두었다. 모든 실제 구현 소스는 Git에서 복구할 수 있다.

이전 감사 문서의 누락 front matter와 임의 00:00 작성 시각을 관측된 파일 생성 시각으로 보정했다. 중단 Task 004의 예약 Plan/Report를 작성하여 깨진 링크를 해결했다. 영구 기록 본문과 사용자 접근 로그는 삭제하지 않았다.
