# [제안-030] 메일링 서비스 기반 통합 인증(계정/메일) 최종 기획서

`Rule.md` 제7조(문서 생명주기)에 의거하여 작성된 영구 기획서입니다.

---

## 0. 선행 문서 상태 갱신 (Rule 7-1)
- 현재 `[보류]` 상태인 `PROPOSALS.md` 및 `UNIMPLEMENTED_PROPOSALS.md`의 **[제안-030]** 항목을 `[채택 / 대기중]`으로 변경하고 `ROADMAP.md` 및 `UNIMPLEMENTED_ROADMAP.md`에 등록 완료하였습니다.

---

## 1. 외부 라이브러리(`requests`) 및 아키텍처 확장 계획
- **조치 사항:** `requirements.txt`에 `requests`를 추가 기록하고 미니서버에 반영합니다.
- **아키텍처 변경:** 모놀리식 `app.py` 구조 개선을 위해 `utils/` 디렉토리를 신설하고 `utils/__init__.py`와 `utils/mailer.py`를 생성합니다. (환경 변수 누락 시 서버 시작 실패 로직 추가 포함)

---

## 2. DB 스키마 마이그레이션 및 Rule 4-2 의존성 체인

### [MODIFY] `users` 테이블 마이그레이션 (`sys_migrations` 적용)
- SQLite 제약을 고려한 2단계 실행:
  1. `ALTER TABLE users ADD COLUMN Email TEXT;`
  2. `CREATE UNIQUE INDEX idx_users_email ON users(Email) WHERE Email IS NOT NULL;`
> [!IMPORTANT]
> **Rule 4-2 동시 수정 체크리스트:**
> 1. `init_db()`: 신규 생성 `users` 테이블 스키마에 `Email TEXT UNIQUE` 추가 및 인덱스 생성 추가.
> 2. `register_page()`: `INSERT INTO users` 구문에 `Email` 추가.
> 3. `register.html`: `<form>` 내 이메일 `<input>` 영역 추가 및 JS `payload`에 추가.
> 4. `mypage.html`: 이메일 표출 및 수정 영역 추가.
> 5. `login()` API: 기존 로그인 성공 시 세션 객체(`session['user']`)에 `Email` 데이터도 함께 담도록 컬럼 확대.

### [NEW] `email_verifications` & `password_resets` 테이블 신설
- **email_verifications:** `Email(PK)`, `PinCode`(해시 저장), `ExpiresAt(3분)`, `IsVerified(0/1)`
- **password_resets:** `Token(PK, 난수 해시)`, `UserId`, `ExpiresAt(1시간)`, `IsUsed(0/1)`

### ⚠️ 기존 사용자의 `Email=NULL` 상태 핸들링 정책
- 로그인은 기존과 동일하게 허용하나, 대시보드 접근 시 "비밀번호 찾기 기능을 위해 이메일을 등록해 주세요" 라는 경고 배너를 표출하여 마이페이지로 유도합니다.

---

## 3. 백엔드(API) 상세 라우트 구현 (Rule 4-3 & 4-5 보안 적용)

> **※ Rule 4-3 준수:** 신설 및 수정되는 모든 라우트와 함수(`send_email` 등) 상단에는 반드시 `[역할]`, `[의존성 관계]`, `[변경 시 영향도]` 주석을 명시합니다.

### [NEW/MODIFY] API 라우트 및 보안(CSRF/토큰) 강화
- 모든 `POST` 요청에 CSRF 토큰 검증 추가.
- 비밀번호 재설정 성공 시 유저의 기존 세션 무효화(강제 로그아웃) 처리.
- PIN 및 토큰 재발송 쿨다운(1분) 및 시도 횟수 제한 방어 적용.

- **`POST /register`**: 이메일 인증(`IsVerified == 1`) 검사 추가.
- **`[NEW] POST /api/update_email`**: PIN 인증 후 이메일 수정 및 세션 갱신.
- **`[NEW] POST /api/auth/request_password_reset`**: 1회용 토큰 발급 및 이메일 전송.
- **`[NEW] GET /reset_password` & `POST /api/auth/reset_password`**: 셀프서비스 전용 비밀번호 재설정 페이지.

---

## 4. 프론트엔드(UI/UX) 상세 설계
- `register.html`, `mypage.html`: 이메일 폼 및 [인증 요청] 버튼, 타이머 제어 배치.
- `login.html`: "비밀번호를 잊으셨나요?" 링크 제공.
- `reset_password.html`: `root_frame.html`을 상속받아 비로그인 상태로 렌더링.

---

## 5. Verification Plan (격리 환경 검증)
1. **Rule 7-3 준수 (Staging):** 위 내용들을 `Staging/` 디렉토리에 파일로 격리하여 1차 구동합니다.
2. **테스트 환경 (Rule 5):** 모든 구동 및 테스트는 개발 PC가 아닌 **미니서버 SSH 환경**에서 수행합니다.
3. **Rule 7-2-2 및 Rule 7-3-4 최종 아카이빙:** 본 기획서는 `Plans/2026-08-12_Proposal030_MailingService_Plan.md` 경로에 영구 보존하며, 검증 및 운영 코드 병합 완료 후 Staging 디렉토리의 코드 파일들을 정리합니다.
