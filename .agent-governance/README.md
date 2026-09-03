# AI Governance Nodes

이 디렉터리는 프로젝트의 활성 AI 실행 규칙을 작은 책임 단위로 분리한 운영 거버넌스 트리다. 사용자용 통합 규정은 루트 `Rule.md`이며, AI는 평상시 그 전문을 자동 로드하지 않고 이 트리의 진입점·라우터·노드를 사용한다.

현재 상태는 `active`이고 거버넌스 버전은 `1.0.0`이다. 노드화 전 세 원본의 내용 스냅샷은 `legacy-sources/`에 보존한다. 루트 `VALIDATION_METHODOLOGY.md`는 원문을 유지하며, 제품별 진입점은 `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`이다.

## 로딩 순서

1. `tooling/governance-tool.mjs validate`로 YAML, front matter, Rule 해시, 양방향 추적성을 검사한다.
2. 사용자 요청에 관련된 모든 intent와 대상 path를 식별한다.
3. `tooling/governance-tool.mjs context`에 모든 intent와 path를 전달한다. Rule 개정이면 변경 section도 전달한다.
4. 반환된 context pack의 노드를 표시된 순서대로 읽는다.
5. 승인된 Plan과 Task가 있으면 그 순서를 따른다.

## 도구 설치와 명령

도구 의존성은 Flask 애플리케이션과 분리되어 `tooling/`에만 설치한다.

```powershell
cd .agent-governance/tooling
npm.cmd ci --ignore-scripts --no-audit --no-fund
node governance-tool.mjs validate
node governance-tool.mjs catalog
```

프로젝트 루트에서는 다음처럼 호출할 수 있다.

```powershell
node .agent-governance/tooling/governance-tool.mjs context --intent add-column --intent frontend --path app.py --path templates/index.html --small-model
```

Rule 변경 전에는 현재 해시와 실제 변경 섹션을 고정한다.

```powershell
node .agent-governance/tooling/governance-tool.mjs sync-status
node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <currentRuleHash> --section 3-1-1 --section 11-3
node .agent-governance/tooling/governance-tool.mjs context --intent edit-rule --path Rule.md --section 3-1-1 --section 11-3 --small-model
```

미등록 intent·path·section, YAML 오류, 해시·서명·양방향 추적 불일치는 종료 코드 1로 차단한다. 제안·계획·검증 자체에는 `validation/kernel.md`, `validation/orchestration.md`, `validation/phases/01~08`을 순서대로 적용한다.

## 추적성 자료

- `traceability/rule-map.yaml`
- `traceability/validation-map.yaml`
- `traceability/entrypoint-map.yaml`
- `traceability/human-rule-map.yaml`
- `traceability/rule-section-baseline.yaml`
- `traceability/exceptions.md`

사용자가 루트 `Rule.md`를 수정하면 `governance/rule-sync.md`의 절차에 따라 영향 노드, 양방향 원장, 섹션 기준선, manifest를 같은 변경 단위로 갱신하고 검증한다.
