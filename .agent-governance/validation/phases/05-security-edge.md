---
id: validation.phase.05-security-edge
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.5.0, VAL-PHASE.5.1, VAL-PHASE.5.2, VAL-PHASE.5.3, VAL-PHASE.5.4]
source_entrypoints: []
human_rule_sections: ["10-6", "10-6-1", "10-6-2", "10-6-3", "10-6-4"]
source_section_digest: 8728240A94A3F7F6BCDC2175BFD01D028BE2FB9EC0563040BDA4E201C6174777
always_load: false
may_relax_parent: false
---

# 5단계: 보안과 예외 엣지 케이스

악의적 입력과 극단 상황에서 방어가 유지되는지 검사한다.

- SQL Injection, XSS, CSRF 방어와 파라미터 검증이 있는가.
- Null, Undefined, 빈 문자열, 배열 등 비정상 타입에서 안전하게 실패하는가.
- 민감 데이터와 통신이 평문으로 노출되는가.
- Alert와 500 응답에 스택 트레이스나 내부 구조가 노출되는가.
- 인증 후 권한 검사가 누락되거나 세션을 우회할 수 있는가.
- 크기 제한, 중복 요청, 변조 파일 같은 추가 공격면이 있는가.


