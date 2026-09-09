# Rule 거버넌스 노드 운영 승격 검증 보고서

## 결론

`Staging/Rule.md` 기반 노드화 구성을 프로젝트 운영 루트에 승격했다. 운영 거버넌스 버전은 `1.0.0`, 상태는 `active`이며 사용자용 통합 규정과 40개 실행 노드가 동일한 Rule 기준선에 동기화되어 있다.

## 운영 산출물

- 사용자 참조본: `Rule.md`
- AI 실행 노드: `.agent-governance/`
- 제품별 진입점: `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`
- 노드화 전 내용 스냅샷: `.agent-governance/legacy-sources/`
- 유지 원본: `VALIDATION_METHODOLOGY.md`

`GEMINI.md`의 삭제된 0번 조항은 복구하지 않았으며, 해당 상태의 내용 스냅샷을 출처 추적용으로 보존했다.

## 무결성 기준

- 운영 Rule SHA-256: `BC06FFB287AB46D56152CDD3FCCC2016F3B2B17D4BDF01B7C6E31ED0C7E664C8`
- 유지된 Validation SHA-256: `1D397B47F7CD330333DAD6C97647D923807F93F92DC023D921DA57E1122E29DF`
- legacy Rule 내용 스냅샷: `4424AFB35E27CE39DB600B2A0E27BD73053F155A4A936DBD371E495B97E75710`
- legacy Validation 내용 스냅샷: `F8F114A0A75A416C6A99BF958C1F55C51FFAE68E70F8A022C19EE39BF6C385A9`
- legacy Gemini 내용 스냅샷: `AF879CD2D1CE46E30B7E0391CF1416294207338BE1913BB3A85B6B5C94DD6085`

legacy 스냅샷은 보존 과정에서 LF로 정규화된 내용 보존본이므로 승격 전 CRLF 파일의 바이트 해시와는 다르다. manifest와 추적성 원장은 실제 보존 파일의 해시를 사용한다.

## Validation Methodology 1~8 결과

1. 거버넌스: manifest·router·10개 YAML·40개 front matter·양방향 원장·원본 해시가 일치했다.
2. 사용자 의도: 승인 범위인 Rule 노드 운영 승격만 적용했고 DB 구조 확정, 앱 기능 변경, 서버 배포는 제외했다.
3. 정적·논리: 도구 회귀 테스트 12개가 모두 통과했다.
4. 운영 영향: 루트 진입점과 상대 경로를 운영형으로 전환하고 `staging-only` 잔존을 제거했다. 앱 코드와 DB는 수정하지 않았다.
5. 보안·극단값: 고정 의존성 `yaml@2.9.0` 설치 상태를 검증했고 `npm audit --omit=dev` 결과 취약점은 0건이었다.
6. 롤백: 노드화 전 세 문서의 내용 스냅샷, 영구 Plan, 검증 보고서와 Git diff를 복구 근거로 유지한다.
7. 휴먼 에러: 미등록 intent·path·section, stale Rule hash, 중복 YAML 키를 fail-closed 하는 회귀 테스트가 통과했다.
8. AI 메타: Codex·Gemini·Claude 진입점이 같은 sync 절차를 안내하며, 작은 모델용 분할 context pack 테스트가 통과했다.

## 실행 결과

- `npm.cmd test`: 12/12 통과
- `validate --expected-rule-sha BC06...664C8`: errors 0, warnings 0
- `sync-status`: added 0, changed 0, removed 0, `inSync: true`
- YAML 파서: configured/locked/installed 모두 `2.9.0`
- Node 런타임: `22.23.2`, 지원 조건 충족
- `npm audit --omit=dev`: 취약점 0

## 정리

스테이징 검증 보고서 5종은 `Report/2026-09-03_Staging_*`로 아카이빙한 뒤, 중복된 Staging 진입점·Rule·노드·Task·설치 의존성을 정리한다. 운영 산출물은 루트와 `.agent-governance/`에 유지된다.
