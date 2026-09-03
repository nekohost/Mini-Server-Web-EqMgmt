# Rule 거버넌스 노드 운영 승격 계획

## 승인 근거

사용자는 2026-09-03에 `Staging/Rule.md`와 `.agent-governance/` 노드 구성을 운영 루트에 반영하도록 명시적으로 승인했다.

## 적용 범위

1. `Staging/Rule.md`를 사용자용 운영 `Rule.md`로 승격한다.
2. Staging의 AI 실행 노드·라우터·추적성·검증 도구를 루트 `.agent-governance/`로 승격한다.
3. Codex·Gemini·Claude 운영 진입점을 루트 `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`로 활성화한다.
4. 기존 `Rule.md`, `VALIDATION_METHODOLOGY.md`, GEMINI 0조가 이미 삭제된 `GEMINI.md`를 `.agent-governance/legacy-sources/`에 원문 보존하여 기존 RULE·VAL·ENTRY 추적 근거를 유지한다.
5. 운영 경로와 상태, Rule SHA-256, 섹션 기준선, 40개 node digest를 `1.0.0` 기준으로 재산출한다.
6. 정규 검증·회귀 테스트·동기화 상태·경로 잔존 검사를 통과한 뒤에만 Staging 거버넌스 산출물을 정리한다.

## 비범위

- `VALIDATION_METHODOLOGY.md` 원본 수정 또는 삭제
- 애플리케이션 코드, 운영 DB, 서버 실행 및 배포
- 제안-013 이후로 보류된 실제 DB 구조 확정
- 사용자 직접 변경인 GEMINI 0조 삭제의 복구

## 롤백

운영 진입점 또는 노드에 문제가 있으면 `.agent-governance/legacy-sources/`의 세 원본과 Git 이력을 이용해 Rule·진입점·manifest를 같은 버전 단위로 되돌린다. Chat·Plans·Report 이력은 롤백 대상에서 제외한다.

## 완료 조건

- 루트 거버넌스 `1.0.0`이 `active` 상태다.
- `sync-status`가 추가·변경·삭제 0건을 보고한다.
- `validate --expected-rule-sha` 오류·경고가 0건이다.
- 회귀 테스트 12개가 통과한다.
- 루트 `VALIDATION_METHODOLOGY.md` 해시가 유지된다.
- 운영 애플리케이션·DB 파일은 변경되지 않는다.

## 완료 결론

2026-09-03 운영 승격을 완료했다. `.agent-governance/manifest.yaml`은 `1.0.0`·`active`이고, Rule 기준선과 40개 노드의 digest를 운영 Rule SHA-256에 맞추었다. 회귀 테스트 12개, 정규 YAML 및 양방향 추적성 검증, 동기화 상태 검사와 npm 취약점 검사를 모두 통과했다. 루트 `VALIDATION_METHODOLOGY.md`의 SHA-256은 승격 전과 동일하며 애플리케이션 코드·DB·서버에는 변경을 가하지 않았다. 상세 근거는 `Report/2026-09-03_Rule_Governance_Production_Promotion_Report.md`에 기록했다.
