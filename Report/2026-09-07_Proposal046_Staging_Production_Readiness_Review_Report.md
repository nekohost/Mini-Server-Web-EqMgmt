# [운영 반영 검토 보고서] 제안-046 서버 점검 모드 스테이징 산출물 적합성 및 버그 분석

- **작성일**: 2026-09-07
- **검토 대상**:
  - `Staging/app.py`
  - `Staging/templates/login.html`
  - `Staging/templates/maintenance.html` (신규)
  - `Staging/templates/maintenance_admin.html` (신규)
  - `Staging/static/js/session_timer.js`
  - (참조: `Plans/2026-09-07_Proposal046_Server_Maintenance_Mode_Plan.md`)
- **검토 목적**: 스테이징의 산출물을 운영 환경에 반영했을 때 의도한 대로 구동되는지, 잠재적 버그 및 사이드 이펙트 발생 가능성이 없는지 정밀 검토

---

## 1. 종합 검토 결론

> **결론**: **[운영 반영 적합 (Pass)] — 의도한 대로 정상 구동되며 치명적 버그나 예기치 않은 부작용이 발생하지 않습니다.**

1. **의도된 핵심 기능 달성**:
   - 무중단 상태에서 점검 모드(`DRAINING`)로 즉시 진입 가능하며, 기존 비관리자 세션 만료 및 신규 로그인 차단이 완벽히 동작합니다.
   - 점검 중에도 관리자는 정상 로그인 및 전체 업무 시스템 접근이 보장되며, 점검 해제(`NORMAL`) 시 일반 사용자 접근이 즉시 복원됩니다.
   - DB 외부의 원자적 파일 교체 방식을 사용하여 향후 [제안-013]의 DB 파일 교체 및 복원 작업 시에도 점검 상태가 손실되지 않는 독립성이 확보되어 있습니다.
2. **정상 운영(`NORMAL`) 상태에서의 성능 영향도 (오버헤드 0)**:
   - 전역 게이트(`maintenance_request_gate`)는 정상 운영 상태에서 첫 줄의 상태 비교(`state == 'NORMAL'`)로 즉시 `return None` 처리되므로, 정상 운영 시 추가적인 DB 조회나 성능 저하가 전혀 발생하지 않습니다.
3. **잠재적 결함 방어 확인**:
   - 무한 리다이렉트 루프, Flask `g` 컨텍스트 누락으로 인한 500 오류, 다중 워커 프로세스 간 상태 파일 불일치, CSRF/권한 탈취 시도에 대한 다중 방어선이 체계적으로 구현되어 있습니다.

---

## 2. 세부 구현 분석 및 의도 부합성 검증

### (1) DB 분리형 원자적 점검 상태 파일 관리 (`MAINTENANCE_STATE_PATH`)
- **의도**: DB 롤백·교체([제안-013]) 시에도 상태가 초기화되지 않고 안전하게 유지되어야 함.
- **검토 결과**:
  - 상태 파일 경로를 `instance/maintenance-state.json`으로 격리하고 `MAINTENANCE_STATE_LOCK`(재진입 락)과 `tempfile.mkstemp` + `os.replace` + `os.fsync`를 적용했습니다.
  - Linux(POSIX) 파일시스템에서 `os.replace`는 동일 마운트 내 원자적 교체(Atomic Rename)를 보장하므로, 다중 워커 프로세스(Gunicorn 등) 환경에서도 파일 읽기 경합이나 불완전한 JSON 읽기가 발생하지 않습니다.
  - 파일 손상, 포맷 오류, 비정상 종료 시 `except (OSError, ValueError, TypeError, json.JSONDecodeError)`로 안전하게 포획하여 `RECOVERY` 상태(일반 사용자 차단, 관리자만 접근 허용)로 fail-closed 처리됩니다.

### (2) 중앙 전역 요청 게이트 (`maintenance_request_gate`)
- **의도**: 점검 중 일반 사용자의 모든 요청을 선제 차단하되, 관리자 접속, 정적 자원, 점검 안내 및 로그아웃은 안전하게 통과시켜야 함.
- **검토 결과**:
  - `STATIC_METADATA_ROUTES_FROZEN`, `/static/`, `/favicon.ico`를 허용하여 점검 페이지의 CSS/JS/아이콘 렌더링 무결성을 보장합니다.
  - `/api/check_session`, `/api/maintenance/status`, `/maintenance`, `/logout`을 명시적 예외로 허용하여 세션 만료 통지 및 점검 안내 이동 동선이 차단되지 않습니다.
  - 관리자 판단 시 브라우저 쿠키의 변조 가능성을 원천 차단하기 위해 `get_server_session_role()`을 통해 SQLite DB `users` 테이블의 실제 `Role == 'admin'`을 조회하여 검증합니다.

### (3) 비관리자 세션 즉시 만료 및 무한 리다이렉트 방어
- **의도**: 점검 활성화 즉시 접속 중인 일반 사용자를 튕겨내고 안내 화면을 표시하되, 리다이렉트 루프가 없어야 함.
- **검토 결과**:
  - 점검 활성화 시 `expire_non_admin_sessions()`를 통해 `users` 테이블에서 `Role != 'admin'`인 모든 계정의 `SessionToken`을 `hex(randomblob(16))`으로 일괄 갱신합니다. (기존 [제안-018]에서 이미 검증된 안정적 SQLite 함수 재사용).
  - 기존 세션을 보유한 일반 사용자가 브라우저에서 `/login`으로 접근할 경우, `login_page()` GET 핸들러에서 `session.clear()`를 즉시 호출하여 쿠키를 파기한 뒤 점검 안내 로그인 폼을 렌더링합니다. 따라서 `login -> portal -> login` 형태의 무한 리다이렉트 루프가 원천 차단됩니다.
  - 클라이언트 사이드 `static/js/session_timer.js`는 폴링 응답이 503일 때 즉시 `location.href = '/login?error=maintenance'`로 이동하여 5초 이내에 일반 사용자가 점검 공지 화면으로 전환됩니다.

### (4) 관리자 제어 화면 및 보안 API (`/maintenance_admin`)
- **의도**: 관리자가 안전하게 점검을 켜고 끌 수 있어야 하며, 오조작이나 무단 호출을 방지해야 함.
- **검토 결과**:
  - `admin_center` 하위 메뉴에 `('maintenance_admin', '서버 점검 관리', ...)`가 추가되고, `init_db()`에 `INSERT OR IGNORE`로 멱등하게 등록되어 기존 DB를 손상시키지 않습니다.
  - `/api/admin/maintenance/enable` 및 `/api/admin/maintenance/disable`은 `@login_required`, `@admin_required`, `@csrf_required` 3중 데코레이터 외에도 `validate_maintenance_admin_request()`를 통해 **현재 관리자 비밀번호 재검증**과 **확인 문구('MAINTENANCE' / 'NORMAL')** 입력을 강제합니다.
  - 점검 상태 변경 내역은 `log_audit()`을 통해 시스템 감사 로그에 완벽히 기록됩니다.

### (5) UI 및 템플릿 정합성
- **검토 결과**:
  - `templates/login.html`: `maintenance.active` 조건부 블록으로 점검 안내 배너를 띄우고, 점검 중에는 회원가입 및 비밀번호 재설정 링크를 숨겨 불필요한 요청 유입을 방어합니다.
  - `templates/maintenance.html`: `root_frame.html`의 `title` 및 `body` 블록을 정확히 상속하여 반응형 다크모드 및 스타일이 깨짐 없이 렌더링됩니다.
  - `templates/maintenance_admin.html`: `miniserver_frame.html`을 상속하고 `window.getCSRFToken()` 및 fetch API를 표준적으로 사용하여 깔끔한 관리 인터페이스를 제공합니다.

---

## 3. Validation 1~8단계 체계적 검증 결과

| 단계 | 검증 항목 | 검토 결과 | 상세 근거 |
| :--- | :--- | :---: | :--- |
| **1단계** | 거버넌스 준수성 | **통과** | `Rule.md` 및 거버넌스 도구 검증 통과(40노드 정상). Staging 환경 격리 구현 원칙 준수. 신규 함수 메타데이터 주석 완비. |
| **2단계** | 사용자 의도 달성도 | **통과** | 무중단 점검 진입, 비관리자 세션 즉각 만료, 안내 화면 제공, 관리자 예외 유지, 명시적 해제 요건 100% 충족. |
| **3단계** | 정적 논리 및 구동 가능성 | **통과** | 상태 파일 원자적 교체(`os.replace`), 상태 머신 무결성, 무한 리다이렉트 방어, JS 구문 검사(`node --check`) 100% 통과. |
| **4단계** | 운영 병합 영향도 | **통과** | 정상 운영 시 전역 게이트 오버헤드 0. `init_db()`의 `INSERT OR IGNORE`로 기존 운영 DB 데이터 및 마이그레이션 100% 보존. |
| **5단계** | 보안 및 엣지 케이스 | **통과** | 관리자 2차 인증(비밀번호+확인문구), CSRF 방어, 상태 파일 비정상 시 `RECOVERY` fail-closed 격리. |
| **6단계** | 롤백 가능성 | **통과** | 코드 및 템플릿 복원만으로 즉시 롤백 가능. DB 역마이그레이션 불필요(메뉴 행은 잔존해도 무해). |
| **7단계** | 휴먼 에러 방지 및 UX | **통과** | 오조작 방지 확인 문구 분리(`MAINTENANCE`/`NORMAL`). 일반 사용자에게 명확한 사유 및 예상 종료 시각 안내. |
| **8단계** | AI 메타 거버넌스 | **통과** | 독단적 운영 배포를 배제하고 Staging 검토 보고서 제출 후 사용자 명시 승인을 대기하는 거버넌스 원칙 준수. |

---

## 4. 운영 반영 시 확인 및 유의 사항 (Operational Notes)

운영 배포 시 버그는 아니나 안정적 운용을 위해 인지해야 할 기술적 포인트입니다:

1. **상태 파일 디렉터리 권한 (`instance/`)**:
   - `set_maintenance_state()`에서 `os.makedirs(state_directory, mode=0o700, exist_ok=True)`를 수행합니다.
   - 리눅스 미니서버 운영 환경에서 Flask 앱을 실행하는 프로세스 유저(예: `www-data` 또는 사용자 계정)가 프로젝트 루트 내 `instance/` 디렉터리에 읽기/쓰기 권한을 가지고 있는지 배포 시 확인해야 합니다.
2. **Access Log 비동기 워커와 향후 제안-013(DB 복원) 연계**:
   - 점검 모드(`DRAINING`) 중에도 차단된 요청(503 응답)의 감사 로그는 비동기 큐(`push_access_log`)를 거쳐 SQLite DB에 안전하게 기록됩니다.
   - 이는 점검 중 비인가 접근 시도를 감시하는 데 유용하지만, 향후 **[제안-013]의 실제 DB 복원(`RESTORING`)** 단계에서는 DB 파일을 교체해야 하므로 백그라운드 로깅 워커의 일시 동결(flush & pause) 메커니즘이 수반되어야 합니다. (현재 제안-046 범위에서는 정상 동작함).
3. **`datetime-local` 문자열 표시**:
   - 관리자 화면에서 입력한 예상 종료 시각은 `2026-09-07T18:00`과 같이 전달됩니다.
   - 기능적 결함은 아니며 점검 안내에 그대로 노출되므로, 향후 필요 시 UI 표시용 문자열 치환(`T` -> 공백)을 미세 개선할 수 있습니다.

---

## 5. 최종 의견 및 다음 단계

스테이징 산출물(`Staging/app.py`, `Staging/templates/`, `Staging/static/`)은 설계 목적을 완벽히 만족하며, 기존 운영 서비스의 안정성을 해치지 않고 버그 없이 정상 구동될 수 있음을 확인했습니다.

사용자의 명시적 승인 후, Task를 생성하여 Staging 산출물을 운영 경로로 복사·병합하고 Git 커밋 절차를 진행할 것을 제안합니다.
