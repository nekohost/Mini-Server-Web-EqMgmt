# Terra·Gemini 검증 보완 종합 보고서

- 검증일: 2026-09-02 (Asia/Seoul)
- 대상: `Staging/Rule.md`, 제품별 진입점, `Staging/.agent-governance/` 전체
- 거버넌스 버전: `0.4.0-staging`
- 결론: **Staging 구현 및 정적·동적 검증 통과**
- 범위 제한: 운영 루트와 실제 DB에는 적용하거나 접근하지 않았다.

## 1. 반영한 검증 결과

### Terra 지적 사항

1. `[제안-013]` 이전 운영 DB 스키마 확정 보류를 `engineering.data-model` 실행 노드에 투영했다.
2. Rule 변경 섹션에서 대상 노드·human map·manifest를 결정적으로 산출하는 `governance.rule-sync`와 `sync-plan`을 추가했다.
3. Rule 동기화 불변식에 manifest의 Rule SHA-256, 거버넌스 버전, 신규 노드 등록을 포함했다.
4. Codex의 Undo capability를 미검증 상태로 교정하고, 런타임 실측 전에는 보장하지 않도록 했다.
5. 선언형 router를 실제 읽기 전용 `context` 로더로 연결했다.
6. 정규 YAML 파서로 모든 YAML과 Markdown front matter를 실제 파싱했다.

### Gemini 부정적 피드백 1~3

1. 복합 요청은 전달된 모든 intent와 path의 route를 합집합으로 결합한다. 미등록·미매칭 입력은 fail-closed 한다.
2. `yaml@2.9.0`을 Staging 거버넌스 도구 전용 의존성으로 격리하고 `package-lock.json`으로 고정했다.
3. Rule 개정 시 `sync-plan`이 수정 대상과 필수 절차를 산출하며, `validate`가 Rule↔node↔human map↔manifest 정합성을 재검증한다.

## 2. 구현 결과

- 사용자용 `Staging/Rule.md`에 `HUMAN-3.1.1-DB-DEFERRAL`과 `HUMAN-11.7`을 추가했다.
- `engineering.data-model`에 `[제안-013]` 구현·원본 백업의 로컬 확보 전 DB 접근 및 운영 스키마 확정 금지를 명시했다.
- `governance.rule-sync`를 추가하고 manifest·human map에 등록했다.
- `router.yaml`에 Rule 동적 노드 선택, 전체 intent/path 결합, 미분류 차단, 실행 로더 경로를 선언했다.
- `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`가 실제 검증기와 context pack을 공통 부트스트랩으로 사용하도록 했다.
- `capabilities/codex.yaml`의 Undo 호환성을 `unverified`로 내렸다.
- 백업 서버 `192.168.0.24`와 그 운영 병합 보존 규칙은 유지했다.
- 과거 검증 보고서는 당시 버전의 역사 기록임을 명시하여 현재 40노드 결과와 혼동되지 않게 했다.

## 3. Validation Methodology 1~8

### 1단계 — 규칙·전제 검증

- 사용자용 Rule과 AI용 노드의 역할을 분리했다.
- Rule SHA-256 `4ADCB1A295EB207FE95C44F8373271EAD3CFBDCDF41231E49148301B64A9D5C4`가 manifest 값과 일치한다.
- 백업 IP와 DB 보류 정책이 Rule과 실행 노드에 함께 존재한다.
- 결과: 통과.

### 2단계 — 사용자 의도 검증

- 사용자가 Rule을 직접 수정하고 AI가 포인터 대상 노드를 동기화한다는 의도를 `HUMAN-11.7`과 `governance.rule-sync`에 고정했다.
- 운영 반영, 실제 DB 열람, `[제안-013]` 구현은 이번 범위에서 제외했다.
- 결과: 통과.

### 3단계 — 정적·논리 검증

- 정규 파서로 YAML 9개와 노드 front matter 40개를 파싱했다.
- manifest 40노드와 human map 40노드가 양방향으로 일치한다.
- 중복 YAML 키 거부 회귀 테스트를 포함해 총 8개 테스트가 통과했다.
- `node --check`로 도구와 테스트 파일의 JavaScript 구문을 확인했다.
- 결과: 오류 0건, 경고 0건.

### 4단계 — 운영 영향 검증

- npm 의존성은 `Staging/.agent-governance/tooling`에만 존재하며 Flask 앱 및 미니서버 런타임에 추가하지 않았다.
- 운영 루트 파일과 DB는 수정하지 않았다.
- Staging 병합 노드에 Rule·노드·map·manifest의 동일 변경 단위 검증을 추가했다.
- 결과: 통과. 실제 운영 병합은 별도 승인·검증 대상이다.

### 5단계 — 보안·경계조건 검증

- 미등록 intent/path는 종료 코드 1로 차단됐다.
- Rule 유지보수 route에서 `--section` 누락 시 종료 코드 1로 차단됐다.
- YAML 파서 또는 잠금 의존성이 없거나 파싱이 실패하면 context를 생성하지 않는다.
- `npm audit --omit=dev --audit-level=low` 결과 취약점 0건이다.
- 결과: 통과.

### 6단계 — 롤백·복구 검증

- 도구는 읽기 전용이며 정책 파일을 자동 수정하지 않는다.
- `sync-plan`은 대상만 산출하고 실제 변경은 Diff가 보이는 구조화 편집 도구로 수행한다.
- `node_modules/`는 tooling `.gitignore`로 제외하며 재현은 잠금 파일 기반 `npm ci`로 한다.
- 결과: 통과.

### 7단계 — 인간 오류 검증

- Rule 3-1-1과 11-3 복합 변경 입력에서 `governance.human-reference`, `governance.rule-sync`, `engineering.data-model` 및 필수 map·manifest가 산출됐다.
- DB+프론트엔드 복합 요청은 `schema-change`와 `frontend-change`를 모두 매칭했다.
- `catalog` 명령이 사용 가능한 intent·path·route 전체를 출력한다.
- 결과: 통과.

### 8단계 — AI 메타 검증

- 작은 모델 예산은 4,000으로 설정했다.
- 한글 과소평가를 줄이기 위해 `utf8-bytes-div-3-ceil` 추정기를 사용한다.
- Rule 변경 시나리오는 3개 pack(3,910 / 3,854 / 3,396), DB+프론트 시나리오는 2개 pack(3,950 / 2,469)으로 분할됐고 모두 예산 이하다.
- 이 추정치는 모델 비종속 계획치이며 실제 토크나이저의 정확한 토큰 수를 보장하지 않는다.
- 결과: 통과. 실제 대상 모델의 한도가 더 작으면 작업 단위를 추가로 나눠야 한다.

## 4. 실행 증거

```text
npm.cmd test
status: pass, tests: 8

node .agent-governance/tooling/governance-tool.mjs validate
YAML files: 9
manifest nodes: 40
human map nodes: 40
errors: 0
warnings: 0

npm.cmd ls --depth=0
yaml@2.9.0

npm.cmd audit --omit=dev --audit-level=low
found 0 vulnerabilities
```

## 5. 잔여 위험과 운영 병합 조건

1. 자연어 요청에서 intent와 path를 뽑는 첫 분류는 여전히 AI 또는 호스트 통합 계층의 책임이다. 도구는 전달된 모든 입력을 결정적으로 처리하고 미등록 입력을 차단하지만, AI가 처음부터 어떤 의도도 전달하지 않는 행위를 수학적으로 방지하지는 못한다. 제품별 진입점과 `catalog` 절차로 이 위험을 낮췄다.
2. context token 수는 모델 비종속 보수 추정치다. 실제 소형 모델 투입 전 해당 모델 토크나이저 또는 더 낮은 예산으로 재검증한다.
3. 운영 병합 시 루트의 Rule·제품별 진입점·`.agent-governance`를 하나의 변경 단위로 적용해야 한다. 부분 병합은 허용하지 않는다.
4. `[제안-013]` 구현과 원본 DB 백업의 로컬 확보 전에는 실제 운영 DB를 열거나 3-1-1의 현재 스키마를 확정하지 않는다.

## 6. 최종 판정

Terra의 6개 지적과 Gemini의 부정적 피드백 1~3은 Staging에서 구현·검증되었다. 현재 결과는 운영 병합 후보로 사용할 수 있으나, 운영 병합 자체는 본 보고서의 범위가 아니며 위 잔여 조건을 지켜 별도 수행해야 한다.
