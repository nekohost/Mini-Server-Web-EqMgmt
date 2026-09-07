# [기획서] AI 거버넌스·검증 기준의 계층형 노드 분산 및 사용자용 통합 Rule 전환

## 0. 문서 상태

- 상태: 노드 및 사용자용 통합 `Rule.md` Staging 구현·정적 검증 완료, 사용자 검토 대기
- 구현 여부: Staging 노드·통합 Rule·양방향 추적성 구현 완료, 루트 전환 미구현
- 현재 `Rule.md` 처리: 영구 유지 대상, 본 계획 단계에서는 수정 금지
- 현재 `GEMINI.md` 처리: 0조 삭제 확인, 본 계획 단계에서는 유지
- 현재 `VALIDATION_METHODOLOGY.md` 처리: 유지, 수정·이동·삭제 금지
- 최종 목표: `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md`의 모든 의미를 AI 실행용 계층형 노드와 사용자 열람용 통합 `Rule.md` 양쪽에 손실 없이 유지한다. AI는 노드를 읽고, 사용자는 통합 `Rule.md`에서 전체 규칙과 대응 노드 포인터를 한 번에 확인한다.
- 본 문서의 승인 범위: 이 계획의 승인만으로 루트 `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md` 또는 운영 소스코드를 변경하거나 삭제할 권한은 발생하지 않는다. 통합 `Rule.md`는 먼저 `Staging/Rule.md`로 작성하고 별도 검증·승인 후에만 루트에 반영한다.

### 개정 이력

- 개정 1: `Rule.md`의 계층형 노드 분산 제안
- 개정 2: `VALIDATION_METHODOLOGY.md`와 `GEMINI.md` 제어 조항의 공통 node화 반영
- 개정 3: `Rule.md` 폐기 방침 철회. 세 문서의 집대성인 사용자 전용 통합 핸드북으로 영구 유지하도록 변경
- 개정 4: `Staging/Rule.md`, `human-rule-map.yaml`, 노드 역포인터와 사람용 문서 로딩 제한을 구현하고 정적 검증 완료

---

## 1. 배경과 문제 정의

현재 거버넌스는 `Rule.md`에 프로젝트 배경, 기술 스택, 구현 규칙, 보안, 배포, 대화 기록, 문서 생명주기, 도구 사용 규칙이 함께 들어 있고, `VALIDATION_METHODOLOGY.md`에 검증 기본 원칙과 1~8단계 검증 절차가 함께 들어 있다. `GEMINI.md`는 매 행위마다 `Rule.md` 전체를 읽고 검증·검토 시 `VALIDATION_METHODOLOGY.md`를 참조하도록 강제한다. Staging 노드 분화로 AI의 컨텍스트 효율은 개선되었으나, 사용자가 모든 정책을 한 문서에서 통독하기 어려워지는 새로운 문제가 생겼다.

이 구조는 큰 모델에서는 동작할 수 있으나 다음 문제가 있다.

1. 단순 질의나 작은 수정에도 전체 규칙을 읽어야 하므로 컨텍스트 사용량이 크다.
2. 서로 무관한 규칙이 동시에 주입되어 작은 모델의 주의가 분산될 수 있다.
3. Gemini, Codex, Claude가 서로 다른 진입 파일을 사용하므로 동일 규칙의 수동 복제 시 불일치 위험이 있다.
4. 도구 이름처럼 플랫폼에 종속적인 표현과, 데이터 보존처럼 모든 플랫폼에 동일한 의도가 한 파일에 섞여 있다.
5. 두 기준 문서를 분해할 때 조항 누락이나 의미 완화가 발생했는지 기계적으로 확인할 구조가 없다.
6. 노드만 남기면 사용자가 전체 규칙 체계를 한 번에 읽고 검토하기 어렵다.
7. 사용자용 문서와 AI용 노드가 별도로 갱신되면 의미 표류가 발생할 수 있다.

따라서 사용자와 AI의 읽기 방식 자체를 분리한다. AI는 결정적 라우터가 선택한 작은 노드를 읽고, 사용자는 세 원본의 전체 의미를 통합한 `Rule.md`를 읽는다. 두 표현은 동일한 규칙 ID와 노드 포인터로 연결하고 동기화 검사를 통과해야만 활성 버전으로 인정한다.

---

## 2. 목표

### 2-1. 필수 목표

1. 현행 `Rule.md`와 `VALIDATION_METHODOLOGY.md`의 모든 번호 조항 및 단계별 관찰점에 영구 식별자와 대상 노드를 부여한다.
2. 각 조항의 강제 수준, 적용 조건, 예외, 선행 규칙 및 검증 방법을 보존한다.
3. Codex, Gemini/Antigravity, Claude가 동일한 공통 규칙 원본을 사용하도록 한다.
4. 작은 컨텍스트 모델은 작업에 필요한 규칙 경로만 부모에서 자식 방향으로 읽도록 한다.
5. 안전, 데이터 보존, 승인 경계 같은 절대 규칙은 라우팅 결과와 무관하게 항상 주입한다.
6. 모델이 스스로 규칙을 선택하는 방식과 외부 로더가 규칙을 선택하는 방식을 모두 지원한다.
7. 기존 단일 파일 제거 전 구 규칙·검증 기준과 신 노드의 의미 동등성을 정적 검사와 실제 시나리오로 검증한다.
8. 전환 도중에는 구 규칙과 신 규칙을 병행하여 규칙 공백이 발생하지 않게 한다.
9. 루트 `Rule.md`를 현재 `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md`의 내용을 집대성한 사용자용 통합 핸드북으로 영구 유지한다.
10. 통합 `Rule.md`의 각 항에 대응 규칙 ID와 실제 노드 경로를 사람이 읽을 수 있는 포인터로 표시한다.
11. AI 진입 파일에는 통합 `Rule.md`를 자동 작업 컨텍스트로 읽지 않도록 명시하여 작은 모델의 컨텍스트 이점을 유지한다.
12. 통합 `Rule.md`와 노드가 불일치하면 해당 거버넌스 버전의 활성화를 차단한다.

### 2-2. 비목표

1. 본 계획에서는 루트 `Rule.md`, `VALIDATION_METHODOLOGY.md`를 수정, 이동 또는 삭제하지 않는다.
2. 본 계획에서는 `GEMINI.md`를 수정하지 않는다.
3. 본 계획에서는 운영 코드나 `Staging/` 코드를 수정하지 않는다.
4. 현행 규칙의 타당성을 임의로 재해석하거나 완화하지 않는다.
5. 플랫폼의 시스템·개발자 지시보다 저장소 규칙을 우선시키려 하지 않는다. 충돌 시 플랫폼 상위 지시를 따르고 충돌 사실을 보고하도록 설계한다.
6. 사용자용 통합 `Rule.md`를 AI의 기본 자동 로딩 문서로 사용하지 않는다.
7. 통합 `Rule.md`를 요약본으로 축소하거나 세 원본의 세부 조건을 생략하지 않는다.

---

## 3. 설계 원칙

### 3-1. 대상별 이중 표현과 동기화 게이트

규칙은 같은 의미를 두 가지 독자층에 맞춰 표현한다.

- `Rule.md`: 사용자가 전체 정책을 통독하고 변경 의도를 판단하는 **사용자용 의미 기준(Human Canonical Reference)**
- `.agent-governance/` 노드: AI가 작업별로 선택해 실행하는 **기계 실행용 투영본(Machine Operational Projection)**

두 표현 중 하나만 단독으로 변경해서는 안 된다. 정책 변경은 같은 변경 단위에서 통합 `Rule.md`, 대상 노드, traceability map을 함께 갱신하고 동기화 검사를 통과해야 완료된다. 불일치가 발견되면 어느 한쪽을 묵시적으로 우선하지 않고 거버넌스 버전 활성화를 차단하여 사용자 판단을 요청한다.

`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`에는 공통 내용을 수동 복제하지 않고, 각 플랫폼이 공통 노드를 찾고 읽는 방법만 둔다. 이 진입 파일들은 통합 `Rule.md`가 사용자용 문서이며 기본 작업 컨텍스트가 아님을 명시한다.

단, 모델이 참조 지시를 놓쳤을 때 즉시 위험한 작업을 수행하지 않도록 다음 최소 안전 커널은 각 진입 파일에 자동 생성 방식으로 포함할 수 있다.

- 제안·질문·검토 요청은 승인 없는 구현으로 확대하지 않는다.
- 파괴적 작업과 외부 반영은 명시적 승인을 요구한다.
- 데이터와 기존 사용자 변경 사항을 보존한다.
- 필요한 규칙 노드를 읽지 못하면 추측하여 실행하지 않는다.
- 플랫폼 상위 지시와 저장소 규칙이 충돌하면 충돌을 보고한다.

이 중복은 사람이 편집하지 않고 공통 커널에서 생성하여 내용 표류를 방지한다.

### 3-2. 통합 `Rule.md`의 표현 원칙

1. 현재 `Rule.md`와 동일한 번호식 Markdown 문서 형식을 유지한다.
2. 기존 문장을 의미 손실 없이 보존하되 중복되는 세 문서의 내용은 사용자 관점에서 읽기 좋은 한 위치로 통합한다.
3. 각 말단 조항 뒤에는 규칙 ID와 대응 노드 ID·경로를 눈에 띄되 본문을 방해하지 않는 포인터로 표시한다.
4. 포인터는 렌더링 화면에서도 보여야 하므로 HTML 주석만 사용하지 않는다.
5. 노드 헤더의 `source_rules`, `source_validations`, `source_entrypoints`와 양방향으로 일치해야 한다.
6. `Rule.md` 상단에 “사용자 열람용이며 AI 자동 로딩 대상이 아님”을 명시한다.

권장 포인터 형식:

```markdown
4-5-1. 민감 정보 하드코딩 금지: ...
        `[규칙 ID: RULE-4.5.1 | 노드: engineering.security | 경로: .agent-governance/engineering/security.md]`
```

하나의 항이 여러 노드에 걸치면 주 노드를 먼저 적고 보조 노드를 이어 적는다. 한 노드가 여러 항을 담당하는 것은 허용하되, 포인터가 없는 말단 조항은 허용하지 않는다.

### 3-3. 부모에서 자식으로 내려가는 규칙 경로

모든 작업은 다음 순서로 규칙을 로딩한다.

```text
안전 커널
  └─ 프로젝트 문맥
      └─ 작업 유형
          └─ 기술 영역
              └─ 대상 경로
                  └─ 승인된 작업 계획
```

하위 노드는 상위 노드를 구체화하거나 강화할 수 있으나, 상위 안전 규칙을 완화할 수 없다.

### 3-4. 의미와 도구 구현의 분리

공통 노드는 “Diff와 Undo가 가능한 편집 수단을 사용한다”처럼 의도를 정의한다. 플랫폼별 진입 파일 또는 capability profile은 이를 다음과 같이 번역한다.

```text
공통 의도: 검토 가능한 패치 방식으로 파일을 변경한다.
Codex: apply_patch 계열 편집 수단
Antigravity: IDE 내장 파일 편집 API
Claude: 해당 실행 환경이 제공하는 구조화된 편집 수단
```

플랫폼에 특정 도구가 없으면 유사 도구를 임의로 가장하지 않고, 가능한 대안과 제한을 보고한다.

### 3-5. 규칙의 점진적 공개

라우터는 관련성이 확인된 노드만 선택한다. 그러나 다음 노드는 항상 로딩한다.

- 안전 및 승인 경계
- 데이터와 사용자 변경 사항 보존
- 현재 작업이 제안인지 실행인지 판별하는 규칙
- 규칙 충돌 및 기능 부재 보고 규칙

---

## 4. 제안 디렉터리 구조

```text
프로젝트 루트/
├─ Rule.md                           # 사용자용 전체 거버넌스 통합 핸드북
├─ AGENTS.md                         # Codex용 자동 인식 진입점
├─ GEMINI.md                         # Antigravity/Gemini용 자동 인식 진입점
├─ CLAUDE.md                         # Claude용 진입점
│
├─ .agent-governance/
│  ├─ manifest.yaml                  # 노드 목록, 버전, 해시, 로딩 순서
│  ├─ router.yaml                    # 작업·경로·위험도별 노드 선택표
│  ├─ capabilities/
│  │  ├─ codex.yaml                  # Codex 도구 대응표
│  │  ├─ gemini-antigravity.yaml     # Antigravity 도구 대응표
│  │  └─ claude.yaml                 # Claude 도구 대응표
│  ├─ core/
│  │  ├─ kernel.md                   # 항상 로딩되는 최상위 불변 규칙
│  │  ├─ precedence.md               # 충돌·우선순위·예외 처리
│  │  └─ task-modes.md               # 질문/검토/계획/구현/검증 구분
│  ├─ context/
│  │  ├─ project.md                  # 프로젝트 목적과 사용자 요구
│  │  ├─ stack.md                    # 기술 스택
│  │  └─ deployment-topology.md      # Windows→GitHub→Linux Lite
│  ├─ engineering/
│  │  ├─ data-model.md               # 장비 필드와 CRUD 요구
│  │  ├─ schema-evolution.md         # 컬럼 확장 및 의존성 체인
│  │  ├─ code-comments.md            # 3단 메타 주석 및 상세 주석
│  │  ├─ data-integrity.md            # DROP 금지, 마이그레이션
│  │  ├─ security.md                 # 비밀, 디버그, 세션, 입력 불신
│  │  └─ frontend-responsive.md      # 모바일·폴더블·PC 레이아웃
│  ├─ operations/
│  │  ├─ local-execution.md          # Windows 로컬 테스트 금지
│  │  ├─ server-execution.md         # Linux Lite 실행·테스트
│  │  └─ staging.md                  # Staging의 목적과 정리 규칙
│  ├─ records/
│  │  ├─ conversation-integrity.md   # 원문 보존, 비밀 치환
│  │  ├─ conversation-storage.md     # 경로, 날짜, append
│  │  ├─ timestamps.md               # KST 및 Z 검증
│  │  ├─ encoding.md                 # UTF-8 및 PowerShell 주의
│  │  └─ scratch-retention.md        # 10개 FIFO 정리
│  ├─ workflow/
│  │  ├─ proposals-roadmap.md        # 제안·로드맵 대기열
│  │  ├─ plans.md                    # 영구 기획서
│  │  ├─ staging-merge.md            # 검증·승인·병합
│  │  ├─ completion-history.md       # FEATURES 및 미구현 목록 정리
│  │  └─ multi-agent-handoff.md      # AI 교차 투입과 자아 식별
│  ├─ tools/
│  │  ├─ read-execute.md             # 터미널 읽기·실행 원칙
│  │  ├─ file-editing.md             # 구조화된 파일 편집 원칙
│  │  └─ conversation-exception.md   # Chat 기록의 예외
│  ├─ validation/
│  │  ├─ kernel.md                   # 검증 기본 원칙과 최소 기준 확장 의무
│  │  ├─ orchestration.md            # task 선작성, 순차 검증, 종합 보고서 병합
│  │  └─ phases/
│  │     ├─ 01-governance.md         # 거버넌스 준수성 검증
│  │     ├─ 02-user-intent.md        # 사용자 의도 달성도 검증
│  │     ├─ 03-static-logic.md       # 논리적 구동 가능성 검증
│  │     ├─ 04-production-impact.md  # 운영 병합 사이드이펙트
│  │     ├─ 05-security-edge.md      # 보안 및 예외 엣지 케이스
│  │     ├─ 06-rollback.md           # 롤백 및 역방향 파급 효과
│  │     ├─ 07-human-error.md        # 휴먼 에러 및 UX 방어
│  │     └─ 08-ai-meta.md            # AI 메타 거버넌스
│  ├─ traceability/
│  │  ├─ rule-map.yaml               # Rule 조항→노드→검증의 전수 매핑
│  │  ├─ validation-map.yaml         # 검증 원칙·관찰점→노드→검사의 전수 매핑
│  │  ├─ entrypoint-map.yaml         # GEMINI 제어 조항→공통 노드·진입점 매핑
│  │  ├─ human-rule-map.yaml         # 통합 Rule 항목↔세 원본 ID↔실제 노드 양방향 매핑
│  │  └─ exceptions.md               # 모순·기능 부재·사용자 결정 기록
│  └─ generated/
│     └─ context-pack.md              # 작업별 생성물, 기본적으로 커밋 제외
│
└─ tools/
   └─ agent-context-loader.*          # 추후 구현할 결정적 컨텍스트 조립기
```

통합 `Rule.md`는 AI router의 노드 목록에 넣지 않는다. manifest에는 `human_reference`와 해시만 기록하며, `always_load` 또는 작업 route에 포함하지 않는다.

디렉터리명은 구현 승인 시 조정할 수 있다. 중요한 것은 사용자용 전체 문서와 AI용 공통 노드 원본을 대상에 맞게 분리하고 추적성으로 결합하는 구조다.

---

## 5. 노드 표준 형식

모든 노드는 작은 모델이 기계적으로 해석할 수 있도록 동일한 헤더를 사용한다.

```yaml
---
id: engineering.schema-evolution
version: 1
parent: engineering.data-model
source_rules:
  - RULE-4.1
  - RULE-4.2
source_validations: []
human_rule_sections:
  - "4-5-1"
applies_when:
  intents:
    - schema-change
    - equipment-field-change
  paths:
    - app.py
    - db_migration.py
    - templates/index.html
priority: high
always_load: false
estimated_tokens: 500
may_strengthen_parent: true
may_relax_parent: false
---

## 반드시 수행

## 금지

## 의존성 체크리스트

## 완료 조건

## 충돌 또는 기능 부재 시 행동
```

노드 작성 규칙은 다음과 같다.

1. 한 노드는 하나의 결정 영역만 다룬다.
2. 조항 원문의 강도를 낮추지 않는다. `반드시`, `금지`, `권고`를 서로 바꾸지 않는다.
3. 예외 조항은 본문에서 분리하고 예외가 적용되는 정확한 조건을 적는다.
4. 플랫폼 도구명은 capability profile로 이동한다.
5. 설명보다 실행 조건과 완료 조건을 우선한다.
6. 일반 노드는 200~600토큰, 안전 커널은 800토큰 이내를 목표로 한다.
7. 노드가 커지면 하위 노드로 분리하되 한 작업의 기본 경로가 과도하게 깊어지지 않게 한다.
8. `human_rule_sections`는 통합 `Rule.md`의 실제 번호와 일치해야 한다.
9. 통합 `Rule.md`의 포인터 대상은 manifest에 등록된 실제 노드여야 한다.

---

## 6. 현행 `Rule.md` 전수 분배 계획

아래 표는 현행 대분류와 모든 하위 조항군의 목적지를 지정한다. 실제 이전 단계에서는 `rule-map.yaml`에 각 말단 번호를 개별 행으로 기록하여 누락을 검사한다.

| 현행 조항 | 보존할 의미 | 대상 노드 |
|---|---|---|
| 서문 | 장비 및 자산 통합 관리 시스템이라는 프로젝트 정체성 | `context/project.md` |
| 1.1 | Flask 및 REST API 학습·운영 목적 | `context/project.md` |
| 1.2 | Windows 개발→GitHub→Linux Lite 배포 흐름 | `context/deployment-topology.md` |
| 1.3 | 상세 주석 및 의존성 여파 안내 요구 | `engineering/code-comments.md` |
| 2.1~2.4 | Python, Flask, SQLite, DBeaver, HTML, Vanilla JS, Tailwind | `context/stack.md` |
| 2.5 | 외부 의존성 사용 시 무의존 대안도 함께 제안 | `context/stack.md` |
| 2.6~2.7 | 미니서버 주소와 접속 URL | `context/deployment-topology.md` |
| 3.1.1 | 장비 기본 필드 | `engineering/data-model.md` |
| 3.1.2 | CRUD 완전 제공 | `engineering/data-model.md` |
| 3.2.1~3.2.3 | 화면 크기별 1·2·3~4열 반응형 기준 | `engineering/frontend-responsive.md` |
| 3.2.4 | 무거운 JS 회피 및 경량 Tailwind 활용 | `engineering/frontend-responsive.md` |
| 4 서문 | 모든 AI 작업자에게 적용 | `core/kernel.md` |
| 4.1.1 | `sqlite3.Row` 기반 컬럼 확장성 | `engineering/schema-evolution.md` |
| 4.2.1~4.2.3.3 | 컬럼 추가 시 DB 정의·INSERT·폼·payload·카드 동시 수정 | `engineering/schema-evolution.md` |
| 4.3.1~4.3.3 | 함수/API의 역할·의존성·변경 영향도 주석 | `engineering/code-comments.md` |
| 4.3 후단 | 각 코드 줄의 상세 설명 주석 | `engineering/code-comments.md` |
| 4.4.1 | 기존 테이블의 임의 DROP 및 초기화 금지 | `engineering/data-integrity.md` 및 `core/kernel.md` |
| 4.4.2 | ALTER 또는 안전한 이전 절차 사전 안내 | `engineering/data-integrity.md` |
| 4.5.1 | 비밀 하드코딩 금지, 환경변수와 gitignore | `engineering/security.md` |
| 4.5.2 | FLASK_DEBUG 환경변수 제어 | `engineering/security.md` |
| 4.5.3 | 세션 쿠키, CSRF, 외부 입력 불신, 서버 세션 권한 검사 | `engineering/security.md` |
| 5.1.1 | Windows PC에서 로컬 테스트 금지 | `operations/local-execution.md` |
| 5.1.2 | 테스트와 구동은 Linux Lite 서버에서 수행 | `operations/server-execution.md` |
| 5.1.3 | Staging은 실행본이 아니라 검토용 안전 복사본 | `operations/staging.md` |
| 5.1.4 | 배포 및 실행 명령 예시 | `operations/server-execution.md` |
| 6 서문 | 대화의 날짜별 Markdown 기록 | `records/conversation-storage.md` |
| 6.1.1~6.1.2 | 사용자·AI 원문과 코드·명령의 무수정 보존 | `records/conversation-integrity.md` |
| 6.1.3 | 실제 AI 모델명과 KST 헤더 | `records/conversation-integrity.md` 및 `workflow/multi-agent-handoff.md` |
| 6.1.4 | 비밀·개인정보 자리표시자 치환 | `records/conversation-integrity.md` 및 `engineering/security.md` |
| 6.1.5 | append 원칙과 기존 기록 수정 제한 | `records/conversation-storage.md` |
| 6.1.6 | Chat 기록과 일반 파일 편집 수단의 구분 | `records/conversation-storage.md` 및 `tools/conversation-exception.md` |
| 6.1.7 | Z 표기의 실제 시간대 검증 | `records/timestamps.md` |
| 6.1.8~6.1.9 | UTF-8 중간 파일과 PowerShell 리터럴 Here-String | `records/encoding.md` 및 플랫폼 capability profile |
| 6.1.10.1~6.1.10.3 | scratch 10개 FIFO, 턴 중 유예, 영구 문서와 구분 | `records/scratch-retention.md` |
| 6.2.1~6.2.8 | 승인 없는 백그라운드 기록, 중간 안내 포함, 날짜 경로·회전 | `records/conversation-storage.md` |
| 6.3.1 | 사용자 헤더 포맷 | `records/conversation-integrity.md` |
| 6.3.2~6.3.4 | 적용 변경과 제안 구분, 선행조건, 코드 블록 보존 | `records/conversation-integrity.md` |
| 6.4.1~6.4.2 | 연·월·일 경로와 두 자리 이름 | `records/conversation-storage.md` |
| 6.4.3 | 대화 삭제·덮어쓰기의 재확인 | `records/conversation-storage.md` 및 `core/kernel.md` |
| 6.4.4 | 과거 기록의 미확인 시각 표기 | `records/timestamps.md` |
| 7 서문 | 문서 생명주기 파이프라인 강제 | `workflow/plans.md` |
| 7.1.1~7.1.2 | PROPOSALS·ROADMAP과 미구현 목록 병기 | `workflow/proposals-roadmap.md` |
| 7.2.1~7.2.2 | 작업 전 Plan 작성과 `Plans/` 영구 기록 | `workflow/plans.md` |
| 7.3.1~7.3.2 | 운영 수정 전 Staging 검증 | `operations/staging.md` 및 `workflow/staging-merge.md` |
| 7.3.3 | 승인·병합 후 Staging 비우기 | `workflow/staging-merge.md` |
| 7.3.4 | Staging 계획서의 Plans 아카이빙 후 삭제 | `workflow/staging-merge.md` |
| 7.4.1~7.4.3 | 완료 이력 보존, 미구현 목록 제거, FEATURES 추가 | `workflow/completion-history.md` |
| 7.5.1~7.5.4 | 다중 AI 역할 인지, 승인 계획 승계, 실제 모델명 기록 | `workflow/multi-agent-handoff.md` |
| 8 서문 | 모든 AI의 파일 시스템 및 터미널 제어 | `tools/read-execute.md` 및 `tools/file-editing.md` |
| 8.0 | Chat 디렉터리 예외 및 6조 우선 | `tools/conversation-exception.md` |
| 8.1.1~8.1.2 | 터미널 읽기·실행 한정, 일반 파일 쓰기 금지 | `tools/read-execute.md` |
| 8.2.1~8.2.2 | 일반 쓰기는 Diff·Undo 가능한 편집 API 사용 | `tools/file-editing.md` 및 플랫폼 capability profile |

### 6-1. 현행 `VALIDATION_METHODOLOGY.md` 전수 분배 계획

검증 방법론도 `Rule.md`와 동등한 정식 node화 및 추적 대상이다. 단순 연결 문서로 남기지 않는다. 실제 이전 단계에서는 기본 원칙과 각 단계의 모든 관찰점에 `VAL-*` 영구 ID를 부여한다.

| 현행 기준 | 보존할 의미 | 대상 노드 |
|---|---|---|
| 문서 서문 | 제안·구현 계획 직후, 코드 작성·운영 병합 전에 적용하는 자체 검증 SOP | `validation/kernel.md` |
| 기본 원칙 1 | `task.md` 선작성, 1단계부터 순차 점검, 종합 보고서에 누적 병합 | `validation/orchestration.md` |
| 기본 원칙 2 | 긍정·부정을 억지로 만들지 않는 객관적·건조한 판단 | `validation/kernel.md` |
| 기본 원칙 3 | 실제로 존재하는 긍정·부정 측면을 독립 도출하고 누락 없이 비교 | `validation/kernel.md` |
| 기본 원칙 4 | 문서의 관찰점은 최소 기준이며 숨은 엣지 케이스를 자율 확장 발굴 | `validation/kernel.md` 및 모든 phase 노드 |
| 1단계 서문 | `Rule.md` 및 전환 후 대응 거버넌스 노드 준수성 심문 | `validation/phases/01-governance.md` |
| 1단계 관찰점 1 | 프론트엔드·백엔드 로직 분리 준수 | `validation/phases/01-governance.md` |
| 1단계 관찰점 2 | 스키마 변경의 비파괴성과 기존 데이터 보존 | `validation/phases/01-governance.md` |
| 1단계 관찰점 3 | 지정된 격리 환경 사용 강제 | `validation/phases/01-governance.md` |
| 1단계 관찰점 4 | 프레임워크 기본값에 의존하지 않고 커스텀 규칙 수용 | `validation/phases/01-governance.md` |
| 1단계 관찰점 5 | 외부 라이브러리의 인가 여부 | `validation/phases/01-governance.md` |
| 2단계 서문 | 최초 사용자 의도와 계획의 간극 비교 | `validation/phases/02-user-intent.md` |
| 2단계 관찰점 1 | 고유 요구사항의 데이터 모델 반영 | `validation/phases/02-user-intent.md` |
| 2단계 관찰점 2 | 기존 거버넌스 워크플로우 통합 | `validation/phases/02-user-intent.md` |
| 2단계 관찰점 3 | 사용자 제약 조건의 누락 여부 | `validation/phases/02-user-intent.md` |
| 2단계 관찰점 4 | 사용자 기대 UI/UX 동선 반영 | `validation/phases/02-user-intent.md` |
| 2단계 관찰점 5 | 향후 확장을 고려한 유연성 | `validation/phases/02-user-intent.md` |
| 3단계 서문 | 로컬 실행 금지 제약 아래 설계 논리로 구동 병목 분석 | `validation/phases/03-static-logic.md` |
| 3단계 관찰점 1 | 데이터 폭증 시 스캔·락·비효율 쿼리 | `validation/phases/03-static-logic.md` |
| 3단계 관찰점 2 | 반복 호출과 클라이언트 메모리 누수 | `validation/phases/03-static-logic.md` |
| 3단계 관찰점 3 | 트랜잭션 예외와 롤백 방어 | `validation/phases/03-static-logic.md` |
| 3단계 관찰점 4 | 비동기 경합과 교착 상태 | `validation/phases/03-static-logic.md` |
| 3단계 관찰점 5 | 캐시 만료와 정합성 | `validation/phases/03-static-logic.md` |
| 4단계 서문 | 격리 결과의 운영 병합 시 충돌 진단 | `validation/phases/04-production-impact.md` |
| 4단계 관찰점 1 | 라우터 주소 및 우선순위 충돌 | `validation/phases/04-production-impact.md` |
| 4단계 관찰점 2 | 권한 제어 우회 노출 | `validation/phases/04-production-impact.md` |
| 4단계 관찰점 3 | 레거시 침범과 개방·폐쇄 원칙 | `validation/phases/04-production-impact.md` |
| 4단계 관찰점 4 | 전역 변수·글로벌 상태의 파급 | `validation/phases/04-production-impact.md` |
| 4단계 관찰점 5 | 기존 테스트·동작의 Breaking Change | `validation/phases/04-production-impact.md` |
| 5단계 서문 | 악의적 조작과 극단 상황의 방어 | `validation/phases/05-security-edge.md` |
| 5단계 관찰점 1 | SQL Injection·XSS·CSRF 방어 | `validation/phases/05-security-edge.md` |
| 5단계 관찰점 2 | Null·Undefined·빈 문자열·타입 오류 | `validation/phases/05-security-edge.md` |
| 5단계 관찰점 3 | 민감 데이터와 통신의 평문 노출 | `validation/phases/05-security-edge.md` |
| 5단계 관찰점 4 | 오류 메시지의 내부 정보 노출 | `validation/phases/05-security-edge.md` |
| 6단계 서문 | 치명적 오류 시 안전한 이전 상태 복귀 | `validation/phases/06-rollback.md` |
| 6단계 관찰점 1 | Up뿐 아니라 Down 마이그레이션 가능성 | `validation/phases/06-rollback.md` |
| 6단계 관찰점 2 | 코드 롤백 후 신규 데이터 의존성 오염 | `validation/phases/06-rollback.md` |
| 6단계 관찰점 3 | 캐시·세션 잔여 데이터 영향 | `validation/phases/06-rollback.md` |
| 6단계 관찰점 4 | 인프라·환경변수와 부분 롤백 충돌 | `validation/phases/06-rollback.md` |
| 7단계 서문 | 엔드 유저 휴먼 에러와 UX 방어 | `validation/phases/07-human-error.md` |
| 7단계 관찰점 1 | 잘못된 동선의 명확한 피드백 | `validation/phases/07-human-error.md` |
| 7단계 관찰점 2 | 데드엔드 UI 방지 | `validation/phases/07-human-error.md` |
| 7단계 관찰점 3 | 파괴적 액션의 이중 확인 | `validation/phases/07-human-error.md` |
| 7단계 관찰점 4 | 필수값·범위 오류의 프론트엔드 1차 검증 | `validation/phases/07-human-error.md` |
| 8단계 서문 | AI 작업자의 불필요한 행위와 컨텍스트 오염 검열 | `validation/phases/08-ai-meta.md` |
| 8단계 관찰점 1 | 작업 중 생성한 scratch 정리 | `validation/phases/08-ai-meta.md` |
| 8단계 관찰점 2 | 로그·아티팩트의 환각과 맥락 오염 방지 | `validation/phases/08-ai-meta.md` |
| 8단계 관찰점 3 | 통제 규정 우회 금지 | `validation/phases/08-ai-meta.md` |
| 8단계 관찰점 4 | 승인 재촉 금지와 객관적 톤 유지 | `validation/phases/08-ai-meta.md` |

### 6-2. 검증 노드 실행 규칙

1. 제안, 기획서, 구현 계획의 검증에서는 `validation/kernel.md`, `validation/orchestration.md`, 1~8단계 노드를 모두 부모에서 자식 순으로 로딩한다.
2. 검증 단계는 병렬로 생략하거나 순서를 바꾸지 않는다. 각 단계 결과를 종합 보고서에 누적한 뒤 다음 단계로 진행한다.
3. 각 phase 파일의 관찰점은 완료 체크리스트가 아니라 최소 탐색 기준이다. AI는 작업 맥락에 맞는 추가 위험을 스스로 찾아야 한다.
4. 특정 단계에서 관찰 대상이 없으면 억지 결과를 작성하지 않고 `해당 없음`의 근거를 남긴다.
5. 검증 결과가 구현 차단 조건을 발견하면 다음 구현 단계로 자동 진행하지 않고 보고한다.
6. 일반 구현 작업에서도 승인된 계획의 검증 결과와 해당 작업에 관련된 phase 노드를 라우터가 다시 불러오도록 한다.

### 6-3. 현행 `GEMINI.md` 공통화 계획

`GEMINI.md`의 나머지 1~8조는 Antigravity의 진입 지시인 동시에 모든 AI에 적용할 가치가 있는 공통 통제 정책이다. 따라서 제품별 파일에만 남기지 않고 다음과 같이 공통 노드로 승격한다.

| 현행 조항 | 공통화할 의미 | 대상 노드 또는 진입점 |
|---|---|---|
| 1~2 | 매 작업 전 적용 규칙을 읽고 행위 직전 적합성을 판단 | 모든 제품별 진입점, `core/precedence.md`, router |
| 3 | 사용자 요청과 거버넌스 충돌 시 실행하지 않고 보고 후 재지시 대기 | `core/precedence.md`, `core/task-modes.md` |
| 4 | 질문에 먼저 답하고, 검토·보고·승인 후 실제 작업 | `core/task-modes.md` |
| 5 | 실제 작업은 Task를 만들고 순차 수행 | `validation/orchestration.md` 및 작업 실행 노드 |
| 6~6-1 | 과장 없이 근거·긍정·부정을 객관적으로 보고 | `core/kernel.md`, `validation/kernel.md` |
| 7 | 승인을 재촉하지 않음 | `core/kernel.md` |
| 8 | 검증·검토 시 Validation 전체 체인 사용 | 모든 제품별 진입점, `validation/orchestration.md` |

`entrypoint-map.yaml`은 이 대응 관계를 추적한다. 결과적으로 `GEMINI.md`는 Antigravity용 로딩 어댑터가 되고, 그 안에 있던 공통 행동 정책은 Codex와 Claude에도 동일하게 적용된다.

### 6-4. 사용자용 통합 `Rule.md` 목차 계획

통합 문서는 현행 `Rule.md`의 번호식 형식과 서술 밀도를 유지한다. 기존 1~8장은 가능한 한 현 위치를 유지하고, 다른 두 문서의 내용은 다음 장으로 통합한다.

| 통합 Rule 장 | 포함 내용 | 주요 노드 영역 |
|---|---|---|
| 1. 프로젝트 배경 및 목적 | 현행 Rule 1장 | `context/*` |
| 2. 기술 스택 및 네트워크 | 현행 Rule 2장 | `context/stack`, `context/deployment-topology` |
| 3. 핵심 요구사항 및 화면 원칙 | 현행 Rule 3장 | `engineering/data-model`, `engineering/frontend-responsive` |
| 4. 설계·의존성·보안 | 현행 Rule 4장 | `engineering/*`, `core/kernel` |
| 5. 실행 및 배포 | 현행 Rule 5장 | `operations/*` |
| 6. 대화 기록 | 현행 Rule 6장 | `records/*`, `tools/conversation-exception` |
| 7. 문서 생명주기 및 개발 파이프라인 | 현행 Rule 7장 | `workflow/*`, `operations/staging` |
| 8. 시스템 도구 운용 | 현행 Rule 8장 | `tools/*`, capability profile |
| 9. AI 공통 행동 및 승인 제어 | 현행 GEMINI 1~8조를 제품 중립적으로 통합 | `core/*`, `validation/orchestration` |
| 10. 다차원 검증 방법론 | Validation 기본 원칙과 1~8단계 전문 | `validation/kernel`, `validation/orchestration`, `validation/phases/*` |
| 11. 규칙 문서와 노드의 동기화 | 사용자용 Rule과 AI용 노드의 역할·변경 절차·불일치 차단 | manifest, `traceability/human-rule-map.yaml` |

기존 조항 번호는 추적성을 위해 가능한 한 유지한다. GEMINI와 Validation에서 편입되는 항목은 새 9장과 10장의 번호를 부여하되 원본 ID도 포인터에 함께 기록한다.

예시:

```markdown
9. AI 공통 행동 및 승인 제어
    9-1. 모든 작업 시작 시 현재 작업에 적용되는 규칙 노드를 확인한다.
         `[원본 ID: ENTRY-GEMINI.1, ENTRY-GEMINI.2 | 노드: core.precedence | 경로: .agent-governance/core/precedence.md]`

10. 다차원 검증 방법론
    10-2. 1단계: 거버넌스 준수성 검증
          `[원본 ID: VAL-PHASE.1.0~1.5 | 노드: validation.phase.01-governance | 경로: .agent-governance/validation/phases/01-governance.md]`
```

### 6-5. 통합 `Rule.md` 변경 관리

1. 사용자가 정책 변경을 요청하면 먼저 통합 `Rule.md`의 대상 조항과 포인터를 식별한다.
2. 같은 변경 단위에서 해당 노드 본문, 노드의 `human_rule_sections`, 관련 traceability map을 수정한다.
3. 의미 동등성, 포인터 유효성, ID 전수성, 해시를 검증한다.
4. 검증이 통과하기 전에는 manifest의 활성 거버넌스 버전을 올리지 않는다.
5. AI는 평상시 통합 `Rule.md`를 읽지 않지만, 사용자가 Rule 자체의 검토·개정·동기화를 요청한 경우에만 명시적으로 읽는다.
6. 자동 생성기를 도입하더라도 사용자 가독성을 훼손하는 기계적 나열을 허용하지 않는다. 초기 버전은 사람이 읽는 품질을 우선하여 작성하고 linter가 일관성을 검사한다.

---

## 7. `GEMINI.md`, `AGENTS.md`, `CLAUDE.md` 전환 계획

### 7-1. 공통 역할

각 진입 파일은 다음 기능만 담당한다.

1. 현재 에이전트와 플랫폼 capability profile을 식별한다.
2. `manifest.yaml`과 항상 로딩할 커널을 지정한다.
3. `router.yaml`을 사용하여 관련 노드를 부모부터 읽도록 지시한다.
4. 규칙을 읽지 못하거나 충돌이 있으면 실행을 중지하고 보고하도록 한다.
5. 현재 요청이 질문·제안이면 답변/계획 범위에 머물고, 구현 요청일 때만 승인된 파이프라인으로 진입한다.
6. 루트 `Rule.md`는 사용자용 통합 핸드북이므로 기본 작업 컨텍스트에 자동 로딩하지 않는다.
7. 사용자가 `Rule.md` 자체의 검토·개정·동기화를 요청했을 때에만 해당 문서와 `human-rule-map.yaml`을 읽는다.

### 7-2. `GEMINI.md`의 특별 처리

기존 0조의 삭제가 확인되어 `GEMINI.md`를 AI가 수정할 수 없다는 제약은 해소되었다. 따라서 구현 승인 후에는 다른 진입 파일과 같은 변경·Diff·검증 절차로 수정할 수 있다. 다만 본 계획 수정은 실제 `GEMINI.md` 변경 승인을 의미하지 않으므로 현재 파일은 유지한다.

현행 “매 행위마다 `Rule.md` 전체 정독” 규칙은 노드 전환이 검증되기 전까지 유지한다. 전환 완료 후에는 다음 의미로 교체한다.

```text
매 행위 전 안전 커널을 확인하고, 매 작업 전 라우터가 선택한 규칙 경로를
부모에서 자식 순으로 읽으며, 실제 행위 직전 선택된 규칙과의 적합성을 판단한다.
검증 또는 검토 작업에서는 validation/kernel, validation/orchestration 및
validation/phases/01~08 전체를 순서대로 읽고 실행한다.
Rule.md는 사용자용 통합 핸드북이므로 일반 작업에서는 자동으로 읽지 않는다.
Rule 자체의 검토·개정·동기화 요청에서만 Rule.md와 human-rule-map.yaml을 읽는다.
```

이는 검증 전에는 적용하지 않는다.

### 7-3. `AGENTS.md`

Codex 진입점으로 신규 제안한다. 루트에는 공통 부트스트랩을 두고, 필요하면 특정 디렉터리의 하위 `AGENTS.md`는 공통 노드를 가리키는 얇은 경로 어댑터로만 생성한다. 하위 파일에 실제 규칙 본문을 복사하지 않는다.

### 7-4. `CLAUDE.md`

Claude 실행 환경의 진입점으로 신규 제안한다. 지원 기능과 자동 탐색 범위는 도입 시점의 실제 환경에서 확인하고, 확인되지 않은 기능을 전제로 설계하지 않는다.

---

## 8. 라우팅 설계

`router.yaml`은 자유 서술형 판단 대신 명시적 키를 사용한다.

```yaml
routes:
  - id: database-schema-change
    match:
      intents: [add-column, alter-schema, migration]
      paths: [app.py, db_migration.py, down_migration.py, "templates/**"]
    load:
      - core/kernel
      - core/task-modes
      - context/project
      - engineering/data-model
      - engineering/schema-evolution
      - engineering/data-integrity
      - workflow/plans
      - operations/staging

  - id: proposal-review
    match:
      intents: [question, proposal, review, plan]
    load:
      - core/kernel
      - core/task-modes
      - workflow/plans
      - validation/kernel
      - validation/orchestration
      - validation/phases/01-governance
      - validation/phases/02-user-intent
      - validation/phases/03-static-logic
      - validation/phases/04-production-impact
      - validation/phases/05-security-edge
      - validation/phases/06-rollback
      - validation/phases/07-human-error
      - validation/phases/08-ai-meta
    action_limit: no-implementation
```

### 8-1. 라우팅 우선순위

1. 플랫폼 시스템·개발자 지시
2. 공통 안전 커널
3. 프로젝트 공통 노드
4. 작업 유형 노드
5. 기술 및 경로별 노드
6. 사용자 승인 기획서
7. 현재 요청의 세부 실행 조건

같은 계층에서 충돌하면 더 구체적인 적용 범위를 우선하되, 상위 안전 규칙을 완화하는 하위 규칙은 오류로 처리한다.

### 8-2. 컨텍스트 예산

- 안전 커널: 항상 포함, 목표 800토큰 이하
- 라우터 결과: 기본 4~8개 노드
- 단일 노드: 목표 200~600토큰
- 기본 context pack: 목표 4,000토큰 이하
- 초소형 모델 프로필: 목표 2,000토큰 이하, 체크리스트 중심 요약 노드 사용
- 제한 초과 시 규칙을 임의 생략하지 않고, 작업을 더 작은 단계로 분리한다.

---

## 9. 이전 절차

### Phase 0. 원본 동결 및 기준선 생성

1. `Rule.md`, `GEMINI.md`, `VALIDATION_METHODOLOGY.md`의 해시와 행 수를 기록한다.
2. `Rule.md`의 모든 번호 조항, `VALIDATION_METHODOLOGY.md`의 기본 원칙·단계·관찰점, `GEMINI.md`의 잔존 1~8조를 파싱하여 세 개의 기준 목록을 만든다.
3. 세 문서의 중복 번호, 잘못된 상호 참조, 모순 가능성을 별도 목록으로 기록한다.
4. 이 단계에서는 원본을 수정하지 않는다.

완료 조건:

- 모든 Rule 말단 조항, Validation 말단 관찰점, GEMINI 제어 조항이 고유 ID를 가진다.
- 원본 해시가 기록된다.
- 미분류 조항 수가 0이다.

### Phase 1. 추적성 원장 작성

1. Rule 조항에는 `RULE-x.y.z`, Validation 기준에는 `VAL-CORE.x` 또는 `VAL-PHASE.x.y`, GEMINI 제어 조항에는 `ENTRY-GEMINI.x` 형식의 안정 ID를 부여한다.
2. 각 ID에 원문, 강제 수준, 적용 조건, 예외, 대상 노드, 검증 사례를 연결한다.
3. 하나의 조항이 둘 이상의 노드에 필요하면 주 노드와 참조 노드를 구분한다.
4. 원문을 재작성하기 전에 먼저 그대로 추출하여 의미 비교 기준으로 남긴다.

완료 조건:

- 세 원본의 말단 항목 수와 `rule-map.yaml`, `validation-map.yaml`, `entrypoint-map.yaml`의 항목 수가 각각 일치한다.
- 누락·고아·중복 소유 조항이 없다.

### Phase 2. 공통 노드 초안 작성

1. 안전 커널부터 작성한다.
2. 프로젝트 문맥, 엔지니어링, 운영, 기록, 워크플로우, 도구, 검증 기본 원칙, 검증 1~8단계 순으로 노드를 작성한다.
3. 각 노드에 `source_rules`를 명시한다.
4. 원문을 간결화하더라도 의무 강도, 예외, 선행 승인 조건은 그대로 유지한다.

완료 조건:

- 모든 노드가 표준 헤더 검사를 통과한다.
- 모든 `source_rules`, `source_validations`, `source_entrypoints`가 해당 추적성 원장에 존재한다.
- 세 원장의 모든 항목이 하나 이상의 노드 또는 진입점에서 소비된다.

### Phase 3. 라우터와 capability profile 작성

1. 작업 의도, 대상 파일, 위험 등급별 라우트를 만든다.
2. Codex, Antigravity, Claude에서 사용 가능한 읽기·편집·터미널·대화 기록 기능을 실측한다.
3. 공통 의도를 각 플랫폼 도구로 번역한다.
4. 기능이 없는 플랫폼의 fail-closed 행동을 정의한다.

완료 조건:

- 대표 작업마다 결정적인 노드 목록이 나온다.
- 같은 입력은 같은 노드 경로를 생성한다.
- 안전 노드는 어떤 라우트에서도 누락되지 않는다.

### Phase 4. 제품별 진입 파일 준비

1. `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` 변경 초안을 작성한다.
2. 세 진입 파일이 Rule 노드와 Validation 노드의 공통 manifest를 참조하도록 한다.
3. 진입 파일의 공통 부분은 생성기로 만들고 수동 편집을 금지한다.
4. 플랫폼별 자동 탐색 및 하위 파일 병합 동작을 실제로 확인한다.

완료 조건:

- 각 플랫폼이 동일한 테스트 요청에서 같은 공통 규칙 ID를 로딩한다.
- 진입 파일의 생성 원본과 결과 해시가 일치한다.
- 사용자가 진입 파일 변경안을 승인하기 전에는 현행 `GEMINI.md`가 유지된다.

### Phase 5. 이중 운용 검증

1. 현행 `Rule.md` 및 `VALIDATION_METHODOLOGY.md` 전체 로딩 결과와 새 노드 로딩 결과를 같은 시나리오에 적용한다.
2. 답변, 제안, 구현, DB 변경, 보안 변경, Staging 병합, 대화 기록 시나리오를 비교한다.
3. 새 체계가 현행보다 약한 결정을 내리면 실패로 판정한다.
4. 작은 모델과 큰 모델에서 각각 누락률과 컨텍스트 사용량을 측정한다.

완료 조건:

- 필수 시나리오의 의미 동등성 검증 100% 통과
- 안전 관련 누락 0건
- 미해결 충돌 0건
- 사용자 검토 완료

### Phase 6. 사용자용 통합 `Rule.md` Staging 초안

1. 현행 `Rule.md` 형식과 1~8장 내용을 보존한 `Staging/Rule.md`를 작성한다.
2. 현행 `GEMINI.md`의 공통 행동 통제를 제품 중립적인 9장으로 편입한다.
3. `VALIDATION_METHODOLOGY.md`의 기본 원칙과 1~8단계를 10장으로 전문 편입한다.
4. 사용자용 문서와 노드의 역할·동기화 규칙을 11장으로 추가한다.
5. 모든 말단 조항에 규칙 원본 ID, 노드 ID, 실제 상대 경로 포인터를 표시한다.
6. `human-rule-map.yaml`을 작성하여 통합 Rule 항목과 세 추적성 원장 및 노드를 연결한다.

완료 조건:

- 세 원본의 의미가 통합 `Rule.md`에서 누락되지 않는다.
- 포인터가 없는 말단 조항이 0개다.
- 존재하지 않는 노드 경로와 ID가 0개다.
- 문서가 현재 `Rule.md`와 유사한 번호식 서술 형식으로 자연스럽게 읽힌다.

### Phase 7. 이중 표현 동기화 및 사용자 가독성 검증

1. 통합 `Rule.md`의 각 항과 노드의 의미를 양방향 비교한다.
2. `human-rule-map.yaml`이 `rule-map.yaml`, `validation-map.yaml`, `entrypoint-map.yaml`의 모든 항목을 소비하는지 검사한다.
3. 통합 Rule에만 있고 노드에 없는 정책, 노드에만 있고 통합 Rule에 없는 정책을 모두 실패 처리한다.
4. 포인터가 렌더링 화면과 원문 양쪽에서 식별 가능한지 확인한다.
5. 사용자가 통합 Rule만 읽어도 프로젝트 배경, 개발 규칙, 승인 경계, 검증 절차를 이해할 수 있는지 정성 검토한다.
6. 작은 모델은 통합 Rule 없이도 동일한 대표 시나리오를 수행하는지 다시 검사한다.

완료 조건:

- 양방향 누락 0건
- 의미 강도 불일치 0건
- 잘못된 포인터 0건
- 사용자 검토 완료

### Phase 8. 정식 전환과 관찰 기간

1. 사용자 승인 후에만 검증된 `Staging/Rule.md`를 루트 `Rule.md`에 반영한다.
2. 모든 제품별 진입 파일을 노드 기반 부트스트랩으로 전환하고 일반 작업에서 `Rule.md`를 읽지 않도록 한다.
3. manifest에 `human_reference: Rule.md`와 통합 Rule 해시를 기록하되 route 또는 `always_load`에는 포함하지 않는다.
4. `VALIDATION_METHODOLOGY.md`의 향후 상태는 사용자 선택에 따라 유지, 호환 포인터화, 아카이브 중 하나로 별도 결정한다.
5. `GEMINI.md`는 Antigravity 진입점으로 유지하되 공통 정책 본문 대신 노드 로딩 지시를 담당한다.
6. 관찰 기간 동안 Rule↔노드 동기화 오류와 플랫폼별 규칙 누락을 감시한다.

완료 조건:

- 통합 `Rule.md`가 사용자용 전체 핸드북으로 유지된다.
- 모든 지원 에이전트가 통합 Rule 전체를 읽지 않고 노드만으로 대표 시나리오를 통과한다.
- Rule↔노드 동기화 검사 통과
- 롤백 절차 검증 완료

`Rule.md`는 이 전환의 삭제 대상이 아니다. 기존 내용을 새 통합 내용으로 대체하는 작업은 별도 Diff 검토와 사용자 승인을 요구한다.

---

## 10. 의미 동등성 검증 계획

### 10-1. 정적 완전성 검사

- Rule 말단 조항 수 = `rule-map.yaml` 항목 수인지 검사한다.
- Validation 기본 원칙·단계별 말단 관찰점 수 = `validation-map.yaml` 항목 수인지 검사한다.
- GEMINI 잔존 제어 조항 수 = `entrypoint-map.yaml` 항목 수인지 검사한다.
- 통합 `Rule.md` 말단 포인터 수와 `human-rule-map.yaml` 항목 수가 일치하는지 검사한다.
- 모든 원장 항목에 대상 노드와 최소 하나의 검증 사례가 있는지 검사한다.
- 노드에 존재하는 모든 `source_rules`와 `source_validations`가 실제 원본 항목인지 검사한다.
- 진입 파일이 존재하지 않는 노드를 참조하지 않는지 검사한다.
- 안전 커널을 완화하는 하위 노드가 없는지 검사한다.
- 문서 내부의 잘못된 상호 참조를 탐지한다.
- manifest의 `human_reference`가 존재하고 route 및 `always_load`에는 포함되지 않는지 검사한다.
- 통합 Rule↔노드 양방향 고아 항목이 없는지 검사한다.

### 10-2. 대표 시나리오 검사

| 시나리오 | 반드시 로딩할 핵심 규칙 |
|---|---|
| 단순 질문 | task-modes, 객관적 보고, 구현 금지 |
| 기능 제안 | Plans 파이프라인, 검증 방법론, 구현 금지 |
| 장비 컬럼 추가 | schema-evolution, data-integrity, code-comments, staging |
| DB 복원 구현 | data-integrity, security, staging, 승인 경계 |
| 프론트엔드 카드 변경 | frontend-responsive, code-comments, staging |
| 비밀 설정 변경 | security, file-editing, deployment topology |
| 대화 기록 | conversation-integrity, storage, timestamps, encoding |
| 완료 기능 병합 | staging-merge, completion-history, multi-agent handoff |
| 파일 삭제 요청 | kernel, task-modes, 해당 파일 생명주기, 재확인 조건 |
| 사용자의 전체 규칙 열람 | 통합 `Rule.md`만으로 세 원본의 전체 의미와 노드 포인터 확인 |
| AI 일반 작업 | 통합 `Rule.md` 미로딩, router가 선택한 노드만 로딩 |
| Rule 정책 개정 | Rule 항목·대상 노드·human-rule-map을 같은 변경 단위로 갱신 |

### 10-3. 모델 규모별 검사

- 대형 모델: 전체 의미와 복합 충돌 판단 확인
- 중형 모델: 일반 경로에서 노드 선택 정확도 확인
- 소형 모델: 통합 `Rule.md` 없이 외부 로더가 생성한 context pack만 사용하여 체크리스트 준수율 확인
- 모든 모델: 규칙을 읽지 못한 경우 실행하지 않고 제한을 보고하는지 확인

### 10-4. N-Phase 검증 방법론 자체의 동등성 적용

본 아키텍처 계획 자체도 현행 `VALIDATION_METHODOLOGY.md`와 전환 대상 Validation 노드 양쪽의 1~8단계를 순차 적용한다. 두 결과가 다르면 정식 전환을 중단한다.

1. 현행 거버넌스 준수성
2. 사용자 의도 달성도
3. 라우터의 논리적 구동 가능성
4. 기존 개발 파이프라인과의 병합 영향
5. 규칙 우회 및 프롬프트 인젝션 위험
6. 구 체계로의 롤백 가능성
7. 사용자 승인 및 파괴적 작업 재확인
8. 다중 AI의 자아 식별과 컨텍스트 오염 방지

---

## 11. 발견된 특수 위험과 처리 방안

### 11-1. `GEMINI.md` 0조 삭제 이후의 변경 경계

- 확인 결과: 사용자 전용 수정 제한이었던 0조는 삭제되었다.
- 남은 위험: 0조 삭제가 곧바로 무승인 자동 변경을 허용하는 것은 아니다. 진입 파일을 잘못 바꾸면 Antigravity의 규칙 로딩이 중단될 수 있다.
- 처리: `GEMINI.md`도 구현 승인, 구조화된 편집, Diff 검토, 로딩 검증, 롤백 순서를 따른다. 별도의 사용자 수동 적용만을 강제하지는 않는다.

### 11-2. 대화 원문 100% 기록의 도구 의존성

- 위험: 일부 에이전트는 실제 메시지 시각, 숨겨진 시스템 메시지 또는 전체 원문 내보내기 기능을 제공하지 않을 수 있다.
- 처리: capability profile에 이용 가능한 범위를 기록한다. 실제 시각이나 원문을 확보하지 못한 경우 임의 생성하지 않고 기능 제한을 보고한다. 규칙을 충족할 수 없는 상태를 성공으로 표시하지 않는다.

### 11-3. 도구 이름의 플랫폼 종속성

- 위험: `replace_file_content`, `run_command` 같은 명칭은 다른 플랫폼에서 존재하지 않을 수 있다.
- 처리: 공통 노드는 요구되는 안전 속성을 정의하고, capability profile이 실제 도구에 대응시킨다.

### 11-4. 전역 행 단위 주석 규칙의 컨텍스트 비용

- 위험: 규칙의 비용이 크더라도 이전 과정에서 임의 완화하면 의미 보존 목표를 위반한다.
- 처리: 현행 의미 그대로 `engineering/code-comments.md`에 이전한다. 규칙 자체를 변경하려면 노드 이전과 분리된 정책 개정 제안 및 사용자 승인을 거친다.

### 11-5. 라우터 오분류

- 위험: 작은 모델이 작업 의도를 잘못 판단하여 필요한 노드를 누락할 수 있다.
- 처리: 파일 경로와 명시적 작업 유형을 우선 사용하는 결정적 로더를 권장한다. 애매하면 안전한 상위 노드를 추가하고, 파괴적 작업은 항상 고위험 노드를 강제한다.

### 11-6. 다중 진입 파일의 내용 표류

- 위험: 수동 편집된 진입 파일의 규칙이 서로 달라진다.
- 처리: 공통 부분 자동 생성, 생성 원본 해시 기록, CI 또는 정적 검사로 불일치를 실패 처리한다. 자동 생성 적용 여부와 관계없이 세 진입 파일의 변경은 Diff와 플랫폼별 로딩 검증을 거친다.

### 11-7. 검증 방법론의 자기 참조와 무한 검증

- 위험: Validation 노드를 검증하기 위해 같은 Validation 노드를 반복 호출하면 종료 조건이 사라질 수 있다.
- 처리: 원본 대비 1회의 전수 동등성 검증과 1회의 교차 시나리오 검증으로 한 사이클을 정의한다. 새 결함이 발견될 때만 수정 후 해당 단계와 영향받는 후속 단계를 재실행한다.

### 11-8. 검증 단계의 선택적 누락

- 위험: 라우터가 관련성이 낮다고 판단하여 계획 검증의 일부 단계를 제외할 수 있다.
- 처리: 제안·기획·구현 계획 검증에서는 1~8단계를 항상 하나의 고정 체인으로 로딩한다. 단계 내부 항목이 실제로 해당 없을 수는 있지만 단계 자체를 생략할 수는 없다.

### 11-9. 통합 `Rule.md`와 노드의 의미 표류

- 위험: 사용자가 보는 문서와 AI가 실행하는 노드가 서로 다른 정책을 담을 수 있다.
- 처리: `human-rule-map.yaml`, 노드의 `human_rule_sections`, 통합 Rule의 가시적 포인터를 삼중 대조한다. 어느 한쪽만 변경된 버전은 manifest에서 활성화하지 않는다.

### 11-10. 사용자용 문서의 가독성 저하

- 위험: 모든 항에 긴 경로를 넣으면 현재 Rule 형식보다 읽기 어려워질 수 있다.
- 처리: 본문은 현재 번호식 문장을 유지하고 포인터는 다음 들여쓰기 줄의 짧은 코드 표기로 통일한다. 상세 다중 매핑은 `human-rule-map.yaml`에 두고 Rule에는 주 노드와 필요한 보조 노드만 표시한다.

### 11-11. AI의 통합 Rule 자동 로딩 회귀

- 위험: 진입 파일이나 router가 통합 Rule을 다시 기본 컨텍스트에 넣으면 소형 모델 최적화가 사라진다.
- 처리: 세 제품 진입 파일에 사용자용 문서임을 명시하고, manifest 검사에서 `Rule.md`가 `always_load` 또는 일반 route에 등장하면 실패 처리한다.

---

## 12. 롤백 계획

1. 통합 Rule 반영 전에는 현행 `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md`가 계속 유효하므로 즉시 구 체계로 복귀할 수 있다.
2. 새 노드의 오류가 발견되면 진입 파일을 현행 규칙 참조 상태로 되돌리고 노드를 비활성화한다.
3. 루트 통합 Rule 반영 전 기존 `Rule.md`의 Git 복구 가능성과 정확한 Diff를 확인한다.
4. 정식 전환 후 문제가 발견되면 루트 `Rule.md`, 제품별 진입 파일, manifest를 동일한 이전 거버넌스 버전으로 함께 되돌린다.
5. `VALIDATION_METHODOLOGY.md`의 상태 변경은 통합 Rule 전환과 분리하여 롤백 가능하게 한다.
6. 롤백 과정에서 대화 기록과 기획 이력은 삭제하지 않는다.

---

## 13. 산출물 목록

구현 단계에서 다음 산출물을 순차적으로 제출한다.

1. `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md` 항목 인벤토리와 원본 해시 보고서
2. `rule-map.yaml`, `validation-map.yaml`, `entrypoint-map.yaml` 전수 추적성 원장
3. 공통 규칙 노드와 검증 1~8단계 노드 초안
4. `manifest.yaml` 및 `router.yaml`
5. 플랫폼별 capability profile
6. `AGENTS.md` 초안
7. `CLAUDE.md` 초안
8. `GEMINI.md` 변경 초안과 로딩 검증안
9. context loader 설계 및 구현안
10. 사용자용 `Staging/Rule.md` 통합 초안
11. `human-rule-map.yaml` 양방향 추적 원장
12. Rule·Validation·Entrypoint·통합 Rule의 의미 동등성 검증 보고서
13. 사용자 가독성과 포인터 검증 보고서
14. 다중 모델·다중 플랫폼 시나리오 검증 보고서
15. 루트 통합 `Rule.md` 전환 Diff 및 롤백 보고서
16. 전환 승인 보고서

---

## 14. 승인 게이트

| 게이트 | 상태 | 사용자 승인 대상 | 승인 전 금지 사항 |
|---|---|---|---|
| G0 | 완료 | 노드화 계획 | Staging 노드 생성 |
| G1 | 완료 | 원본 인벤토리와 추적성 원장 | 규칙·검증 기준 재작성 |
| G2 | 완료 | Staging Rule·Validation 노드와 router | 운영 진입 파일 전환 |
| G3 | 완료 | 사용자용 통합 Rule 구조 계획 | `Staging/Rule.md` 작성 |
| G4 | 대기 | `Staging/Rule.md`와 `human-rule-map.yaml` | 루트 `Rule.md` 변경 |
| G5 | 대기 | 의미 동등성·가독성·포인터 검증 보고서 | 통합 Rule 정식 채택 |
| G6 | 대기 | 루트 Rule·세 진입 파일·manifest의 정확한 Diff | 운영 루트 반영 |
| G7 | 대기 | 관찰 기간 결과 | 구 호환 문서 상태 변경 |

승인은 다음 단계로 진행할 권한만 부여한다. 이후 단계나 파괴적 작업의 승인을 포괄하지 않는다. `Rule.md` 삭제 게이트는 존재하지 않는다.

---

## 15. 최종 완료 기준

다음 조건을 모두 충족해야 전체 전환이 완료된 것으로 판정한다.

1. 현행 `Rule.md`의 모든 말단 조항, `VALIDATION_METHODOLOGY.md`의 모든 기본 원칙·단계·관찰점, `GEMINI.md`의 잔존 제어 조항이 해당 추적성 원장에 존재한다.
2. 모든 Rule·Validation·GEMINI 제어 항목이 하나 이상의 활성 노드 또는 진입점에 연결된다.
3. 규칙과 검증 기준의 의무 강도, 순차성, 최소 기준 확장 의무, 예외, 승인 조건이 유지된다.
4. 통합 `Rule.md`가 세 원본의 전체 의미를 현재 Rule과 유사한 번호식 형식으로 제공한다.
5. 통합 Rule의 모든 말단 항목에 유효한 규칙 ID와 노드 포인터가 있다.
6. `human-rule-map.yaml`과 노드의 `human_rule_sections`가 양방향으로 일치한다.
7. Codex, Gemini/Antigravity, Claude가 같은 공통 노드를 참조하며 일반 작업에서 통합 Rule을 자동 로딩하지 않는다.
8. 각 플랫폼에서 대표 시나리오 검증을 통과한다.
9. 작은 모델용 context pack이 안전 규칙을 누락하지 않는다.
10. 기존 문서 생명주기와 대화 기록 정책이 유지된다.
11. 미해결 충돌과 미지원 기능이 0건이거나, 사용자가 승인한 명시적 예외로 기록된다.
12. 통합 Rule과 노드가 함께 롤백 가능하다는 검증 결과가 있다.
13. 사용자가 Staging 통합 Rule과 루트 반영을 각각 별도로 승인한다.

---

## 16. 현재 판단

### 긍정적 측면

- 작업과 무관한 규칙을 매번 읽지 않아도 되어 컨텍스트 사용량을 줄일 수 있다.
- 규칙 ID와 추적성 원장으로 누락 여부를 기계적으로 검사할 수 있다.
- 플랫폼별 도구 차이를 공통 정책에서 분리할 수 있다.
- 작은 모델에는 외부 로더가 필요한 규칙만 제공하여 자기 라우팅 실패를 줄일 수 있다.
- 사용자는 통합 `Rule.md` 한 파일에서 전체 규칙·검증 기준과 실제 노드 위치를 확인할 수 있다.
- AI는 통합 Rule 전체를 읽지 않아도 되어 노드 분화의 컨텍스트 이점을 유지한다.

### 부정적 측면 및 비용

- 초기 분해, 매핑, 검증에 상당한 문서 작업이 필요하다.
- 라우터와 생성기를 관리하지 않으면 새로운 단일 실패 지점이 생긴다.
- 각 에이전트 제품의 자동 인식 방식이 달라 실제 환경별 검증이 필요하다.
- 검증 1~8단계를 항상 적용하는 작업은 컨텍스트 절감 폭이 일반 작업보다 작다.
- 의미 동등성을 단순 문자열 비교만으로 보장할 수 없어 시나리오 검증이 필요하다.
- 같은 의미를 Rule과 노드 양쪽에 유지하므로 동기화 검사와 변경 규율이 추가로 필요하다.
- 모든 말단 항목에 가시적 포인터를 넣으면 문서가 길어지고 시각적 밀도가 높아질 수 있다.

### 결론

`Rule.md`는 제거하지 않는다. 최종 구조에서 통합 `Rule.md`는 사용자가 읽는 전체 거버넌스 핸드북이 되고, Rule 노드와 Validation 노드는 AI가 작업별로 읽는 실행 투영본이 된다. 세 플랫폼 진입 파일은 동일한 manifest와 router를 사용하며 일반 작업에서 통합 Rule을 자동 로딩하지 않는다.

안전한 순서는 현재 세 원본과 Staging 노드의 전수 추적 → `Staging/Rule.md` 통합 초안 → 모든 항의 가시적 노드 포인터 부여 → Rule↔노드 양방향 동등성 및 사용자 가독성 검증 → 사용자 승인 → 루트 `Rule.md` 반영 → 플랫폼별 관찰 기간이다. 현재 단계에서는 계획서만 개정했으며 루트 `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md`는 유지한다.
