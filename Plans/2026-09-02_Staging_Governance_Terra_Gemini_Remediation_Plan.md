# Staging 거버넌스 Terra·Gemini 검증 보완 계획

## 1. 목적

Terra 독립 감사 결과와 Chat에 기록된 Gemini 부정적 피드백 1~3을 결합하여, 사용자용 `Staging/Rule.md` 변경이 AI 실행 노드·추적성·manifest에 빠짐없이 투영되고 작은 모델도 결정적인 경로를 따라갈 수 있도록 Staging 거버넌스를 보완한다.

## 2. 검증 결과 통합

### Terra

1. `[제안-013]` 완료 전 운영 DB 스키마 확정 보류가 실행 노드에 없음
2. Rule 개정 route가 변경 포인터 대상 노드와 추적성·manifest를 결정적으로 선택하지 못함
3. manifest 해시·버전·신규 노드 등록이 동기화 불변식에 명시되지 않음
4. Codex capability가 실측되지 않은 Undo 호환성을 사실처럼 선언함
5. router와 fail-closed가 선언에 머물고 실행 로더가 없음
6. YAML 정규 파서 검증이 없음

### Gemini 부정적 피드백 1~3

1. 복합 요청에서 AI가 intent·path route를 누락할 위험
2. YAML 런타임 파서 부재
3. Rule·노드·manifest·human map·router 동시 갱신의 유지보수 부담

## 3. 구현 범위

1. `Staging/Rule.md` 3-1-1에 `[제안-013]` 기반 DB 확인 보류를 사용자용 정책으로 명시한다.
2. `engineering.data-model`과 human map에 같은 의미를 투영한다.
3. Rule 유지보수 전용 `governance.rule-sync` 노드를 추가한다.
4. Rule 11장에 변경 섹션 식별부터 대상 노드·역포인터·manifest 해시·버전 갱신 및 재검증까지의 고정 절차를 추가한다.
5. router에 Rule 유지보수 필수 입력, 다중 intent·path 결합, 미분류 요청 fail-closed 조건을 명시한다.
6. 정규 YAML 파서가 manifest·router·traceability·capability와 Markdown front matter를 실제 파싱하는 Node 기반 읽기 전용 도구를 추가한다.
7. 도구는 다음 명령을 제공한다.
   - `validate`: YAML 구문, 스키마·경로·ID·해시·양방향 추적성 검사
   - `context`: 여러 intent·path·Rule section을 결합하여 로딩할 노드를 manifest 순서로 결정적으로 출력
   - `sync-plan`: 변경 Rule section에서 수정해야 할 대상 노드·map·manifest·검증 절차를 출력
8. Codex capability는 Undo를 실측 전 보장하지 않도록 낮춘다.
9. 과거 검증 보고서는 역사 기록임을 명확히 하고 새 종합 검증 보고서를 작성한다.

## 4. 도구 및 의존성 결정

- 실행 환경: 현재 개발 PC의 Node.js
- YAML 파서: npm `yaml` 패키지를 Staging 거버넌스 도구 전용 의존성으로 격리
- 잠금: `package-lock.json`으로 실제 버전과 무결성 고정
- 애플리케이션 영향: Flask 운영 애플리케이션과 Linux 미니서버 런타임에는 의존성을 추가하지 않음
- 무의존 대안: PowerShell 정규식 검사 또는 JSON 전환이 가능하지만, 전자는 정규 YAML 파싱을 보장하지 못하고 후자는 현재 설계의 전면 형식 변경과 이중 유지보수를 초래하므로 이번 구현에서는 채택하지 않음

## 5. 안전 조건

- 도구의 기본 동작은 읽기 전용이며 정책 문서를 자동 수정하지 않는다.
- `sync-plan`은 수정 대상을 산출할 뿐 의미를 자동 생성하거나 파일을 덮어쓰지 않는다.
- 실제 정책 편집은 플랫폼별 구조화 편집 도구로 수행한다.
- 미분류 intent, 존재하지 않는 경로·노드, Rule 해시 불일치, YAML 파싱 실패는 종료 코드 실패로 차단한다.
- `[제안-013]` 완료 및 원본 DB 백업의 로컬 확보 전에는 실제 운영 스키마를 확정하거나 DB를 열람하지 않는다.

## 6. 동기화 대상

- `Staging/Rule.md`
- `Staging/.agent-governance/manifest.yaml`
- `Staging/.agent-governance/router.yaml`
- `Staging/.agent-governance/governance/*`
- `Staging/.agent-governance/engineering/data-model.md`
- `Staging/.agent-governance/traceability/human-rule-map.yaml`
- `Staging/.agent-governance/capabilities/codex.yaml`
- 제품별 Staging 진입점과 README
- Staging 거버넌스 도구·잠금 파일·검증 보고서

## 7. 완료 조건

1. Rule 수정 섹션에서 대상 노드가 결정적으로 산출된다.
2. 복합 intent·path는 모든 매칭 route를 합집합으로 로드한다.
3. 누락·모호성·해시 불일치는 fail-closed 된다.
4. 모든 YAML과 front matter가 정규 YAML 파서에서 통과한다.
5. Rule↔node↔human map↔manifest 검사가 오류 0건이다.
6. Validation 1~8단계 보고서가 작성된다.
7. 운영 루트와 실제 DB는 변경하지 않는다.

