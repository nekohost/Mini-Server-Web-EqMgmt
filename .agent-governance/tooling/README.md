# Governance Tooling

대화 자동 기록기는 프로젝트 루트에서 다음 명령으로 사용한다.

```text
node .agent-governance/tooling/conversation-recorder.mjs ensure --platform all --workspace . --json
node .agent-governance/tooling/conversation-recorder.mjs status --workspace . --json
node .agent-governance/tooling/conversation-recorder.mjs verify --platform all --workspace . --json
```

`npm test`는 기존 governance 도구 시험과 대화 기록기 fixture 시험을 함께 실행한다.

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
- `--reference-path <path>`: 읽기 전용 참고·영향 경로를 반복 선언한다. 실제 작업 대상 `--path`와 구분하며 수정 권한을 부여하지 않는다.
- `node .agent-governance/tooling/governance-tool.mjs sync-status`: 승인된 섹션 기준선과 현재 Rule을 비교해 추가·변경·삭제 섹션, 영향 노드, 현재 Rule hash를 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs sync-plan --expected-rule-sha <sha256> --section <번호>`: 실제 변경 섹션을 대상으로 노드·기준선·map·digest 갱신 계획을 출력한다.
- `node .agent-governance/tooling/governance-tool.mjs snapshot`: 기준선 작성 또는 검증에 쓸 섹션 hash와 노드별 기대 digest를 출력한다.

`--intent`, `--path`, `--section`은 반복할 수 있다. 작은 모델은 `--small-model`을 사용해 안전 노드를 유지한 여러 pack으로 나눌 수 있다. 미분류 입력, 단일 pack으로도 수용할 수 없는 노드, stale Rule hash는 fail-closed 한다.

Rule 변경 순서는 `sync-status` → 모든 변경 섹션을 지정한 `sync-plan --expected-rule-sha` → 사람이 검토한 노드·map·기준선·digest 반영 → 같은 hash로 `validate --expected-rule-sha`이다. 도구는 정책 파일을 자동 수정하지 않으며, AI는 diff와 복구 가능성이 보이는 구조화 편집 도구를 사용한다.

## Context 1.6.0: 작업 의미·경로 역할·진단

1. catalog로 knownIntents와 knownPathPatterns를 확인한다. 기존 error 문자열뿐 아니라 diagnostics[].code를 읽는다.
2. DB migration/컬럼 변경과 UI intent는 경로와 독립적으로 필수 보호 노드를 선택한다. catalog의 pathHints는 예시이며 paths의 필수 조건과 다르다.
3. 경로는 정규화 후 별도로 검증한다. 일반 implement/question이 unknown path를 자동 허용하지 않는다. 알려진 디렉터리 아래 새 파일은 허용하지만 새로운 최상위 경로는 등록 검토가 필요하다. 경로 분류 성공은 DB·비밀·Git 파일에 대한 접근/수정 승인을 의미하지 않는다.
4. Staging 접두사는 제거하거나 원본으로 자동 변환하지 않는다. 원본을 참고한다면 --reference-path로 선언한다. 동일 경로를 대상과 참고 양쪽에 선언하지 않는다.
5. 존재하는 symlink/junction 조상이 프로젝트 밖을 가리키는 경우도 외부 scope intent가 필요하다. 외부 scope 분류는 대상 workspace의 변경 승인을 대신하지 않는다.
6. context 자체도 전체 거버넌스 정합성을 확인한다. 실패 시 nodes/packs를 반환하지 않는다. 상세 계약 노드는 모든 context에 포함하며 작은 pack에서도 누락하지 않는다.

프로젝트 루트에서 실행하는 예시(규칙 조회일 뿐 실제 파일 수정 없음):

```powershell
node .agent-governance/tooling/governance-tool.mjs context --intent implement --intent plan --intent migration --intent ui --path Staging/Official_Model_Name_20260912/app.py --path Staging/Official_Model_Name_20260912/templates/lineup_management.html --reference-path app.py --reference-path utils/database_contract.py --reference-path templates/lineup_management.html
```

참고할 원본이 없는 신규 후보라면 --reference-path를 생략한다. Staging-only migration도 같은 DB 보호 규칙을 선택한다. 분류 조건을 맞추기 위해 무관한 app.py를 추가하지 않는다.

| 진단 코드 | 의미와 확인 방법 |
|---|---|
| UNKNOWN_INTENT | 등록되지 않은 종류. catalog의 knownIntents를 확인하며 자동 등록/의미 축소는 하지 않는다. |
| INTENT_PATH_MISMATCH | 등록된 종류지만 경로 한정 route가 불일치. 진단의 routes/expectedPaths를 확인한다. |
| UNMATCHED_PATH / INVALID_PATH | 등록 경로 밖 또는 빈값·제어문자·glob 입력. 역할별 실제 경로를 확인한다. |
| EXTERNAL_SCOPE_REQUIRED | 정규화/실제 조상이 외부 경계에 해당. 사용자 의도에 맞는 scope를 확인한다. |
| MISSING_TARGET_PATH / PATH_ROLE_CONFLICT | 수정 작업에 참고만 있거나 같은 경로의 역할이 겹친다. 승인된 실제 대상을 확인한다. |
| MISSING_SECTION / UNKNOWN_SECTION | Rule 섹션 입력이 없거나 추적성에 없다. 대상 섹션 및 sync-status를 확인한다. |
| POLICY_VALIDATION_FAILED | 해시·노드·map 등 정책 불일치. 정상 context로 일반 작업을 재개할 수 없다. |
| CONTEXT_BUDGET_EXCEEDED | 모든 규칙을 보존한 작은 작업으로 분할한다. 예산 확대/규칙 삭제로 통과시키지 않는다. |
| MISSING_OPTION_VALUE / UNKNOWN_OPTION | CLI 옵션 구문 오류. help로 지원 문법을 확인한다. |

실패 후 일반 구현은 중단한다. 기존 승인 범위에서 읽기 전용 catalog/validate/입력 대조와 근거 있는 입력 정정은 가능하다. 정정 근거를 기록하고 validate 및 새 context 성공, 전체 pack 읽기 후 같은 승인 범위에서 재개한다. 실제 미등록 작업·권한 부족·규칙 충돌·정책 변경 필요는 별도 절차로 처리하며 무한 재시도하지 않는다.
