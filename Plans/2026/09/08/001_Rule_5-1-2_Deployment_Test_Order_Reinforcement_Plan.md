# [규칙 보강계획 보고서] Rule 5-1-2 개발·검증·배포 순서 명확화

작성일: 2026-09-08
상태: 계획 및 사전 검증 완료, 규칙 변경 미수행
대상 조항: `Rule.md` 5-1-2
대상 실행 노드: `.agent-governance/operations/server-execution.md`
기준 Rule SHA-256: `0366391F84CF1F9C6AA30DB4E8E60927A05903A159E13AB815A2C586445AD7EB`

## 1. 문제와 보강 목표

현행 5-1-2의 “모든 실제 테스트와 구동은 Linux에서 수행한다”는 문장은 실행 장소는 분명히 정하지만 전체 작업 순서와 단계 사이의 관계는 정하지 않는다. 이 때문에 Linux 실행 검증을 로컬 운영 소스 병합과 Git push의 선행조건으로 잘못 해석할 수 있다.

보강 목표는 다음 두 사실을 한 조항에서 동시에 고정하는 것이다.

1. Windows의 Staging과 운영 소스 루트에서는 애플리케이션을 구동하지 않고 정적 검증만 한다.
2. 실제 구동 검증은 승인된 운영 소스를 Git으로 Linux에 전달한 뒤 수행한다.

## 2. 용어 정의

5-1-2에 다음 용어를 명시한다.

- **운영 소스 반영**: 검증·승인된 Staging 변경을 Windows 프로젝트 루트의 `app.py`, `templates/` 등 Git 관리 대상에 병합하는 작업이다. 실행 중인 Linux 서비스에 적용하는 행위가 아니다.
- **Git 원격 반영**: 운영 소스 반영분을 commit하고 원격 저장소에 push하는 작업이다.
- **Linux 배포**: 미니서버 또는 사용자가 검증 대상으로 지정한 백업 Linux 서버에서 승인된 commit을 pull하는 작업이다.
- **서비스 적용 및 실행 검증**: Linux pull 뒤 안전하게 프로세스를 시작·재시작하고 실제 동작을 확인하는 작업이다.

이 구분으로 “운영 반영”이라는 한 표현이 로컬 소스 병합과 실행 중 서비스 변경을 동시에 뜻하지 않게 한다.

## 3. 5-1-2에 추가할 표준 순서

다음 순서를 5-1-2의 필수 순서로 추가한다.

1. Windows의 `Staging/`에 구현 후보를 작성한다.
2. Staging 소스를 구동하지 않고 정적 검사와 Validation 1~8을 수행한다.
3. 검사 결과와 미해결 위험을 사용자에게 보고하고 운영 소스 병합 승인을 받는다.
4. 승인된 변경만 Windows 프로젝트 루트의 운영 소스에 병합한다.
5. 운영 소스와 승인된 Staging 결과의 동일성 및 정적 검사를 다시 확인한다.
6. 계획서 등 영구 보존 예외를 이관한 뒤 Staging 임시 파일을 정리한다.
7. 운영 소스, 계획, Task, 보고서를 같은 변경 범위로 commit하고 Git 원격에 push한다.
8. 미니서버 또는 사용자가 지정한 백업 Linux 서버에서 정확한 commit을 pull하고 일치 여부를 확인한다.
9. Linux의 격리된 모의 데이터 또는 승인된 시험 조건에서 구문·의존성·기능 검증을 수행한다.
10. 검증 결과에 따라 서비스를 시작·재시작하고 브라우저/API 동작을 확인한다.

Linux 실행 검증은 8단계의 pull 이후에 수행하는 후속 검증이다. Linux 실행 검증이 아직 수행되지 않았다는 이유만으로 3단계에서 승인된 로컬 운영 소스 병합이나 7단계의 Git 전달을 선행 차단하지 않는다.

## 4. 실패 시 복귀 지점

- 2단계 정적 검증 실패: Staging 구현 단계로 돌아가 수정한다. 운영 소스에는 병합하지 않는다.
- 5단계 운영 소스 정적 재검증 실패: 운영 병합을 중단하고 승인된 Staging 결과와의 차이를 교정한다.
- 8~10단계 Linux 검증 실패: 서버에서 즉석 수정하지 않는다. Windows Staging으로 돌아가 수정·정적 검증·승인·운영 소스 병합·push·pull 순서를 다시 수행한다.
- 실행 중인 서비스에 치명적 문제가 확인되면 직전 정상 commit과 기존 DB 백업을 기준으로 복구하고, 원인 수정은 Windows 개발 흐름에서 다시 시작한다.

## 5. 제안 문안

`Rule.md` 5-1-2의 기존 첫 문장은 유지하고 그 아래에 다음 의미의 문단과 순서표를 추가한다.

> 실제 테스트를 Linux에서 수행한다는 규칙은 테스트 환경을 정하는 규칙이다. 검증된 Staging 산출물은 사용자 승인 후 Windows 운영 소스에 먼저 병합하고 Staging을 정리한 다음 commit·push한다. Linux에서는 그 commit을 pull한 뒤 실제 테스트와 서비스 구동을 수행한다. 따라서 Linux 실행 검증은 로컬 운영 소스 병합이나 Git push의 선행조건으로 해석하지 않는다.

최종 Rule에는 위 문단만 두지 않고 제3절의 10단계 번호 목록을 함께 실어 순서 생략과 재배열을 막는다.

## 6. 동기화 대상

규칙 구현 승인을 받은 경우 다음 파일을 하나의 변경 단위로 갱신한다.

| 파일 | 변경 내용 |
| --- | --- |
| `Staging/Rule.md` 또는 충돌 없는 전용 Rule 후보 영역 | 5-1-2 보강안을 먼저 작성하고 검토 |
| `Rule.md` | 승인된 5-1-2 용어와 10단계 순서 반영 |
| `.agent-governance/operations/server-execution.md` | 같은 용어·순서·실패 복귀 의미를 실행 지침으로 투영하고 노드 버전 갱신 |
| `.agent-governance/traceability/human-rule-map.yaml` | `HUMAN-5.1.2-ORDER`를 5-1-2와 실행 노드에 양방향 연결 |
| `.agent-governance/traceability/rule-section-baseline.yaml` | 5-1-2 섹션 hash와 전체 Rule hash 갱신 |
| `.agent-governance/manifest.yaml` | Rule SHA-256과 `governance_version` 갱신 |

새 노드나 새 라우팅 유형은 필요하지 않으므로 manifest의 `nodes`와 `router.yaml`은 변경하지 않는다. `operations.local-execution`, `operations.staging`, `workflow.staging-merge`는 이미 이 순서를 지지하므로 의미 변경 대상에서 제외하고 회귀 검증 대상으로만 사용한다.

## 7. 구현 시 거버넌스 절차

1. 현재 다른 작업의 Staging 산출물이 존재하면 먼저 소유 작업을 확인하고 섞지 않는다.
2. 구현 직전에 `sync-status`를 다시 실행한다.
3. 현재 hash가 본 계획의 기준 hash와 다르면 변경된 모든 섹션을 재분석하고 계획을 갱신한다.
4. 동일하면 `sync-plan --expected-rule-sha 036639...AD7EB --section 5-1-2`로 대상 파일을 다시 확정한다.
5. Staging 후보 작성과 검토 후 사용자 승인을 받아 Rule·노드·map·baseline·manifest를 같은 버전 묶음으로 반영한다.
6. 변경된 Rule의 새 SHA와 섹션 hash, 노드 `source_section_digest`를 계산해 반영한다.
7. 계획 때 기록한 기준 hash를 사용해 `validate --expected-rule-sha 036639...AD7EB`를 실행한다.
8. `sync-status`가 변경 0건과 `inSync: true`를 보고하는지 확인한다.
9. diff와 Validation 1~8 보고서를 제출한 뒤 별도의 운영 병합 승인을 적용한다.
10. 병합 완료 후 해당 Rule Staging 임시 파일만 정리한다.

## 8. 수용 기준

- AI가 문장만 읽고도 Staging 정적 검증 → 운영 소스 병합 → Staging 정리 → commit/push → Linux pull → Linux 실행 검증 순서를 재현할 수 있다.
- “Linux에서 실제 테스트”를 “Linux 테스트 완료 전에는 운영 소스 병합·push 금지”로 해석할 여지가 없다.
- 로컬 운영 소스 반영과 Linux 서비스 적용이 서로 다른 단계로 정의된다.
- Linux 실패 시 서버에서 직접 고치지 않고 Windows Staging 흐름으로 복귀한다.
- Rule, 실행 노드, human map, 기준선, manifest가 같은 의미와 버전으로 검증된다.
- 기존 Staging 작업이나 애플리케이션 코드·DB에는 변경이 없다.

