# [Staging] 제안-017 감사 로그 고도화 개발 계획서 (PLAN)

이 문서는 `Staging/` 디렉토리에 격리 작성된 **[제안-017] 감사 로그 컬럼별 조건 검색, 페이징 및 페이지 당 보기 개수 영속화** 기능의 모의 개발 설계서입니다.

---

## 📌 1. 시스템 목표 및 개요

- **목적**: 대용량 감사 로그(`audit_logs`) 데이터 탐색의 효율성과 보안 추적 성능을 극대화.
- **핵심 목표**:
  1. 컬럼별 조건 검색 (행위자, 일시, IP, 대상 등) + Exact/LIKE 검색 옵션 선택
  2. RESTful 비동기 API 기반의 전역 페이징(Pagination)
  3. 페이지 당 보기 개수 설정 (50, 100, 150, 200, 300, 500 및 기타/직접 입력)
  4. 설정값의 `user_settings` DB JSON 영속화 (재접속 시 이전에 설정한 보기 개수 자동 복원)

---

## 🛡️ 2. 보안 및 기술 고려사항 (Best Practices)

1. **SQL Injection 방지 (Whitelist 처리)**:
   - 프론트엔드에서 파라미터로 넘어오는 `search_field`는 반드시 백엔드의 사전 정의 허용 컬럼 목록(`['ActorLoginId', 'ActorName', 'IpAddress', 'Action', 'TargetId', 'Details']`)에 대조하여 검증합니다.
   - 검색 파라미터는 Dynamic SQL을 안전하게 형성하도록 SQLite 파라미터 바인딩(`?`)만을 사용합니다.
2. **Custom Page Size 상한/하한 방어 (DoS 방지)**:
   - '기타' 옵션으로 직접 숫자 입력 시 최소 10개 ~ 최대 1,000개 범위를 강제(`min 10, max 1000`)하여 백엔드/프론트엔드 메모리 과부하를 방지합니다.
3. **`user_settings` 연동 정규화**:
   - `user_settings` 테이블의 `SettingsJson` 컬럼에 `"audit_log_page_size"` 키로 저장하여 기존 다크 모드/기타 UI 설정과 깔끔하게 통합 관리합니다.

---

## 🏗️ 3. Staging 시안 아키텍처 및 구성 파일

| 구분 | 파일 위치 | 설명 |
| :--- | :--- | :--- |
| **기획/설계** | `Staging/Staging_PLAN.md` | 본 개발 계획서 |
| **백엔드 시안** | `Staging/Staging_app_patch.py` | `/api/audit_logs` REST API 파라미터화 쿼리 및 파라미터 처리 모듈 시안 |
| **프론트엔드 시안** | `Staging/Staging_audit_logs.html` | Tailwind + Vanilla JS 기반의 컬럼 검색, 페이징, 보기 개수 설정 영속화 템플릿 시안 |

---

## 🔄 4. API 스펙 (REST API)

### GET `/api/audit_logs`
- **Query Parameters**:
  - `page`: 페이지 번호 (기본값: 1)
  - `per_page`: 페이지 당 표시 건수 (기본값: 200, max: 1000)
  - `search_field`: 검색할 컬럼 (`ActorLoginId`, `ActorName`, `IpAddress`, `Action`, `TargetId`, `Details` 중 선택)
  - `match_type`: 검색 방식 (`exact` 또는 `like`, 기본값: `like`)
  - `keyword`: 검색어 문자열
- **Response JSON**:
  ```json
  {
    "status": "success",
    "data": [
      {
        "AuditId": 102,
        "ActorLoginId": "admin",
        "ActorName": "관리자",
        "Action": "USER_ROLE_CHANGE",
        "TargetId": "user1",
        "IpAddress": "127.0.0.1",
        "CreatedAt": "2026-08-04 10:12:33"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 50,
      "total_count": 1520,
      "total_pages": 31
    }
  }
  ```

---

## 🚀 5. 검토 및 운영 반영(Merge) 수칙

- 본 파일들은 `Staging/` 폴더 내에 위치하므로 운영 환경(`app.py`, `templates/audit_logs.html`)에는 즉시 영향을 주지 않습니다.
- 사용자 리뷰 후 승인이 이루어지면 `Staging/Staging_app_patch.py`의 엔드포인트를 `app.py`에 병합하고, `Staging/Staging_audit_logs.html`을 `templates/audit_logs.html`로 교체(Merge)합니다.

---

## 🛠️ 6. [Gemini 3.1 Pro 리뷰] 수정 및 보완 요구사항 (Flash 모델 작업 지침)

이 섹션은 최초 작성(Flash)된 코드의 부족한 점을 보완하기 위해 Pro 모델이 작성한 리뷰 및 수정 지침입니다. 다음 사항을 코드에 반영해야 합니다.

1. **권한 체계의 불일치 (하드코딩 제거)**
   - **현재 상태**: `session.get('role') != 'admin'`을 사용하여 하드코딩으로 권한을 검사함.
   - **수정 목표**: 기존 `app.py` 표준 방식인 `check_menu_permission('audit_logs')` 함수를 사용하도록 변경하여 RBAC 구조 일관성 유지.

2. **표준 세션 데코레이터 적용**
   - **현재 상태**: API 엔드포인트 내에서 `if 'user_id' not in session:` 수동 검사 수행.
   - **수정 목표**: `app.py` 표준 방식대로 `@login_required` 데코레이터를 적용하여 코드 가독성 및 무결성 확보.

3. **입력값 형변환 오류(Type Casting Error) 예외 처리**
   - **현재 상태**: `page = int(request.args.get('page', 1))` 처리 시 문자가 입력되면 500 에러 발생.
   - **수정 목표**: 숫자가 아닌 잘못된 파라미터가 들어올 경우, 500 에러가 아닌 400 Bad Request 로 처리되거나 기본값(1, 200 등)으로 자동 Fallback 되도록 방어 로직 추가.

4. **전체 검색(all) 시 JSON 데이터 컬럼(OldValue, NewValue) 누락 보완**
   - **현재 상태**: `all` 키워드 검색 시 기본 컬럼(Details 포함)만 `LIKE` 검색 범위에 포함됨.
   - **수정 목표**: DB에 저장된 `OldValue`, `NewValue` 컬럼 역시 JSON 텍스트이므로 `LIKE` 조건(`%keyword%`)에 추가하여 데이터 변경 이력 검색 효율을 극대화.

5. **권한에 따른 Page Size 제한(DoS 방어) 유연성 제공**
   - **현재 상태**: 무조건 최대 1,000개로 하드코딩 제한 (`max 1000`). 관리자가 대량 로그를 조회할 권리마저 제한되는 문제 발생.
   - **수정 목표**: 유효한 권한을 갖춘 세션(`check_menu_permission` 통과)의 경우에는 관리자의 사용성을 보장하기 위해 상한선(limit)을 10,000개 등으로 대폭 상향하거나 제한을 완화. (프론트엔드 HTML의 `<input type="number" max="1000">` 속성 역시 `max="10000"` 등으로 수정 필요).

6. **[긴급 버그 수정] 키워드 미입력 시 전체 이력 표출 및 DB 스키마 바인딩 결함 보완**
   - **원인 분석**: `audit_logs` 테이블에는 `ActorName` 및 `Details` 물리 컬럼이 존재하지 않고 `ActorLoginId`, `TargetTable`, `OldValue`, `NewValue`가 존재함. 이로 인해 `SELECT ActorName, Details` 쿼리 실행 시 `sqlite3.OperationalError`가 발생하여 키워드 유무와 관계없이 에러가 도출됨.
   - **수정 목표**: 
     1) `audit_logs a LEFT JOIN users u ON a.ActorLoginId = u.LoginId` 구문으로 `ActorName`(`COALESCE(u.Name, a.ActorLoginId, 'System')`)을 정규 쿼리로 안전 결합.
     2) 키워드가 없거나 빈 문자열일 경우 `WHERE` 절을 생성하지 않고 전체 감사 로그 데이터를 `ORDER BY AuditId DESC LIMIT ? OFFSET ?`로 즉시 반환하여 키워드 미입력 시 전체 이력 조회가 완벽히 수행되도록 보완.

---

## 🛡️ 7. [Gemini 3.1 Pro 2차 리뷰] 프론트엔드 조작 및 DoS 보안 취약점 검토

사용자 피드백에 따라 프론트엔드(`Staging_audit_logs.html`)의 `max="10000"` 등 HTML 요소가 브라우저 개발자 도구(F12)를 통해 임의 조작될 경우를 대비한 보안 검토 이력입니다. 
Flash 모델은 향후 관련 API 및 UI 개발 시 아래와 같은 **서버 사이드 검증(Server-Side Validation)** 원칙을 반드시 기억하고 준수해야 합니다.

1. **프론트엔드 코드 조작 우려 사항 (사용자 지적)**
   - 브라우저 개발자 도구로 `<input type="number" max="10000">` 제한을 `max="999999"` 등 비정상적인 값으로 수정하여 요청할 경우, 서버 메모리를 고갈시키는 DoS(Denial of Service) 공격이 발생할 수 있다는 위험성 지적.
2. **백엔드(서버) 이중 보안 및 강제 제한(Clamping) 원칙 확립**
   - 백엔드에서 사용자 권한은 클라이언트 전달 값이 아닌 암호화 서명된 `session` 객체를 통해 안전하게 가져오므로 클라이언트가 권한(Role)을 임의 변조할 수 없습니다.
   - 프론트엔드에서 비정상적인 `per_page` 값을 전달하더라도, 백엔드 내부 로직에서 `elif per_page > max_limit: per_page = max_limit`를 통해 안전한 상한선(일반 1,000 / 관리자 10,000)으로 **강제 하향 조정(Clamping)** 하도록 처리되어야 합니다.
   - **최종 결론**: HTML 등 프론트엔드의 제약 사항(max)은 오직 사용자 편의성(UI/UX) 목적이며, 실제 데이터 조작 및 자원 한도 초과 방어는 오직 백엔드 서버 로직에서 전적으로 통제해야 완벽히 안전합니다.
