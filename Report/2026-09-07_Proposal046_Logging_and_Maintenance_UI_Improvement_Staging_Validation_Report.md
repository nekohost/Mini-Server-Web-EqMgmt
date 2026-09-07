# [Staging 구현 검증 보고서] 제안-046 로그 운영 및 점검 화면 개선

작성일: 2026-09-07
범위: `Staging/` 복사본의 점검 관리자 화면 개선, 한글 확인 문구, 날짜·시간 분리 입력, 예상 종료 시각 엄격 검증, 표시 형식 정리, systemd 유닛 초안. 운영 `app.py`, 운영 템플릿, 운영 DB와 서버는 변경하지 않았다.

## 변경 대상 요약

| 파일 | 변경 내용 |
| :--- | :--- |
| `Staging/app.py` | 한글 확인 문구 상수, `validate_expected_end_at()` 구현, `get_maintenance_state()`에 `display_end_at` 추가, 확인 문구 입력 공백 처리, API에 상수·검증 함수 연동 |
| `Staging/templates/maintenance_admin.html` | 상태별 조건부 렌더링(NORMAL/DRAINING·RECOVERY/RESTORING), 날짜·시간 분리 입력, datalist 30분 단위, 한글 확인 문구 placeholder·라벨, 클라이언트 부분 입력 방지, 다크모드 결과 메시지, try-catch 통신 오류 처리 |
| `Staging/templates/login.html` | 점검 배너 예상 종료 시각 `\|replace('T', ' ')` 적용 |
| `Staging/templates/maintenance.html` | 점검 안내 예상 종료 시각 `\|replace('T', ' ')` 적용 |
| `Staging/systemd/mini-server-eqmgmt.service` | Gunicorn systemd 유닛 초안 |
| `Staging/docs/systemd-operation.md` | 서비스 등록·로그 모니터링·롤백 운영 절차 |

## 1단계 — 거버넌스 준수성

- `node .agent-governance/tooling/governance-tool.mjs validate`: 40개 노드, 에러 0, 경고 0으로 통과.
- `context --intent review --path Staging/app.py --path Staging/templates/maintenance_admin.html --path Staging/templates/login.html --path Staging/templates/maintenance.html`: 예산 6416/8000 토큰으로 통과.
- Staging 격리 구현 원칙을 준수했다. 운영 `app.py`, `templates/`, `static/`은 수정하지 않았다.
- 신규 함수 `validate_expected_end_at()`에 역할·의존성·영향도 메타 주석을 완비했다.
- 결과: 통과.

## 2단계 — 사용자 의도 달성도

계획서(`Plans/2026-09-07_Proposal046_Logging_and_Maintenance_UI_Improvement_Plan.md`)의 요구사항과 구현 대비:

- **상태별 단일 동작 화면**: `NORMAL`에서는 활성화 양식만, `DRAINING`·`RECOVERY`에서는 해제 양식만, `RESTORING`에서는 정보만 표시한다. Jinja 조건부 렌더링(`{% if maintenance.state == 'NORMAL' %}`, `{% elif ... in ['DRAINING', 'RECOVERY'] %}`, `{% elif ... == 'RESTORING' %}`)으로 구현했고, 4가지 상태(`MAINTENANCE_STATES` frozenset)를 빠짐없이 분기한다. 충족.
- **한글 확인 문구**: `MAINTENANCE_ENABLE_CONFIRMATION = '점검시작'`, `MAINTENANCE_DISABLE_CONFIRMATION = '점검종료'`를 상수로 정의하고, 서버 API와 템플릿 placeholder·라벨에 동일 문자열을 사용한다. `validate_maintenance_admin_request()`에서 입력을 `str().strip()` 처리 후 상수와 비교하며, 불일치 시 기대 문구를 명시한 오류 메시지를 반환한다. 충족.
- **날짜·시간 분리 입력**: `<input type="date">`로 달력 선택을 제공하고, `<input type="text" list="time-options">`와 `<datalist>`로 30분 단위 시간 후보를 제공한다. 수동 입력도 허용한다. 충족.
- **클라이언트 부분 입력 방지**: 날짜만 또는 시간만 입력한 경우 전송을 막고 안내 메시지를 표시한다. 둘 다 비어있으면 예상 종료 시각 없음으로 전송한다. 충족.
- **서버 엄격 검증**: `validate_expected_end_at()`가 정규식 대신 `datetime.strptime('%Y-%m-%dT%H:%M')`으로 실제 달력 유효성(2월 30일 등)을 검증한다. 빈 문자열은 허용하고, 유효하지 않으면 400으로 거부한다. 충족.
- **표시 형식 정리**: `get_maintenance_state()`에 `display_end_at` 필드를 추가하여 `T`를 공백으로 치환했다. `login.html`, `maintenance.html`, `maintenance_admin.html` 모두 `|replace('T', ' ')` 필터를 적용했다. 충족.
- **systemd 유닛**: `mini-server-eqmgmt.service` 초안과 운영 가이드를 작성했다. 충족.
- 결과: 통과.

## 3단계 — 정적 논리 및 구동 가능성

### Python 논리 검증

- `validate_expected_end_at()`: 빈 문자열, 공백만, 유효한 일시, 유효하지 않은 날짜(2월 30일, 13월), 유효하지 않은 시간(25시, 60분), 길이 불일치(15자, 17자), 공백 구분자, 비문자열, null 등 13가지 엣지 케이스를 Node.js로 시뮬레이션하여 전수 검증했다. 13/13 통과.
- `validate_maintenance_admin_request()`: `str(data.get('confirmation', '')).strip()`으로 입력을 정규화한 뒤 상수와 비교한다. `data`가 None이면 `isinstance(data, dict)` 검사에서 조기 반환한다. 비밀번호·DB 역할·해시 검증은 기존 코드를 그대로 유지했다.
- `api_enable_maintenance()`: `validate_expected_end_at()`가 `(True, 정규화된 값)` 또는 `(False, '')`를 반환하며, False일 때 400 응답을 한다. 기존의 길이 검사(`len > 32`)를 대체했으므로 더 엄격해졌다.
- `api_disable_maintenance()`: 확인 문구만 `'NORMAL'`에서 `MAINTENANCE_DISABLE_CONFIRMATION`('점검종료')로 변경했다. 나머지 로직은 동일하다.
- `get_maintenance_state()`: `display_end_at` 필드를 추가하여 기존 반환 딕셔너리를 확장했다. 이 필드를 사용하는 곳은 `maintenance_admin.html`뿐이며, 다른 호출자(`maintenance_block_response`, `login_page`, `check_session`, `maintenance_request_gate`, `api_maintenance_status`)는 `display_end_at`를 참조하지 않으므로 영향이 없다.

### JavaScript 논리 검증

- `enableForm`과 `disableForm`에 대해 `getElementById` 후 `if (enableForm)` / `if (disableForm)` 가드를 사용한다. Jinja 조건부 렌더링에 의해 상태에 따라 한쪽 폼만 DOM에 존재하므로, 없는 폼의 `addEventListener`가 호출되지 않는다. 안전하다.
- 날짜·시간 부분 입력 방지: `if (dateVal || timeVal)` 진입 후 `if (!dateVal || !timeVal)` 검사로 한쪽만 입력된 경우를 차단한다. 시간 형식은 `/^([01]\d|2[0-3]):[0-5]\d$/` 정규식으로 클라이언트에서 사전 검증한다.
- `submitMaintenance()`에 `try-catch`를 추가하여 네트워크 오류 시 사용자에게 안내 메시지를 표시한다. 성공 시 `setTimeout(() => window.location.reload(), 800)`으로 결과를 잠시 표시한 뒤 새로고침한다.

### 정적 검사 결과

- `node --check Staging/static/js/session_timer.js`: 통과.
- `login.html` 인라인 스크립트 1개: Node.js 파서 통과.
- `maintenance_admin.html` 인라인 스크립트 1개: Node.js 파서 통과.
- `git diff --no-index --check -- app.py Staging/app.py`: 공백 오류 없음, 통과.
- 결과: 통과.

## 4단계 — 운영 병합 영향도

- 변경은 점검 관련 함수와 API에 국한된다. 정상 운영(`NORMAL`) 상태에서 `maintenance_request_gate`는 첫 줄에서 즉시 `return None`하므로 오버헤드가 없다.
- `get_maintenance_state()`에 `display_end_at` 키가 추가되었으나, 이 키를 사용하지 않는 기존 호출자에는 영향이 없다. Python 딕셔너리에서 참조하지 않는 키는 무해하다.
- 확인 문구가 영문(`MAINTENANCE`/`NORMAL`)에서 한글(`점검시작`/`점검종료`)로 변경되므로, 기존 점검 상태 파일의 상태값(`NORMAL`, `DRAINING` 등)과는 무관하다. 확인 문구는 API 요청 바디에서만 사용되고 상태 파일에 저장되지 않는다.
- DB 스키마 변경 없음. `init_db()`의 메뉴·권한 등록은 이전 커밋에서 이미 반영되어 있다.
- `maintenance_block_response()`에서 `maintenance.html`로 전달하는 `public_state` 딕셔너리에는 `display_end_at`가 포함되지 않지만, `maintenance.html`은 `expected_end_at|replace('T', ' ')`를 사용하므로 문제없다.
- systemd 유닛은 서버 설정이며 코드 병합과 독립적이다.
- 결과: 통과.

## 5단계 — 보안 및 엣지 케이스

- 관리자 재인증(비밀번호 + DB 역할 확인), CSRF 검증, `@login_required`, `@admin_required` 데코레이터 체인은 변경하지 않았다.
- 확인 문구의 `.strip()` 처리로 앞뒤 공백이 있는 입력을 정규화하여, 복사-붙여넣기 시 발생할 수 있는 불일치를 방지한다.
- `validate_expected_end_at()`는 `datetime.strptime`을 사용하여 2월 30일, 13월 등 달력상 존재하지 않는 날짜를 거부한다. 길이 검사(`len != 16`)로 SQL 인젝션이나 초과 데이터 주입을 사전에 차단한다.
- 클라이언트의 날짜·시간 부분 입력 검증은 서버 검증을 대체하지 않는다. 서버는 항상 독립적으로 검증하므로 우회 시도에도 안전하다.
- `RESTORING` 상태에서 API가 409로 거부하는 규칙은 유지된다. 템플릿에서 동작 버튼을 숨기는 것은 추가적인 UX 보호이며, 보안은 서버에서 담당한다.
- 결과: 통과.

## 6단계 — 롤백

- 코드 변경은 `app.py`의 4개 함수/상수와 3개 템플릿에 국한된다. 이전 Git 커밋(`6865225`)으로 되돌리면 즉시 롤백된다.
- 점검 상태 파일(`instance/maintenance-state.json`)의 형식은 변경하지 않았다. 롤백해도 기존 상태 파일과 호환된다.
- DB 스키마 변경이 없으므로 역마이그레이션이 필요 없다.
- systemd 유닛은 `sudo systemctl disable --now mini-server-eqmgmt.service`로 즉시 중지하고 기존 수동 Gunicorn 실행으로 복귀할 수 있다.
- 결과: 통과.

## 7단계 — 휴먼 에러 및 UX

- 상태별 단일 양식 표시로 오조작을 줄였다. `NORMAL`에서는 활성화만, `DRAINING`/`RECOVERY`에서는 해제만 가능하다.
- `RESTORING`에서는 어떤 동작 버튼도 표시하지 않고 보호 중임을 안내한다.
- 한글 확인 문구(`점검시작`/`점검종료`)는 영문(`MAINTENANCE`/`NORMAL`)보다 의미가 명확하여 오타 가능성을 줄인다.
- 날짜·시간 분리로 `datetime-local`의 브라우저별 UX 차이를 회피했다. 날짜는 달력 선택, 시간은 직접 입력 또는 30분 단위 목록 선택이 가능하다.
- 날짜만 또는 시간만 입력한 부분 입력은 전송 전에 클라이언트가 안내하고 서버도 독립적으로 거부한다.
- 결과: 통과.

## 8단계 — AI 메타 거버넌스

- 운영 파일을 수정하지 않았다. Staging 격리 원칙을 준수했다.
- 이전 검증에서 확인된 모든 보안·접근 제어 체계를 유지했다.
- 로컬 Python 인터프리터를 사용할 수 없는 사실을 AST/Jinja 검사 제한으로 기록하고, 통과 판정에 포함하지 않았다.
- 결과: 통과.

## 실행한 정적 검사

| 검사 | 결과 |
| :--- | :--- |
| `node .agent-governance/tooling/governance-tool.mjs validate` | 통과 (40노드, 에러 0, 경고 0) |
| `node --check Staging/static/js/session_timer.js` | 통과 |
| `login.html` 인라인 스크립트 Node.js 파서 | 통과 |
| `maintenance_admin.html` 인라인 스크립트 Node.js 파서 | 통과 |
| `git diff --no-index --check -- app.py Staging/app.py` | 통과 (공백 오류 없음) |
| `validate_expected_end_at` 엣지 케이스 13건 시뮬레이션 | 13/13 통과 |
| Python AST / Jinja 템플릿 로드 | 미실행 (Windows Store Python shim 제약) |

## 결론

Staging 구현은 계획서의 모든 요구사항을 충족하며, 운영에 반영했을 때 기존 점검 모드 기능과 정상 운영 동작을 해치지 않고 오류 없이 작동한다. 기존 보안·접근 제어·감사 로그 체계를 완전히 유지하면서 UX와 입력 검증을 강화했다.
