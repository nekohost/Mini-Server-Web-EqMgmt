---
artifact_id: REPORT-20260912-001
work_id: DB-STRUCTURE-AUDIT-20260912
created_at: 2026-09-12T14:13:53.550+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/12/001_Backup_DB_Structure_Audit_Task.md
  - ./003_Database_Contract_Production_Release_Report.md
---

# 백업 서버 DB 구조 감사 Report

- work_id: `DB-STRUCTURE-AUDIT-20260912`
- Task: `Tasks/2026/09/12/001_Backup_DB_Structure_Audit_Task.md`
- 조사 대상: `/home/nekohost/services/Mini-Server-Web-EqMgmt/equipment.db`
- 서버 코드 기준: `main` / `1f19fd30b626`
- 조사 방식: SQLite URI `mode=ro` 및 코드 정적 대조
- 데이터 변경: 없음

## 1. 종합 결론

실제 DB 파일은 `PRAGMA integrity_check=ok`, `PRAGMA foreign_key_check=0건`이며 현재 저장된 데이터의 참조 관계와 노드 트리는 정상이다. DB는 17개 업무 테이블, 9개 명시적 인덱스, 0개 뷰, 0개 트리거로 구성되어 있다.

다만 현재 상태가 정상인 것과 스키마가 장기적으로 안전한 것은 별개다. 가장 중요한 발견은 `access_logs.RequestPayload`가 로그인·회원가입의 비밀번호 필드를 원문 요청 본문에 포함해 저장한다는 사실이다. 또한 스키마에 외래키가 선언되어 있어도 일반 애플리케이션 연결은 `PRAGMA foreign_keys=ON`을 설정하지 않아 제약이 실제 쓰기에서 강제되지 않는다.

## 2. 파일 및 SQLite 상태

| 항목 | 실제 값 |
|---|---:|
| 파일 크기 | 11,100,160 bytes |
| 파일 권한 | `600`, 소유자 `nekohost` |
| SQLite 버전 | 3.45.1 |
| 저널 모드 | WAL |
| WAL/SHM | 모두 존재 |
| 인코딩 | UTF-8 |
| 페이지 | 2,710 × 4,096 bytes |
| `schema_version` | 38 |
| `user_version` | 0 |
| `secure_delete` | 1 |
| 무결성 검사 | `ok` |
| 외래키 위반 | 0건 |

## 3. 논리 구조

```text
users
├─ user_settings                         [FK, ON DELETE CASCADE]
├─ approval_requests                     [RequesterId만 FK]
├─ email_verifications                   [Email 기반, FK 없음]
└─ password_resets                       [UserId 논리 참조, FK 없음]

categories ─┐
             ├─ lineup_nodes(parent_id 자기참조)
manufacturers┘      └─ equipment_options ── equipments

equipment                                  [비어 있는 레거시 1-Tier 테이블]

audit_logs                                 [범용 앱 감사, FK/트리거 없음]
equipments_audit_log                       [삭제 후에도 남는 독립 장비 감사]
access_logs                                [HTTP 메타데이터와 요청/응답 본문]
menus ── role_menu_permissions             [코드 기반 논리 참조]
sys_migrations                             [사용자 정의 마이그레이션 원장]
```

선언된 외래키는 총 7개다. `lineup_nodes` 3개, `equipment_options` 1개, `equipments` 1개, `approval_requests` 1개, `user_settings` 1개다. 사용자·메뉴·감사 주체 등 다수 관계는 코드에서만 연결한다.

## 4. 테이블 현황

| 영역 | 테이블 | 행 수 | 주요 역할 |
|---|---|---:|---|
| 장비 | `equipment` | 0 | 레거시 1-Tier 장비 |
| 장비 | `equipments` | 1 | 현재 장비 인스턴스 |
| 장비 | `equipment_options` | 2 | 재사용 가능한 모델 옵션 |
| 장비 | `lineup_nodes` | 14 | 최대 50단계 모델 트리 |
| 장비 | `categories` | 1 | 카테고리 마스터 |
| 장비 | `manufacturers` | 1 | 제조사 마스터 |
| 사용자 | `users` | 2 | 계정·역할·세션 토큰·소프트 삭제 |
| 사용자 | `user_settings` | 1 | 사용자 환경설정 JSON |
| 인증 | `email_verifications` | 2 | 이메일 PIN 해시 |
| 인증 | `password_resets` | 0 | 비밀번호 재설정 토큰 해시 |
| 권한 | `menus` | 13 | 메뉴 계층 |
| 권한 | `role_menu_permissions` | 25 | 역할별 메뉴 허용 |
| 결재 | `approval_requests` | 0 | 마스터·노드·옵션 승인 |
| 감사 | `audit_logs` | 50 | 범용 감사 이력 |
| 감사 | `equipments_audit_log` | 5 | 장비 생성·변경·삭제 이력 |
| 운영 | `access_logs` | 3,999 | HTTP 접근 및 payload |
| 운영 | `sys_migrations` | 13 | 적용된 마이그레이션 |

## 5. 데이터 정합성 결과

### 정상 확인

- `equipments → equipment_options → lineup_nodes → categories/manufacturers` 고아 참조: 모두 0건
- 장비 소유 사용자 고아 참조: 0건
- `user_settings`, `password_resets`, `approval_requests`, 메뉴 권한 고아 참조: 모두 0건
- 노드 부모·카테고리·제조사 고아 참조: 모두 0건
- 루트에서 도달할 수 없는 노드: 0건
- 노드 순환의 간접 징후 및 직접 depth 불일치: 0건
- 부모·자식 카테고리/제조사 조합 불일치: 0건
- 대소문자 무시 형제 노드 중복 및 옵션명 중복: 0건
- 유효하지 않은 옵션·환경설정·결재 JSON: 0건
- 미승인 카탈로그에 연결된 활성 장비: 0건
- 공개 상태인 임시장비: 0건
- 비밀번호는 2계정 모두 Werkzeug 해시 형식이다.

### 현재 데이터의 의미 있는 상태

- 장비 1건은 `ACTIVE`, 비임시, 공개 상태다.
- 노드 14건은 모두 `APPROVED`이며 깊이는 1~5단계다.
- 옵션 2건은 모두 `APPROVED`다.
- 옵션 1건은 현재 어떤 장비도 참조하지 않는다.
- 노드 12건은 옵션이 없다. 카탈로그 중간 노드 또는 아직 옵션이 없는 말단 노드일 수 있으므로 곧바로 오류로 보지 않는다.
- 장비 감사 5건 중 4건은 현재 장비 행이 없다. `equipments_audit_log`가 삭제 이력을 독립 보존하도록 설계되었으므로 의도된 결과다.
- 사용자 2명은 모두 미삭제·미비활성 상태다.

## 6. 코드와 실제 스키마 대조

- 현재 서버 `app.py`가 참조하는 핵심 3-Tier 객체와 컬럼은 실제 DB에 존재한다.
- 서버는 현재 `main@1f19fd30b626`이고 로컬 작업공간은 `main@5acf978ff995`로 2커밋 뒤처져 있다. 실제 DB 대조에는 서버와 동일한 `origin/main` 코드를 사용했다.
- 현재 장비 CRUD는 `equipments`를 사용하고, `equipment`는 비어 있지만 백업 후보의 최소 필수 테이블 목록에 계속 포함된다.
- 장비 삭제는 `equipments` 행을 물리 삭제하고 옵션은 재사용 카탈로그로 보존한다. 실제로 미사용 옵션 1건이 남아 있다.
- 옵션은 현재 관리자 API에서 참조 장비가 0건일 때만 삭제할 수 있다.
- 전체 모델명은 `lineup_nodes.parent_id`를 따라 루트부터 말단까지 계산하며 실제 트리는 이 계산 조건을 충족한다.

## 7. 발견 사항과 위험도

### Critical — 인증 비밀번호가 접근 로그 요청 본문에 저장됨

`after_request_func()`는 DB 관리 API만 예외로 두고 모든 POST/PUT/PATCH/DELETE 요청 본문을 `request.get_data(as_text=True)`로 저장한다.

값을 읽지 않고 JSON 키만 조사한 결과:

- `/login`: payload 13건 중 유효 JSON 10건, 10건 모두 `Password` 키 포함
- `/register`: payload 16건 중 유효 JSON 2건, 2건 모두 `Password` 키 포함
- 전체 요청 payload 보유 로그: 539건
- 전체 응답 payload 보유 로그: 3,312건
- 최대 요청/응답 payload: 각각 67,059 / 58,539 bytes

실제 비밀번호 값은 조사하거나 출력하지 않았다. 그러나 DB 접근자 또는 DB 백업을 획득한 주체가 해당 값을 읽을 수 있으므로 즉시 별도 보안 조치가 필요한 상태다.

### High — 외래키 선언이 일반 앱 연결에서 강제되지 않음

`open_application_database()`는 `sqlite3.connect()`와 `row_factory`만 설정하고 `PRAGMA foreign_keys=ON`을 실행하지 않는다. 조사 연결에서도 기본값은 0이었다. 현재 `foreign_key_check`는 0건이지만, 향후 코드 실수나 직접 SQL 쓰기로 고아 행이 생성될 수 있다.

### High — 마스터 삭제 로직과 NOT NULL 스키마가 충돌

카테고리·제조사 삭제 코드에는 `lineup_nodes.category_id` 또는 `manufacturer_id`를 `NULL`로 바꾸는 구문이 남아 있다. 두 컬럼은 실제 스키마에서 `NOT NULL`이므로 해당 경로는 연결 노드가 존재할 때 실패한다.

### Medium — 레거시/신규 장비 모델이 동시에 유지됨

레거시 `equipment`는 0건이고 실제 서비스는 `equipments`를 사용한다. 그러나 백업 후보 최소 계약과 일부 마이그레이션·관리 코드에는 레거시 테이블이 남아 있어 향후 코드가 어느 모델을 기준으로 하는지 혼동할 수 있다.

### Medium — 감사가 DB 트리거가 아닌 애플리케이션 코드에만 의존

DB 트리거는 0개다. 따라서 앱을 거치지 않은 직접 DB 변경은 `audit_logs`나 `equipments_audit_log`에 자동 기록되지 않는다. 독립 감사 테이블의 삭제 이력 보존 자체는 정상이다.

### Medium — 성장 시 병목이 될 인덱스 공백

현재 데이터 규모에서는 영향이 작지만 실행계획에서 다음 전체 스캔이 확인됐다.

- 나의 장비·공개 장비: `equipments` 전체 스캔
- 비밀번호 재설정 최신 요청: `password_resets` 전체 스캔 + 임시 정렬 B-Tree
- 중복 결재 확인: `approval_requests` 전체 스캔
- 감사 로그 최근 목록: `audit_logs` 전체 스캔

`lineup_nodes.parent_id`와 `equipment_options.lineup_node_id` 조회는 기존 인덱스를 정상 사용한다.

### Medium — 마이그레이션 이력 의존 스키마

SQLite `user_version`은 0이고 13개 문자열 마이그레이션 이름만 `sys_migrations`에 기록한다. 실제 기존 DB에서는 `SessionToken`이 ALTER로 마지막에 추가됐지만 현재 신규 `users` CREATE 문에는 앞쪽에 포함된다. 백업 호환성 검사가 정규화 SQL·컬럼 순서를 엄격 비교하므로 서로 다른 생성 이력의 DB가 논리적으로 같은 컬럼을 가져도 후보 복원을 거절할 가능성이 있다.

## 8. 권고 우선순위

1. 로그인·회원가입·비밀번호/PIN·토큰 관련 요청/응답 payload 수집을 즉시 차단하거나 키 기반으로 비식별화한다.
2. 기존 `access_logs`의 자격증명 포함 행은 별도 백업·감사·복구 계획을 수립한 뒤 파기 또는 마스킹한다. 이는 파괴적 데이터 작업이므로 별도 승인과 사전 백업이 필요하다.
3. 모든 애플리케이션 DB 연결 직후 `PRAGMA foreign_keys=ON`을 적용하고 삭제·복원·마이그레이션 회귀 테스트를 수행한다.
4. 마스터 삭제는 NOT NULL을 깨는 NULL 갱신 대신 사용 중 삭제 차단 또는 명시적 대체 마스터 병합으로 통일한다.
5. 레거시 `equipment` 제거 여부와 3-Tier 모델의 단일 정식 계약을 별도 마이그레이션 계획으로 확정한다.
6. `equipments(user_id,is_draft,is_public)`, `password_resets(UserId,ExpiresAt)`, 결재 대기 조회, 감사 최신 조회에 맞춘 인덱스를 실제 데이터 증가율과 함께 설계한다.
7. 스키마 버전과 정규화된 마이그레이션 기준선을 도입해 생성 이력에 따른 DDL 차이를 제거한다.

## 9. Validation 1~8

1. **거버넌스 준수성:** recorder ensure와 governance validate 통과. 원격 DB는 Mini-Server owner의 지원 실행 범위에서 읽기 전용으로 조사했다.
2. **사용자 의도 충족:** `app.py` 추정이 아니라 실제 서버 DB를 직접 조사하고 서버 코드 기준과 대조했다.
3. **정적 로직:** 테이블·컬럼·FK·인덱스·쿼리 실행계획과 삭제/로그 수집 로직을 교차 확인했다.
4. **운영 영향:** DB·서버 코드·서비스 상태를 변경하지 않았다. WAL DB를 URI `mode=ro`로 열었다.
5. **보안/예외:** 비밀번호·이메일·세션 토큰·PIN·payload 실제 값은 읽거나 보고서에 기록하지 않았다. 구조와 집계만 사용했다.
6. **롤백:** DB 변경이 없어 롤백 대상은 없다. 추가된 Task/Report만 일반 파일 변경이다.
7. **인적 오류:** 레거시/신규 테이블명과 의도된 독립 감사 행을 고아 데이터와 구분했다.
8. **AI 메타:** 실제 조사 대상은 백업 서버 DB, 코드 기준은 서버 HEAD이며 로컬 뒤처진 코드와 혼동하지 않았다.

## 10. 최종 판정

- 현재 DB 데이터 무결성: **정상**
- 현재 노드/옵션/장비 참조 상태: **정상, 미사용 옵션 1건 존재**
- 스키마 장기 안정성: **개선 필요**
- 접근 로그의 인증정보 보호: **즉시 조치 필요**
- 이번 조사에 따른 DB 변경: **없음**
