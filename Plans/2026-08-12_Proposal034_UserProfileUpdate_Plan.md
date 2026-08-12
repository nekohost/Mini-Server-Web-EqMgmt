# [제안-034] 내 정보 사용자 프로필(아이디, 이름, 닉네임) 본인 인증 기반 수정 기능 기획서

## 1. 개요 및 목적
- **목적**: 마이페이지(`/mypage`)에서 사용자가 본인의 기본 정보(아이디 `LoginId`, 실명 `Name`, 닉네임 `NickName`)를 직접 수정할 수 있도록 기능을 제공합니다.
- **보안 핵심 수칙**: 본인 소유권 확인을 위해 **현재 비밀번호(`current_password`) 검증**을 필수로 거쳐야만 프로필 변경이 이루어집니다.
- **Rule.md 준수 수칙**:
  - `Rule 4-3` (코드 주석 보존 수칙: `[역할]`, `[의존성 관계]`, `[변경 시 영향도]` 명시).
  - `Rule 4-5-3` (세션 및 CSRF 토큰 검증).
  - `Rule 7-3` (Staging 검증 절차 준수).

---

## 2. 세부 구현 계획

### 2.1. 백엔드 API 신설 (`Staging/Staging_app.py` ➡️ `app.py`)
- **엔드포인트**: `POST /api/users/update_profile`
- **인증 및 보안**:
  - `@login_required` 및 `@csrf_required` 적용.
  - 요청 바디: `{ "login_id": "...", "name": "...", "nickname": "...", "current_password": "..." }`
- **검증 로직**:
  1. 필수값 체크: `login_id`, `name`, `nickname`, `current_password` 전달 여부 확인.
  2. 본인 인증: DB의 `user['Password']`와 `current_password`를 `check_password_hash()`로 검증. 불일치 시 400 반환 ("현재 비밀번호가 올바르지 않습니다.").
  3. 아이디(`LoginId`) 변경 시 타 계정 중복 체크:
     - `SELECT UserId FROM users WHERE LoginId = ? AND UserId != ?`
     - 존재 시 400 반환 ("이미 사용 중인 아이디입니다.").
  4. DB 업데이트: `UPDATE users SET LoginId=?, Name=?, NickName=?, UpdatedAt=? WHERE UserId=?`
     - `try-except sqlite3.IntegrityError` 예외 처리 추가 (UNIQUE 제약 방어).
  5. 세션 정보 갱신: `session['user']['LoginId']`, `session['user']['Name']`, `session['user']['NickName']` 갱신.
  6. 보안 감사 로그 기록: `log_audit(user['UserId'], user['LoginId'], 'UPDATE_USER_PROFILE', 'users', user['UserId'], old_data, new_data)`

### 2.2. 프론트엔드 UI/UX (`Staging/Staging_mypage.html` ➡️ `templates/mypage.html`)
- **프로필 카드 수정**:
  - 마이페이지 사용자 프로필 헤더 우측에 `[✏️ 프로필 수정]` 버튼 배치.
- **프로필 수정 모달 (`profileModal`)**:
  - 아이디, 이름, 닉네임 입력 필드 (기존 사용자 정보로 기본 세팅).
  - **현재 비밀번호 확인 입력 필드** (필수 입력).
  - 메시지 출력 영역 및 [저장하기] 버튼.
- **비동기 처리 & UX**:
  - 저장 클릭 시 `showGlobalLoading('프로필 정보를 변경 중입니다...')` 연동.
  - 성공 시 메시지 출력 후 모달 닫기 & 화면 표시 정보(아이디, 이름, 닉네임) 즉시 동기화.

### 2.3. 스테이징 검증 파이프라인 (`Staging/`)
1. `Staging/Staging_app.py` 및 `Staging/Staging_mypage.html` 작성 후 독립 테스트 실행.
2. 사용자 승인 획득 후 `app.py` 및 `templates/mypage.html`로 병합.

---

## 3. 검증 계획 (Verification Plan)
1. **현재 비밀번호 오입력 테스트**: 틀린 비밀번호 입력 시 프로필이 변경되지 않고 에러 메시지가 표시되는지 검증.
2. **아이디 중복 테스트**: 이미 존재하는 타 계정의 LoginId로 변경 시도 시 400 에러 반환 검증.
3. **정상 프로필 변경 테스트**: 올바른 비밀번호 입력 후 아이디/이름/닉네임이 정상 변경되고, DB 및 세션, UI가 실시간으로 갱신되는지 확인.
4. **감사 로그 검증**: `audit_logs` 테이블에 `UPDATE_USER_PROFILE` 이벤트가 올바른 행위자와 변경값으로 남는지 확인.
