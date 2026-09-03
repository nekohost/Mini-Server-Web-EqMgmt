---
id: engineering.security
version: 1
parent: core.kernel
source_rules: [RULE-4.5.1, RULE-4.5.2, RULE-4.5.3, RULE-6.1.4]
source_validations: [VAL-PHASE.4.2, VAL-PHASE.5.1, VAL-PHASE.5.2, VAL-PHASE.5.3, VAL-PHASE.5.4]
source_entrypoints: []
human_rule_sections: ["4-5-1", "4-5-2", "4-5-3", "6-1-4", "10-5-2", "10-6-1", "10-6-2", "10-6-3", "10-6-4"]
source_section_digest: 4B9627545C4819DFA9B0BD82D4CD56C49551690084F5BCEF20F305B4EB491CBD
always_load: false
may_relax_parent: false
---

# 보안과 환경 설정

시스템이 인터넷에 공개될 수 있음을 전제로 한다.

1. `app.secret_key`, 계정, API 토큰, 인증서 개인키 등 민감 정보를 소스에 평문으로 기록하거나 Git에 포함하지 않는다.
2. 비밀은 환경변수 또는 `.env`로 분리하고 `.gitignore` 제외 여부를 확인한다.
3. `debug=True`를 하드코딩하지 않는다. `FLASK_DEBUG` 환경변수로 제어하며 `debug=False`도 무조건 강제하지 않는다.
4. `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE` 등 세션 쿠키 정책을 엄격히 적용한다.
5. 모든 외부 입력을 불신하고 서버 세션을 기준으로 권한을 확인한다.
6. SQL Injection, XSS, CSRF, 비정상 타입, 내부 오류 정보 노출을 검증한다.
7. 문서와 대화 기록의 비밀은 자리표시자로 치환한다.


