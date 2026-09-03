# Governance Tooling

이 디렉터리는 활성 운영 거버넌스를 위한 읽기 전용 검사·라우팅 도구다. Flask 애플리케이션 및 Linux 미니서버 런타임과 분리된다. 아래 명령은 프로젝트 루트를 작업 디렉터리로 한다.

## 설치

```powershell
cd .agent-governance/tooling
npm.cmd ci --ignore-scripts --no-audit --no-fund
```

`package-lock.json`에 고정된 `yaml@2.9.0`만 설치하며 lifecycle script는 실행하지 않는다.

## 명령

- `node .agent-governance/tooling/governance-tool.mjs validate [--expected-rule-sha <sha256>]`: YAML, Markdown front matter, Rule·node·human map·manifest, 섹션 기준선과 node digest를 검증한다.
- `node .agent-governance/tooling/governance-tool.mjs catalog`: 지원 intent·path와 전체 route를 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs context --intent <id> --path <path>`: 모든 일치 route를 합쳐 manifest 순서의 context pack을 JSON으로 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs sync-status`: 승인된 섹션 기준선과 현재 Rule을 비교해 추가·변경·삭제 섹션, 영향 노드, 현재 Rule hash를 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <sha256> --section <번호>`: 실제 변경 섹션을 대상으로 노드·기준선·map·digest 갱신 계획을 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs snapshot`: 기준선 작성 또는 검증에 쓸 섹션 hash와 노드별 기대 digest를 출력한다.

`--intent`, `--path`, `--section`은 반복할 수 있다. 작은 모델은 `--small-model`을 사용해 안전 노드를 유지한 여러 pack으로 나눌 수 있다. 미분류 입력, 단일 pack으로도 수용할 수 없는 노드, stale Rule hash는 fail-closed 한다.

Rule 변경 순서는 `sync-status` → 모든 변경 섹션을 지정한 `sync-plan --expected-rule-sha` → 사람이 검토한 노드·map·기준선·digest 반영 → 같은 hash로 `validate --expected-rule-sha`이다. 도구는 정책 파일을 자동 수정하지 않으며, AI는 diff와 복구 가능성이 보이는 구조화 편집 도구를 사용한다.
