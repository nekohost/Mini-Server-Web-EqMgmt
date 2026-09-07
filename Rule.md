# Mini-Server-Web-EqMgmt 통합 거버넌스 규칙

> [!IMPORTANT]
> 이 문서는 **사용자가 전체 정책을 한 번에 읽기 위한 통합 핸드북**입니다. 일반 AI 작업의 자동 로딩 대상이 아닙니다. Codex, Gemini/Antigravity, Claude 등 AI는 각 제품 진입점과 `.agent-governance/manifest.yaml`, `.agent-governance/router.yaml`이 지정한 노드를 읽습니다. AI가 이 문서를 읽는 경우는 사용자가 Rule 자체의 검토·개정·동기화를 요청했을 때로 제한합니다.

이 프로젝트는 개인 보유 장비(노트북, 보조배터리, 모니터, 이어폰 등)를 등록하고 관리하기 위해 Windows PC에서 개발하여 GitHub를 거쳐 Linux Lite 미니서버에 배포되는 웹 애플리케이션입니다.

각 말단 항목 뒤의 포인터는 해당 정책을 AI가 실제로 읽는 규칙 ID, 노드 ID, Staging 상대 경로를 나타냅니다.

---

## 1. 프로젝트 배경 및 목적

### 1-1. 프로젝트 목적

Python Flask 백엔드와 RESTful API를 학습하고 운영하는 프로젝트입니다.

> `[규칙 ID: RULE-1.1 | 노드: context.project | 경로: .agent-governance/context/project.md]`

### 1-2. 개발 및 배포 환경

Windows PC에서 소스코드 작성과 Git Push를 수행하고, GitHub를 거쳐 Linux Lite 미니서버가 Git Pull로 배포받습니다.

> `[규칙 ID: RULE-1.2 | 노드: context.deployment-topology | 경로: .agent-governance/context/deployment-topology.md]`

### 1-3. 사용자 특성

모든 코드에는 상세한 설명 주석이 반드시 포함되어야 하며, 변경 발생 시 의존성 여파를 반드시 명확하게 안내해야 합니다.

> `[규칙 ID: RULE-1.3 | 주 노드: engineering.code-comments | 보조 노드: context.project | 경로: .agent-governance/engineering/code-comments.md]`

---

## 2. 기술 스택 및 네트워크 정보

### 2-1. Language & Backend

Python 3 + Flask를 REST API 서버로 사용합니다.

> `[규칙 ID: RULE-2.1 | 노드: context.stack | 경로: .agent-governance/context/stack.md]`

### 2-2. Database

SQLite3를 `equipment.db` 파일 형태로 사용합니다.

> `[규칙 ID: RULE-2.2 | 노드: context.stack | 경로: .agent-governance/context/stack.md]`

### 2-3. Database GUI

Windows PC용 DB GUI로 DBeaver를 사용합니다.

> `[규칙 ID: RULE-2.3 | 노드: context.stack | 경로: .agent-governance/context/stack.md]`

### 2-4. Frontend

HTML5, Vanilla JavaScript, Tailwind CSS CDN을 사용합니다.

> `[규칙 ID: RULE-2.4 | 노드: context.stack | 경로: .agent-governance/context/stack.md]`

### 2-5. 외부 의존성

외부 의존성 리소스는 필요할 때 사용할 수 있습니다. 다만 외부 의존성을 사용하지 않고 구현 가능한 방법도 동시에 제안해야 하며, 의존성의 필요성·비용·운영 영향을 함께 설명해야 합니다.

> `[규칙 ID: RULE-2.5 | 노드: context.stack | 경로: .agent-governance/context/stack.md]`

### 2-6. 미니서버 주소

미니서버 IP는 `192.168.0.166`, Flask 포트는 `5000`입니다.
백업 서버 IP는 `192.168.0.24`입니다. 이 주소는 사용자가 Staging 통합 Rule에 직접 추가한 운영 정보이므로 운영 규칙으로 병합할 때 누락하거나 이전 내용으로 덮어쓰지 않으며, 포인팅 대상 노드에도 동일하게 유지합니다.

> `[규칙 ID: RULE-2.6 | 추가 정책 ID: HUMAN-2.6-BACKUP | 노드: context.deployment-topology | 경로: .agent-governance/context/deployment-topology.md]`

### 2-7. 실제 접속 URL

모바일과 PC의 내부 네트워크 접속 URL은 `http://192.168.0.166:5000`입니다.

> `[규칙 ID: RULE-2.7 | 노드: context.deployment-topology | 경로: .agent-governance/context/deployment-topology.md]`

---

## 3. 핵심 요구사항 및 화면 최적화 원칙

### 3-1. 장비 데이터 구조

#### 3-1-1. 기본 필드

고유 ID(`id`), 장비별명(`name`), 카테고리(`category`), 제조사(`manufacturer`), 모델명(`model_name`), 구입일(`purchase_date`), 시리얼넘버(`serial_number`), 메모(`memo`)는 프로젝트 초창기의 확인된 기준 필드입니다. 이후 개발로 실제 운영 DB 구조가 달라졌을 수 있으므로 현재 운영 스키마의 확정값으로 단정하지 않습니다. `[제안-013]` DB 백업·복원 기능이 구현되고 원본 운영 DB 백업을 로컬로 안전하게 받은 뒤 실제 스키마를 확인합니다. 그전에는 AI가 실제 운영 DB를 열람하거나 이 목록만을 근거로 스키마를 변경하지 않으며, 별도의 사용자 명시 승인 없이는 운영 스키마를 확정하지 않습니다.

> `[규칙 ID: RULE-3.1.1 | 추가 정책 ID: HUMAN-3.1.1-DB-DEFERRAL | 노드: engineering.data-model | 경로: .agent-governance/engineering/data-model.md]`

#### 3-1-2. CRUD

생성, 조회, 수정, 삭제 기능을 완전하게 제공해야 합니다.

> `[규칙 ID: RULE-3.1.2 | 노드: engineering.data-model | 경로: .agent-governance/engineering/data-model.md]`

### 3-2. 실시간 반응형 및 모바일·폴더블 최적화

#### 3-2-1. 접은 스마트폰·폴더블 세로 화면

1열 카드 레이아웃(`grid-cols-1`)을 사용합니다.

> `[규칙 ID: RULE-3.2.1 | 노드: engineering.frontend-responsive | 경로: .agent-governance/engineering/frontend-responsive.md]`

#### 3-2-2. 펼친 폴더블·태블릿

2열 카드 레이아웃(`sm:grid-cols-2`)을 사용합니다.

> `[규칙 ID: RULE-3.2.2 | 노드: engineering.frontend-responsive | 경로: .agent-governance/engineering/frontend-responsive.md]`

#### 3-2-3. PC 및 대형 화면

3~4열 카드 레이아웃(`lg:grid-cols-3 xl:grid-cols-4`)을 사용합니다.

> `[규칙 ID: RULE-3.2.3 | 노드: engineering.frontend-responsive | 경로: .agent-governance/engineering/frontend-responsive.md]`

#### 3-2-4. 기기 리소스 최적화

무거운 JavaScript 라이브러리를 사용하지 않고 Vanilla JavaScript와 경량 Tailwind CSS를 우선합니다.

> `[규칙 ID: RULE-3.2.4 | 노드: engineering.frontend-responsive | 경로: .agent-governance/engineering/frontend-responsive.md]`

---

## 4. 소프트웨어 설계 및 의존성 지침

Codex, ChatGPT, Gemini, Claude 등 모든 AI가 이 프로젝트의 코드를 수정하거나 기능을 추가할 때 아래 원칙을 엄격히 준수합니다.

> `[규칙 ID: RULE-4-PREAMBLE | 노드: core.kernel | 경로: .agent-governance/core/kernel.md]`

### 4-1. 컬럼 확장성 보장

#### 4-1-1. `sqlite3.Row` 기반 확장성

DB 테이블에 새로운 컬럼이 추가되더라도 기존 코드가 파괴되지 않아야 합니다. 백엔드 DB 조회 로직은 `sqlite3.Row` 기반으로 작성하여 컬럼 추가 시 Python 코드 수정을 최소화합니다.

> `[규칙 ID: RULE-4.1.1 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

### 4-2. 컬럼 추가 시 동시 수정 체크리스트

새 컬럼을 추가할 때에는 아래 의존성 체인을 한 작업 단위로 함께 수정하고 사용자에게 영향 범위를 안내합니다.

#### 4-2-1. DB 정의

`app.py`의 `init_db()` 내 `CREATE TABLE` 구문에 새 컬럼 정의를 추가합니다.

> `[규칙 ID: RULE-4.2.1 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

#### 4-2-2. INSERT 처리

`app.py`의 `add_equipment()` 내 `INSERT INTO` 구문과 `data.get()`에 새 컬럼을 추가합니다.

> `[규칙 ID: RULE-4.2.2 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

#### 4-2-3. 프론트엔드

##### 4-2-3-1. 입력 폼

`templates/index.html`의 `<form>`에 새 값을 입력받을 `<input>`을 추가합니다.

> `[규칙 ID: RULE-4.2.3.1 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

##### 4-2-3-2. 전송 payload

JavaScript `payload` 객체에 새 필드를 추가합니다.

> `[규칙 ID: RULE-4.2.3.2 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

##### 4-2-3-3. 카드 렌더링

`fetchEquipment()`의 HTML 카드 렌더링에 `${item.새컬럼명}` 출력을 추가합니다.

> `[규칙 ID: RULE-4.2.3.3 | 노드: engineering.schema-evolution | 경로: .agent-governance/engineering/schema-evolution.md]`

### 4-3. 코드 주석 보존

모든 함수와 API 라우트 상단에 다음 메타 주석을 유지합니다.

#### 4-3-1. 역할

`[역할]`에는 함수 또는 라우트의 기능을 명시합니다.

> `[규칙 ID: RULE-4.3.1 | 노드: engineering.code-comments | 경로: .agent-governance/engineering/code-comments.md]`

#### 4-3-2. 의존성 관계

`[의존성 관계]`에는 의존하는 함수·파일과 이 코드에 의존하는 프론트엔드 요소를 명시합니다.

> `[규칙 ID: RULE-4.3.2 | 노드: engineering.code-comments | 경로: .agent-governance/engineering/code-comments.md]`

#### 4-3-3. 변경 시 영향도

`[변경 시 영향도]`에는 수정 시 함께 영향을 받는 위치를 명시합니다.

> `[규칙 ID: RULE-4.3.3 | 노드: engineering.code-comments | 경로: .agent-governance/engineering/code-comments.md]`

#### 4-3-4. 코드 행별 상세 설명

모든 코드에는 각 코드 줄이 무엇을 수행하는지 설명하는 상세 주석이 포함되어야 합니다. 기존 주석을 제거하거나 의미를 축소하지 않습니다.

> `[규칙 ID: RULE-4.3.4 | 노드: engineering.code-comments | 경로: .agent-governance/engineering/code-comments.md]`

### 4-4. 데이터 보존과 마이그레이션

모든 DB 스키마 조작 및 변경은 기존 데이터의 보존을 최우선으로 합니다.

#### 4-4-1. 파괴적 초기화 금지

스키마 변경을 이유로 기존 테이블을 함부로 `DROP`하거나 전체 초기화하지 않습니다.

> `[규칙 ID: RULE-4.4.1 | 주 노드: engineering.data-integrity | 보조 노드: core.kernel | 경로: .agent-governance/engineering/data-integrity.md]`

#### 4-4-2. 안전한 이전 절차

DB 구조 변경이나 데이터 보정이 필요하면 `ALTER TABLE`을 사용하거나, 데이터를 안전하게 이전하는 Migration 또는 직접 쿼리의 정확한 방법·순서·백업·검증·롤백 절차를 사전에 안내합니다.

> `[규칙 ID: RULE-4.4.2 | 노드: engineering.data-integrity | 경로: .agent-governance/engineering/data-integrity.md]`

### 4-5. 보안 및 환경 설정

시스템이 외부 인터넷에 공개될 수 있음을 전제로 모든 코드와 설정을 보호합니다.

#### 4-5-1. 민감 정보 하드코딩 금지

`app.secret_key`, DB 계정, API 토큰, 인증서 개인키 등 민감 정보를 소스코드에 평문으로 기록하거나 GitHub에 Push하지 않습니다. `.env` 등 환경변수 파일로 분리하고 `.gitignore`에서 제외합니다.

> `[규칙 ID: RULE-4.5.1 | 노드: engineering.security | 경로: .agent-governance/engineering/security.md]`

#### 4-5-2. 환경변수 Debug 제어

`debug=True`를 소스에 하드코딩하지 않으며 `debug=False`도 무조건 강제하지 않습니다. `.env`의 `FLASK_DEBUG` 값으로 Debug를 켜고 끌 수 있게 합니다.

> `[규칙 ID: RULE-4.5.2 | 노드: engineering.security | 경로: .agent-governance/engineering/security.md]`

#### 4-5-3. 세션·권한·입력 보호

`SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE` 등 쿠키 정책을 엄격히 적용하고 CSRF를 방어합니다. 외부 입력을 항상 불신하며 권한 검사는 서버 세션을 기준으로 수행합니다.

> `[규칙 ID: RULE-4.5.3 | 노드: engineering.security | 경로: .agent-governance/engineering/security.md]`

---

## 5. 실행 및 배포 방법

### 5-1. 미니서버 환경

#### 5-1-1. Windows 로컬 실행 금지

Windows PC는 소스 작성과 Git Push 용도로만 사용하며 애플리케이션 로컬 실행이나 동작 테스트를 수행하지 않습니다. 파일 조회와 정적 분석 같은 비파괴 검사는 가능합니다.

> `[규칙 ID: RULE-5.1.1 | 노드: operations.local-execution | 경로: .agent-governance/operations/local-execution.md]`

#### 5-1-2. Linux Lite 테스트와 구동

모든 실제 테스트와 구동은 미니서버 `192.168.0.166`에 SSH로 접속하여 수행합니다.

> `[규칙 ID: RULE-5.1.2 | 노드: operations.server-execution | 경로: .agent-governance/operations/server-execution.md]`

#### 5-1-3. Staging의 목적

Staging은 직접 구동하기 위한 환경이 아니라 정적 판단, 검토, 보고서 작성을 위한 안전한 베타 복사본입니다.

> `[규칙 ID: RULE-5.1.3 | 노드: operations.staging | 경로: .agent-governance/operations/staging.md]`

#### 5-1-4. 실행 스크립트 예시

```bash
# 최신 소스코드 동기화
git pull origin main

# 백엔드 서버 구동(기존 프로세스 확인과 안전한 종료 후 재시작)
python3 app.py

# 내부 네트워크 접속
# http://192.168.0.166:5000
```

> `[규칙 ID: RULE-5.1.4 | 노드: operations.server-execution | 경로: .agent-governance/operations/server-execution.md]`

---

## 6. 대화 기록 관리 규칙

사용자와 AI가 나눈 대화는 날짜별 Markdown 파일로 기록합니다.

> `[규칙 ID: RULE-6-PREAMBLE | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

### 6-1. 핵심 무결성 원칙

#### 6-1-1. 사용자·AI 원문 보존

사용자 메시지와 AI의 최종 응답은 요약·의역·수정 없이 Markdown 구조, 코드 블록, 링크를 포함한 원문 그대로 기록합니다.

> `[규칙 ID: RULE-6.1.1 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-1-2. 코드·설정·명령 보존

AI가 제안한 코드, 설정 예시, 실행 명령과 중간 안내도 실제 대화와 토씨 하나 다르지 않게 기록합니다.

> `[규칙 ID: RULE-6.1.2 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-1-3. 실제 AI 이름과 KST 헤더

현재 작업자는 다른 AI 이름을 무비판적으로 복사하지 않고 실제 모델명을 사용합니다. `## Codex YYYY-MM-DD HH:mm:ss.000`, `## Claude ...`, `## Gemini ...`처럼 `Asia/Seoul` 기준으로 기록합니다.

> `[규칙 ID: RULE-6.1.3 | 주 노드: workflow.multi-agent-handoff | 보조 노드: records.conversation-integrity | 경로: .agent-governance/workflow/multi-agent-handoff.md]`

#### 6-1-4. 비밀과 개인정보 치환

비밀번호, API 키, 인증서 개인키, 토큰, 개인정보는 기록하지 않고 `<비밀번호>` 같은 자리표시자로 치환합니다.

> `[규칙 ID: RULE-6.1.4 | 주 노드: records.conversation-integrity | 보조 노드: engineering.security | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-1-5. Append 기본값과 시간순 삽입

대화 파일은 기본적으로 끝에 이어쓰기하며 기존 대화를 수정·제거하지 않습니다. 저장하려는 대화 블록의 확인된 KST 시각이 이미 기록된 가장 최근 블록보다 같거나 늦으면 그대로 append합니다. 더 이르면 최근 일부의 대화 헤더를 먼저 비교하여 시간순 위치에 블록 전체를 삽입합니다. 이때 기존 블록의 원문과 헤더는 수정·삭제하지 않고 순서만 조정합니다. 최근 비교 범위에서 위치를 확인할 수 없으면 본문 전체를 다시 읽지 않고 이전 구간의 헤더와 위치 정보만 제한적으로 추가 탐색합니다. 누락이나 잘못된 기록이 발견되면 사용자에게 정정 또는 제거를 제안합니다.

> `[규칙 ID: RULE-6.1.5 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-1-6. Chat 저장 수단

대화 저장은 완전성과 원문 보존을 우선합니다. Antigravity에서 터미널을 사용해 온 이유는 IDE 내장 API가 대화를 지속적으로 누락하거나 환각을 포함해 잘못 기록한 경험 때문이며, 이 경험을 다른 플랫폼에 일률적으로 적용하지 않습니다. Codex·VS Code·Codex Extension 등 현재 플랫폼의 구조화된 편집 도구가 원문 완전성, Diff 확인, Undo를 신뢰성 있게 제공하면 그 도구로 최종 저장하는 것을 우선합니다. 해당 도구에서 누락이나 오기입이 확인되면 터미널 저장의 필요성과 절차를 사용자에게 먼저 보고하고 승인을 받은 뒤 Chat 기록 예외를 적용합니다. 이 예외는 일반 소스·리소스 편집으로 자동 확장하지 않습니다.

> `[규칙 ID: RULE-6.1.6 | 추가 정책 ID: HUMAN-6.1.6-PLATFORM | 주 노드: records.conversation-storage | 보조 노드: tools.conversation-exception | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-1-7. 타임스탬프 검증과 정렬 기준

대화 블록의 KST 밀리초 헤더는 실제 사용자 발언 또는 AI 응답의 확인된 발생 시각을 사용합니다. 로그에 `Z`가 있어도 실제로 이미 KST일 수 있으므로 현재 KST와 비교하여 검증한 뒤 변환하고, 기계적으로 9시간을 더하지 않습니다. 저장 시에는 이 헤더 시각을 시간순 삽입의 기준으로 사용합니다. 실제 시각을 플랫폼에서 확인할 수 없으면 임의 시각을 만들지 않고 그 제한을 보고합니다. 다만 확인할 수 있는데도 불구하고 할 수 없다고 거짓말을 해서는 안됩니다.

> `[규칙 ID: RULE-6.1.7 | 노드: records.timestamps | 경로: .agent-governance/records/timestamps.md]`

#### 6-1-8. Windows UTF-8 보호

PowerShell Chat append 시 한글을 명령 문자열에 직접 하드코딩하지 않습니다. IDE 편집 API로 UTF-8 중간 파일을 만든 뒤 `Get-Content -Encoding UTF8`로 읽어 append합니다.

> `[규칙 ID: RULE-6.1.8 | 노드: records.encoding | 경로: .agent-governance/records/encoding.md]`

#### 6-1-9. PowerShell Here-String 보호

Markdown을 PowerShell로 기록할 때 큰따옴표 확장 Here-String `@"..."@`을 사용하지 않습니다. 백틱과 제어 문자 변형을 막기 위해 작은따옴표 리터럴 Here-String `@'...'@`을 사용합니다.

> `[규칙 ID: RULE-6.1.9 | 노드: records.encoding | 경로: .agent-governance/records/encoding.md]`

#### 6-1-10. scratch 자동 정리

##### 6-1-10-1. FIFO 정리

`scratch/`의 임시 파일이 10개를 초과하면 다음 턴 시작 시 생성 시각이 오래된 파일부터 순서대로 정리합니다.

> `[규칙 ID: RULE-6.1.10.1 | 노드: records.scratch-retention | 경로: .agent-governance/records/scratch-retention.md]`

##### 6-1-10-2. 한 턴 내 유예

한 턴의 작업 연속성을 위해 파일 수가 일시적으로 10개를 초과하면 즉시 삭제하지 않고 다음 턴 시작까지 유예합니다.

> `[규칙 ID: RULE-6.1.10.2 | 노드: records.scratch-retention | 경로: .agent-governance/records/scratch-retention.md]`

##### 6-1-10-3. 영구 문서와의 구분

`scratch/` 임시 파일은 `Chat/` 및 `Plans/` 영구 문서와 무관하며 문서 생명주기 보존 대상이 아닙니다.

> `[규칙 ID: RULE-6.1.10.3 | 노드: records.scratch-retention | 경로: .agent-governance/records/scratch-retention.md]`

### 6-2. 자동 기록 파이프라인

#### 6-2-1. 승인 없는 기록

대화 기록 추가는 별도의 사용자 승인 없이 진행합니다.

> `[규칙 ID: RULE-6.2.1 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-2. 중간 안내 포함과 저장 시점

사용자에게 실제 전달한 중간 안내는 최종 저장 시 원문과 동일하게 함께 기록합니다. 긴 작업의 모든 내부 추론·도구 호출·세부 과정마다 즉시 Chat을 갱신하도록 강제하지 않으며, 사용자에게 전달하지 않은 내부 작업 과정은 기록 대상이 아닙니다.

> `[규칙 ID: RULE-6.2.2 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-3. 기록 위치

대화 기록 위치는 `Chat/YYYY/MM/DD.md`입니다.

> `[규칙 ID: RULE-6.2.3 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-4. 현재 날짜 확인

AI는 최종 응답 전에 현재 날짜를 확인합니다.

> `[규칙 ID: RULE-6.2.4 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-5. 기존 날짜 파일과 최근 헤더 비교

현재 날짜 파일이 있으면 최근 32개 대화 헤더만 먼저 읽어 저장 블록의 시각과 비교합니다. 저장 시각이 마지막 헤더보다 같거나 늦으면 파일 끝에 원문을 이어 기록합니다. 더 이르면 해당 최근 범위의 시간순 위치에 블록 전체를 삽입합니다. 대상 시각이 그 범위보다 더 이르면 본문을 추가로 읽지 않고 이전 구간의 헤더와 위치 정보만 제한적으로 탐색하여 위치를 결정합니다.

> `[규칙 ID: RULE-6.2.5 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-6. 날짜 파일 생성

현재 날짜 파일이 없으면 연도·월 폴더와 일자 파일을 생성합니다.

> `[규칙 ID: RULE-6.2.6 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-7. 날짜 변경

날짜가 바뀌면 이전 날짜 파일이 아니라 새 날짜 파일에 기록합니다.

> `[규칙 ID: RULE-6.2.7 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-2-8. 같은 날짜의 대화와 안정적 순서

같은 날짜의 대화는 같은 일자 파일에 기록합니다. append를 기본값으로 하되, 확인된 시각이 더 이른 블록은 시간순 위치에 삽입합니다. 같은 시각의 블록은 기존 동률 블록 뒤에 기록하여 이미 확정된 순서를 유지합니다. 삽입 직전 최근 헤더가 바뀌었으면 오래된 판단으로 덮어쓰지 않고 최근 범위를 다시 확인합니다.

> `[규칙 ID: RULE-6.2.8 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

### 6-3. 기록 포맷과 가독성

#### 6-3-1. 사용자 헤더

사용자 항목은 `## 사용자 YYYY-MM-DD HH:mm:ss.000` 형식을 사용합니다.

> `[규칙 ID: RULE-6.3.1 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-3-2. 변경과 제안 구분

실제 프로젝트나 서버에 적용된 변경과 사용자가 검토·실행해야 하는 제안을 명확히 구분합니다.

> `[규칙 ID: RULE-6.3.2 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-3-3. 제안의 실행 조건

제안 단계 코드에는 실행 환경, 대상 파일 또는 서버, 선행 조건을 함께 기록합니다.

> `[규칙 ID: RULE-6.3.3 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

#### 6-3-4. 코드 블록

제안 내용은 Markdown 코드 블록으로 원문을 보존하고 `bash`, `python`, `caddyfile` 같은 언어 또는 형식을 지정합니다.

> `[규칙 ID: RULE-6.3.4 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`

### 6-4. 서식 규칙과 예외

#### 6-4-1. 연·월 폴더

연도와 월을 하위 폴더로 나누며 월은 두 자리 숫자를 사용합니다. 예: `07`.

> `[규칙 ID: RULE-6.4.1 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-4-2. 일자 파일명

일자별 파일은 두 자리 숫자를 사용합니다. 예: `23.md`.

> `[규칙 ID: RULE-6.4.2 | 노드: records.conversation-storage | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-4-3. 삭제·덮어쓰기 재확인

사용자가 대화 삭제나 덮어쓰기를 요청해도 즉시 실행하지 않고 한 번 더 실행 여부를 확인하여 최종 승인을 받습니다.

> `[규칙 ID: RULE-6.4.3 | 주 노드: records.conversation-storage | 보조 노드: core.kernel | 경로: .agent-governance/records/conversation-storage.md]`

#### 6-4-4. 과거 미확인 시각

실제 시각을 보유하지 않은 기존 항목은 임의 시각을 만들지 않고 확인 기준 시각과 `이전에 기록됨`을 사용합니다. 이 예외는 규칙 확정 이전의 과거 기록에만 적용하며 새로운 대화에는 정확한 시각을 사용합니다.

> `[규칙 ID: RULE-6.4.4 | 노드: records.timestamps | 경로: .agent-governance/records/timestamps.md]`

---

## 7. 문서 생명주기 및 개발 파이프라인

AI는 기능 추가와 코드 수정 시 아래 문서·개발 파이프라인을 준수합니다.

> `[규칙 ID: RULE-7-PREAMBLE | 노드: workflow.plans | 경로: .agent-governance/workflow/plans.md]`

### 7-1. 기획 및 대기

#### 7-1-1. 제안 등록

신규 기능 제안이나 아이디어는 원본 보존 문서 `PROPOSALS.md`와 미구현 추적 문서 `UNIMPLEMENTED_PROPOSALS.md`에 함께 기록합니다.

> `[규칙 ID: RULE-7.1.1 | 노드: workflow.proposals-roadmap | 경로: .agent-governance/workflow/proposals-roadmap.md]`

#### 7-1-2. 로드맵 등록

채택·승인된 개발 항목은 이력 문서 `ROADMAP.md`와 작업 대기열 `UNIMPLEMENTED_ROADMAP.md`에 함께 등록합니다.

> `[규칙 ID: RULE-7.1.2 | 노드: workflow.proposals-roadmap | 경로: .agent-governance/workflow/proposals-roadmap.md]`

### 7-2. 영구 보존 기획

#### 7-2-1. 작업 전 Plan

기능 추가, 버그 수정, 아키텍처 개편 전에 Plan을 작성합니다.

> `[규칙 ID: RULE-7.2.1 | 노드: workflow.plans | 경로: .agent-governance/workflow/plans.md]`

#### 7-2-2. Plans 영구 기록

모든 기획 문서는 `Plans/YYYY-MM-DD_XXX_Plan.md` 형식으로 `Plans/`에 영구 기록하고 조율합니다.

> `[규칙 ID: RULE-7.2.2 | 노드: workflow.plans | 경로: .agent-governance/workflow/plans.md]`

### 7-3. 임시 검증 및 병합

#### 7-3-1. 운영 수정 전 Staging

운영 코드(`templates/`, `app.py` 등)를 수정하기 전에 `Staging/`을 안전망으로 사용합니다.

> `[규칙 ID: RULE-7.3.1 | 주 노드: operations.staging | 보조 노드: workflow.staging-merge | 경로: .agent-governance/operations/staging.md]`

#### 7-3-2. 모의 결과물 검증

`Staging/`에 모의 소스코드와 검토 산출물을 작성하여 검증합니다. Staging 자체를 Windows에서 구동하지 않습니다.

> `[규칙 ID: RULE-7.3.2 | 주 노드: operations.staging | 보조 노드: workflow.staging-merge | 경로: .agent-governance/operations/staging.md]`

#### 7-3-3. 승인·병합 후 정리

사용자가 검증 결과를 승인하고 운영 병합이 완료되면 Staging 임시 파일을 정리하여 빈 상태로 유지합니다.

> `[규칙 ID: RULE-7.3.3 | 노드: workflow.staging-merge | 경로: .agent-governance/workflow/staging-merge.md]`

#### 7-3-4. Staging 계획서 아카이빙

`Staging_PLAN.md`는 즉시 삭제하지 않습니다. 먼저 `Plans/YYYY-MM-DD_작업내용_Plan.md`로 이관하여 영구 보존한 뒤 삭제합니다.

> `[규칙 ID: RULE-7.3.4 | 노드: workflow.staging-merge | 경로: .agent-governance/workflow/staging-merge.md]`

### 7-4. 완료와 이력 보존

#### 7-4-1. 원본 제안·로드맵 보존

개발 완료 후에도 `PROPOSALS.md`와 `ROADMAP.md`의 원본 항목을 삭제하지 않습니다.

> `[규칙 ID: RULE-7.4.1 | 노드: workflow.completion-history | 경로: .agent-governance/workflow/completion-history.md]`

#### 7-4-2. 완료 상태와 미구현 목록

원본 항목 상태를 `[개발 완료 (FEATURES.md 이관)]` 등으로 갱신합니다. 완료된 항목은 `UNIMPLEMENTED_PROPOSALS.md`와 `UNIMPLEMENTED_ROADMAP.md`에서 제거하여 대기열을 최신화합니다.

> `[규칙 ID: RULE-7.4.2 | 노드: workflow.completion-history | 경로: .agent-governance/workflow/completion-history.md]`

#### 7-4-3. FEATURES 기록

최종 완성된 상세 기능 명세를 `FEATURES.md`에 추가합니다.

> `[규칙 ID: RULE-7.4.3 | 노드: workflow.completion-history | 경로: .agent-governance/workflow/completion-history.md]`

### 7-5. 다중 AI 컨텍스트와 자아 식별

#### 7-5-1. AI 교차 투입

사용자는 기획·검토 모델과 코딩·실행 모델 등 다양한 플랫폼의 AI를 교차 투입할 수 있습니다.

> `[규칙 ID: RULE-7.5.1 | 노드: workflow.multi-agent-handoff | 경로: .agent-governance/workflow/multi-agent-handoff.md]`

#### 7-5-2. 현재 역할 인지

AI는 자신이 기획·검토를 수행하는지 코딩·실행을 수행하는지 식별합니다. 역할이 불명확하고 결과를 바꿀 수 있으면 사용자에게 확인합니다.

> `[규칙 ID: RULE-7.5.2 | 노드: workflow.multi-agent-handoff | 경로: .agent-governance/workflow/multi-agent-handoff.md]`

#### 7-5-3. 승인된 맥락 승계

새 AI는 직전 AI의 사용자 승인 계획(`Plans/`, `Staging_PLAN.md`)과 `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md` 등 관련 문서의 방향성을 읽고 존중합니다.

> `[규칙 ID: RULE-7.5.3 | 노드: workflow.multi-agent-handoff | 경로: .agent-governance/workflow/multi-agent-handoff.md]`

#### 7-5-4. 실제 모델명 사용

대화 기록 시 이전 AI의 이름을 복사하지 않고 현재 작업 중인 실제 모델명을 헤더에 사용합니다. 이 항목은 6-1-3과 6-3-1을 함께 참조합니다.

> `[규칙 ID: RULE-7.5.4 | 노드: workflow.multi-agent-handoff | 경로: .agent-governance/workflow/multi-agent-handoff.md]`

---

## 8. AI 시스템 도구 운용 및 제어

AI가 파일 시스템과 터미널에 접근할 때 시스템 안전과 사용자 통제권을 보장합니다.

> `[규칙 ID: RULE-8-PREAMBLE | 노드: tools.read-execute | 경로: .agent-governance/tools/read-execute.md]`

### 8-0. Chat 기록 우선 예외

제8조의 일반 도구 규칙은 `Chat/` 대화 저장에는 적용하지 않습니다. 대화 저장은 제6조와 `tools.conversation-exception`을 우선합니다. 이 예외를 다른 파일 쓰기로 확장하지 않습니다.

> `[규칙 ID: RULE-8.0 | 노드: tools.conversation-exception | 경로: .agent-governance/tools/conversation-exception.md]`

### 8-1. 터미널 읽기·실행 원칙

#### 8-1-1. 허용 목적

PowerShell, Bash 등 터미널은 파일 내용 조회, 디렉터리 탐색, 서버 구동, 상태 모니터링 등 상태를 읽거나 승인된 실행을 수행하는 용도로 사용합니다.

> `[규칙 ID: RULE-8.1.1 | 노드: tools.read-execute | 경로: .agent-governance/tools/read-execute.md]`

#### 8-1-2. 일반 파일 터미널 쓰기 제한

`Add-Content`, `echo`, 리디렉션, `cat >` 같은 터미널 명령으로 일반 소스·리소스를 생성·수정·덮어쓰는 행위는 기본적으로 금지합니다. Chat 기록에는 8-0을 적용합니다. 일반 파일은 구조화된 편집 도구로 조치할 수 없고 해당 플랫폼에서 터미널 변경의 Diff와 신뢰 가능한 Undo 또는 동등한 복구가 실제로 검증된 경우에만 8-2-2의 사전 보고·명시 승인 절차에 따라 조건부 대안으로 제시할 수 있습니다.

> `[규칙 ID: RULE-8.1.2 | 추가 정책 ID: HUMAN-8-TERMINAL-FALLBACK | 주 노드: tools.read-execute | 보조 노드: tools.file-editing | 경로: .agent-governance/tools/read-execute.md]`

### 8-2. 구조화된 파일 편집

#### 8-2-1. 편집 API 사용

Chat 기록 외의 소스 코드, 문서, 리소스 쓰기는 IDE 또는 에이전트의 구조화된 파일 편집 API를 사용합니다.

> `[규칙 ID: RULE-8.2.1 | 노드: tools.file-editing | 경로: .agent-governance/tools/file-editing.md]`

#### 8-2-2. Diff와 Undo

파일 변경은 사용자가 Diff를 확인하고 Undo할 수 있어야 합니다. 구조화된 편집 도구로 조치할 수 없더라도 터미널 쓰기로 즉시 우회하지 않습니다. 터미널 변경이 실제로 Diff와 신뢰 가능한 Undo 또는 동등한 복구를 제공하는지 검증하고, 검증된 경우에만 정확한 대상·방법·영향·복구 절차를 사용자에게 대안으로 제시하여 명시 승인을 받은 뒤 수행합니다. 복구 가능성을 검증할 수 없으면 터미널 쓰기는 금지하고 기능 제한을 보고합니다.

> `[규칙 ID: RULE-8.2.2 | 추가 정책 ID: HUMAN-8-TERMINAL-FALLBACK | 노드: tools.file-editing | 경로: .agent-governance/tools/file-editing.md]`

---

## 9. AI 공통 행동 및 승인 제어

### 9-1. 작업 시작 전 규칙 확인

AI는 매 행위 전 안전 커널을 확인하고, 각 작업을 시작하기 전에 manifest와 router를 통해 적용 규칙 노드를 읽습니다.

> `[원본 ID: ENTRY-GEMINI.1 | 주 노드: core.precedence | 보조 노드: core.kernel | 경로: .agent-governance/core/precedence.md]`

### 9-2. 행위 직전 적합성 판단

AI는 실제 행위 직전에 선택된 규칙이 요청과 행위에 어떻게 적용되는지 판단합니다.

> `[원본 ID: ENTRY-GEMINI.2 | 노드: core.precedence | 경로: .agent-governance/core/precedence.md]`

### 9-3. 규칙 충돌

사용자 요청이 활성 규칙과 충돌하면 작업을 실행하지 않습니다. 충돌 규칙 ID, 요청과의 충돌 지점, 실행 영향, 필요한 사용자 결정을 아티팩트로 보고하고 재지시를 기다립니다.

> `[원본 ID: ENTRY-GEMINI.3 | 주 노드: core.task-modes | 보조 노드: core.precedence | 경로: .agent-governance/core/task-modes.md]`

### 9-4. 질문과 승인 경계

사용자가 질문하면 답변부터 합니다. 질문·제안·검토·계획을 승인 없는 구현으로 확대하지 않습니다. 답변 후 처리 방안을 검토·보고하고 사용자가 실제 작업을 승인하면 구현합니다.

> `[원본 ID: ENTRY-GEMINI.4 | 노드: core.task-modes | 경로: .agent-governance/core/task-modes.md]`

### 9-5. 순차 Task

실제 작업을 시작할 때 Task를 만들고 순차적으로 수행합니다.

> `[원본 ID: ENTRY-GEMINI.5 | 주 노드: validation.orchestration | 보조 노드: core.task-modes | 경로: .agent-governance/validation/orchestration.md]`

### 9-6. 객관적 문구

모든 대화는 과장되거나 거창한 표현보다 객관적이고 명확한 문구를 사용합니다.

> `[원본 ID: ENTRY-GEMINI.6 | 노드: core.kernel | 경로: .agent-governance/core/kernel.md]`

#### 9-6-1. 긍정·부정 판단의 근거

판단에는 실제로 존재하는 긍정적 결과와 부정적 결과를 포함합니다. 어느 한쪽이 없다면 억지로 만들지 않고 없다는 근거를 그대로 표현하며, 실제로 존재하는 요소를 누락하지 않습니다.

> `[원본 ID: ENTRY-GEMINI.6.1 | 주 노드: validation.kernel | 보조 노드: core.kernel | 경로: .agent-governance/validation/kernel.md]`

### 9-7. 승인 재촉 금지

사용자가 충분하다고 판단하여 승인할 때까지 승인을 재촉하지 않습니다.

> `[원본 ID: ENTRY-GEMINI.7 | 노드: core.kernel | 경로: .agent-governance/core/kernel.md]`

### 9-8. 검증 방법론 사용

검증이나 검토에서는 제10장의 기본 원칙과 1~8단계 검증 체인을 순서대로 모두 적용합니다.

> `[원본 ID: ENTRY-GEMINI.8 | 노드: validation.orchestration | 경로: .agent-governance/validation/orchestration.md]`

---

## 10. 다차원 심층 자체 검증 방법론

신규 제안이나 구현 계획을 수립한 직후, 실제 코드를 작성하거나 운영 환경에 병합하기 전에 이 자체 검증 표준 절차를 적용합니다.

> `[검증 ID: VAL-PREAMBLE | 노드: validation.kernel | 경로: .agent-governance/validation/kernel.md]`

### 10-1. 기본 원칙

#### 10-1-1. 순차 검증

`task.md` 아티팩트 또는 동등한 Task 목록을 먼저 만들고 1단계부터 8단계까지 순서대로 점검합니다. 각 단계 결과를 종합 검증 보고서에 누적합니다.

> `[검증 ID: VAL-CORE.1 | 노드: validation.orchestration | 경로: .agent-governance/validation/orchestration.md]`

#### 10-1-2. 객관적·건조한 판단

긍정적·부정적 결과를 억지로 만들지 않고 실제 사실을 객관적이고 명확하게 기록합니다.

> `[검증 ID: VAL-CORE.2 | 주 노드: validation.kernel | 보조 노드: core.kernel | 경로: .agent-governance/validation/kernel.md]`

#### 10-1-3. 긍정·부정 다면 교차 검증

실제로 존재하는 장점과 단점·위험을 독립적으로 도출하고 비교합니다. 어느 한쪽이 없으면 없다는 근거를 남기되 존재하는 요소를 누락하지 않습니다.

> `[검증 ID: VAL-CORE.3 | 주 노드: validation.kernel | 보조 노드: core.kernel | 경로: .agent-governance/validation/kernel.md]`

#### 10-1-4. 자율적 위협 발굴

각 단계의 관찰점은 최소 기준입니다. 문서에 적힌 항목만 체크하고 끝내지 않으며 작업 맥락의 숨은 엣지 케이스와 취약점을 스스로 확장하여 발굴합니다.

> `[검증 ID: VAL-CORE.4 | 주 노드: validation.kernel | 보조 노드: core.kernel | 경로: .agent-governance/validation/kernel.md]`

### 10-2. 1단계: 거버넌스 준수성

계획과 변경이 활성 거버넌스 규칙을 위반하지 않는지 심문합니다.

> `[검증 ID: VAL-PHASE.1.0 | 노드: validation.phase.01-governance | 경로: .agent-governance/validation/phases/01-governance.md]`

#### 10-2-1. 프론트엔드·백엔드 분리

프론트엔드와 백엔드의 책임 및 로직 분리가 유지되는지 확인합니다.

> `[검증 ID: VAL-PHASE.1.1 | 노드: validation.phase.01-governance | 경로: .agent-governance/validation/phases/01-governance.md]`

#### 10-2-2. 스키마와 데이터 보존

DB 스키마 변경이 파괴적이지 않고 기존 데이터 보존 원칙을 명시하는지 확인합니다.

> `[검증 ID: VAL-PHASE.1.2 | 주 노드: validation.phase.01-governance | 보조 노드: engineering.data-integrity | 경로: .agent-governance/validation/phases/01-governance.md]`

#### 10-2-3. 격리 환경

실제 구현과 검증이 운영 환경보다 지정된 Staging 안전망을 먼저 사용하는지 확인합니다.

> `[검증 ID: VAL-PHASE.1.3 | 주 노드: validation.phase.01-governance | 보조 노드: operations.staging | 경로: .agent-governance/validation/phases/01-governance.md]`

#### 10-2-4. 커스텀 규칙

프레임워크 기본 설정만 신뢰하지 않고 프로젝트 고유 규칙을 수용하는지 확인합니다.

> `[검증 ID: VAL-PHASE.1.4 | 노드: validation.phase.01-governance | 경로: .agent-governance/validation/phases/01-governance.md]`

#### 10-2-5. 외부 라이브러리

외부 라이브러리가 인가되었고 무의존 대안이 함께 검토되었는지 확인합니다.

> `[검증 ID: VAL-PHASE.1.5 | 노드: validation.phase.01-governance | 경로: .agent-governance/validation/phases/01-governance.md]`

### 10-3. 2단계: 사용자 의도 달성도

사용자의 최초 요청과 현재 계획·결과 사이의 간극을 대조합니다.

> `[검증 ID: VAL-PHASE.2.0 | 노드: validation.phase.02-user-intent | 경로: .agent-governance/validation/phases/02-user-intent.md]`

#### 10-3-1. 고유 요구사항

시스템 고유 요구가 데이터 모델과 설계에 왜곡 없이 반영되었는지 확인합니다.

> `[검증 ID: VAL-PHASE.2.1 | 노드: validation.phase.02-user-intent | 경로: .agent-governance/validation/phases/02-user-intent.md]`

#### 10-3-2. 기존 워크플로우 통합

기존 거버넌스와 문서 워크플로우가 계획에 통합되었는지 확인합니다.

> `[검증 ID: VAL-PHASE.2.2 | 노드: validation.phase.02-user-intent | 경로: .agent-governance/validation/phases/02-user-intent.md]`

#### 10-3-3. 사용자 제약

사용자가 제시한 제약 중 묵인되거나 누락된 항목이 없는지 확인합니다.

> `[검증 ID: VAL-PHASE.2.3 | 노드: validation.phase.02-user-intent | 경로: .agent-governance/validation/phases/02-user-intent.md]`

#### 10-3-4. UI·UX 동선

사용자가 기대하는 UI·UX 동선이 설계에 반영되었는지 확인합니다.

> `[검증 ID: VAL-PHASE.2.4 | 주 노드: validation.phase.02-user-intent | 보조 노드: engineering.frontend-responsive | 경로: .agent-governance/validation/phases/02-user-intent.md]`

#### 10-3-5. 향후 확장

단기 해결뿐 아니라 향후 확장을 고려한 유연한 구조인지 확인합니다.

> `[검증 ID: VAL-PHASE.2.5 | 노드: validation.phase.02-user-intent | 경로: .agent-governance/validation/phases/02-user-intent.md]`

### 10-4. 3단계: 논리적 구동 가능성

Windows 로컬 구동 금지 제약 아래 정적 설계와 허용된 검사로 병목을 분석합니다.

> `[검증 ID: VAL-PHASE.3.0 | 주 노드: validation.phase.03-static-logic | 보조 노드: operations.local-execution | 경로: .agent-governance/validation/phases/03-static-logic.md]`

#### 10-4-1. 데이터 증가

데이터 폭증 시 전체 스캔, 락, 비효율 쿼리 문제가 발생하는지 확인합니다.

> `[검증 ID: VAL-PHASE.3.1 | 노드: validation.phase.03-static-logic | 경로: .agent-governance/validation/phases/03-static-logic.md]`

#### 10-4-2. 반복 호출과 메모리

프론트엔드 반복 호출이나 클라이언트 메모리 누수가 가능한지 확인합니다.

> `[검증 ID: VAL-PHASE.3.2 | 노드: validation.phase.03-static-logic | 경로: .agent-governance/validation/phases/03-static-logic.md]`

#### 10-4-3. 트랜잭션 예외

트랜잭션 예외 시 데이터 무결성과 롤백이 보장되는지 확인합니다.

> `[검증 ID: VAL-PHASE.3.3 | 주 노드: validation.phase.03-static-logic | 보조 노드: engineering.data-integrity | 경로: .agent-governance/validation/phases/03-static-logic.md]`

#### 10-4-4. 비동기 경합

비동기 흐름의 Race Condition 또는 Deadlock 가능성을 확인합니다.

> `[검증 ID: VAL-PHASE.3.4 | 노드: validation.phase.03-static-logic | 경로: .agent-governance/validation/phases/03-static-logic.md]`

#### 10-4-5. 캐시 정합성

캐시 만료와 정합성 파괴 가능성을 확인합니다.

> `[검증 ID: VAL-PHASE.3.5 | 노드: validation.phase.03-static-logic | 경로: .agent-governance/validation/phases/03-static-logic.md]`

### 10-5. 4단계: 운영 병합 영향

격리 결과물이 운영 루트에 병합될 때의 사이드이펙트를 평가합니다.

> `[검증 ID: VAL-PHASE.4.0 | 주 노드: validation.phase.04-production-impact | 보조 노드: workflow.staging-merge | 경로: .agent-governance/validation/phases/04-production-impact.md]`

#### 10-5-1. 라우트 충돌

신규 라우트 주소와 기존 우선순위가 충돌하는지 확인합니다.

> `[검증 ID: VAL-PHASE.4.1 | 노드: validation.phase.04-production-impact | 경로: .agent-governance/validation/phases/04-production-impact.md]`

#### 10-5-2. 권한 제어

신규 API와 기능이 기존 권한 제어 밖으로 노출되는지 확인합니다.

> `[검증 ID: VAL-PHASE.4.2 | 주 노드: validation.phase.04-production-impact | 보조 노드: engineering.security | 경로: .agent-governance/validation/phases/04-production-impact.md]`

#### 10-5-3. 레거시 침범

기존 비즈니스 코드를 침범하지 않고 확장되는지 확인합니다.

> `[검증 ID: VAL-PHASE.4.3 | 노드: validation.phase.04-production-impact | 경로: .agent-governance/validation/phases/04-production-impact.md]`

#### 10-5-4. 글로벌 상태

전역 변수나 글로벌 상태 변경이 다른 기능에 파급되는지 확인합니다.

> `[검증 ID: VAL-PHASE.4.4 | 노드: validation.phase.04-production-impact | 경로: .agent-governance/validation/phases/04-production-impact.md]`

#### 10-5-5. Breaking Change

기존 테스트와 동작을 깨는 변경이 포함되는지 확인합니다.

> `[검증 ID: VAL-PHASE.4.5 | 노드: validation.phase.04-production-impact | 경로: .agent-governance/validation/phases/04-production-impact.md]`

### 10-6. 5단계: 보안 및 예외 엣지 케이스

악의적 입력과 극단 상황에서 방어가 유지되는지 검사합니다.

> `[검증 ID: VAL-PHASE.5.0 | 노드: validation.phase.05-security-edge | 경로: .agent-governance/validation/phases/05-security-edge.md]`

#### 10-6-1. 주요 웹 취약점

SQL Injection, XSS, CSRF 방어와 파라미터 검증을 확인합니다.

> `[검증 ID: VAL-PHASE.5.1 | 주 노드: validation.phase.05-security-edge | 보조 노드: engineering.security | 경로: .agent-governance/validation/phases/05-security-edge.md]`

#### 10-6-2. 비정상 값과 타입

Null, Undefined, 빈 문자열, 배열 등 비정상 입력에서 안전하게 실패하는지 확인합니다.

> `[검증 ID: VAL-PHASE.5.2 | 주 노드: validation.phase.05-security-edge | 보조 노드: engineering.security | 경로: .agent-governance/validation/phases/05-security-edge.md]`

#### 10-6-3. 평문 노출

민감 데이터와 통신이 평문으로 노출되는지 확인합니다.

> `[검증 ID: VAL-PHASE.5.3 | 주 노드: validation.phase.05-security-edge | 보조 노드: engineering.security | 경로: .agent-governance/validation/phases/05-security-edge.md]`

#### 10-6-4. 내부 정보 노출

Alert나 500 응답에 스택 트레이스와 내부 구조가 노출되는지 확인합니다.

> `[검증 ID: VAL-PHASE.5.4 | 주 노드: validation.phase.05-security-edge | 보조 노드: engineering.security | 경로: .agent-governance/validation/phases/05-security-edge.md]`

### 10-7. 6단계: 롤백 및 역방향 파급

병합 직후 치명적인 오류가 발견된 상황에서 안전한 복귀가 가능한지 검사합니다.

> `[검증 ID: VAL-PHASE.6.0 | 노드: validation.phase.06-rollback | 경로: .agent-governance/validation/phases/06-rollback.md]`

#### 10-7-1. Up·Down 마이그레이션

DB Up 변경뿐 아니라 Down 또는 동등한 복구 절차가 가능한지 확인합니다.

> `[검증 ID: VAL-PHASE.6.1 | 주 노드: validation.phase.06-rollback | 보조 노드: engineering.data-integrity | 경로: .agent-governance/validation/phases/06-rollback.md]`

#### 10-7-2. 신규 데이터 의존성

코드 롤백 후 신규 데이터 때문에 시스템 기동이 실패하는지 확인합니다.

> `[검증 ID: VAL-PHASE.6.2 | 주 노드: validation.phase.06-rollback | 보조 노드: engineering.data-integrity | 경로: .agent-governance/validation/phases/06-rollback.md]`

#### 10-7-3. 캐시·세션 잔여물

캐시, 세션, 클라이언트 저장소의 잔여 데이터가 롤백 후 오류를 만드는지 확인합니다.

> `[검증 ID: VAL-PHASE.6.3 | 노드: validation.phase.06-rollback | 경로: .agent-governance/validation/phases/06-rollback.md]`

#### 10-7-4. 환경변수와 부분 롤백

환경변수·인프라와 코드가 결합되어 부분 롤백 충돌이 생기는지 확인합니다.

> `[검증 ID: VAL-PHASE.6.4 | 노드: validation.phase.06-rollback | 경로: .agent-governance/validation/phases/06-rollback.md]`

### 10-8. 7단계: 휴먼 에러 및 UX 방어

사용자가 잘못 조작해도 복구 가능하고 이해 가능한 흐름인지 검사합니다.

> `[검증 ID: VAL-PHASE.7.0 | 노드: validation.phase.07-human-error | 경로: .agent-governance/validation/phases/07-human-error.md]`

#### 10-8-1. 잘못된 동선의 피드백

잘못된 동선에 비활성화 사유와 명확한 오류 피드백이 제공되는지 확인합니다.

> `[검증 ID: VAL-PHASE.7.1 | 주 노드: validation.phase.07-human-error | 보조 노드: engineering.frontend-responsive | 경로: .agent-governance/validation/phases/07-human-error.md]`

#### 10-8-2. 데드엔드 UI

다음 단계로 갈 수 없는 데드엔드 UI가 있는지 확인합니다.

> `[검증 ID: VAL-PHASE.7.2 | 주 노드: validation.phase.07-human-error | 보조 노드: engineering.frontend-responsive | 경로: .agent-governance/validation/phases/07-human-error.md]`

#### 10-8-3. 파괴적 액션 이중 확인

삭제·덮어쓰기 등 파괴적 액션 전에 사용자 이중 확인이 있는지 확인합니다.

> `[검증 ID: VAL-PHASE.7.3 | 노드: validation.phase.07-human-error | 경로: .agent-governance/validation/phases/07-human-error.md]`

#### 10-8-4. 프론트엔드 입력 검증

필수값 누락과 범위 오류를 프론트엔드에서 1차 검증하는지 확인합니다.

> `[검증 ID: VAL-PHASE.7.4 | 주 노드: validation.phase.07-human-error | 보조 노드: engineering.frontend-responsive | 경로: .agent-governance/validation/phases/07-human-error.md]`

### 10-9. 8단계: AI 작업자 메타 거버넌스

AI가 목적 달성을 이유로 불필요한 행위를 수행하거나 저장소와 컨텍스트를 오염시키지 않았는지 검사합니다.

> `[검증 ID: VAL-PHASE.8.0 | 노드: validation.phase.08-ai-meta | 경로: .agent-governance/validation/phases/08-ai-meta.md]`

#### 10-9-1. scratch 정리

분석용 scratch 파일을 보존 정책에 맞게 정리했는지 확인합니다.

> `[검증 ID: VAL-PHASE.8.1 | 주 노드: validation.phase.08-ai-meta | 보조 노드: records.scratch-retention | 경로: .agent-governance/validation/phases/08-ai-meta.md]`

#### 10-9-2. 환각과 컨텍스트 오염

로그와 아티팩트에 환각, 억지 주장, 무관한 맥락을 넣지 않았는지 확인합니다.

> `[검증 ID: VAL-PHASE.8.2 | 주 노드: validation.phase.08-ai-meta | 보조 노드: records.conversation-integrity | 경로: .agent-governance/validation/phases/08-ai-meta.md]`

#### 10-9-3. 통제 규정 우회 금지

Rule, Validation, 진입점 통제를 표현 변경이나 우회로 회피하지 않았는지 확인합니다.

> `[검증 ID: VAL-PHASE.8.3 | 주 노드: validation.phase.08-ai-meta | 보조 노드: workflow.multi-agent-handoff | 경로: .agent-governance/validation/phases/08-ai-meta.md]`

#### 10-9-4. 승인 재촉과 객관적 톤

승인을 재촉하지 않고 객관적이고 명확한 문구를 사용했는지 확인합니다.

> `[검증 ID: VAL-PHASE.8.4 | 주 노드: validation.phase.08-ai-meta | 보조 노드: core.kernel | 경로: .agent-governance/validation/phases/08-ai-meta.md]`

---

## 11. 사용자용 Rule과 AI용 노드의 동기화

### 11-1. 대상별 역할

`Rule.md`는 사용자가 전체 정책을 읽고 변경 의도를 판단하는 사용자용 의미 기준입니다. `.agent-governance/` 노드는 AI가 작업별로 읽는 기계 실행용 투영본입니다.

> `[통합 정책 ID: HUMAN-11.1 | 노드: governance.human-reference | 경로: .agent-governance/governance/human-reference.md]`

### 11-2. AI의 Rule 로딩 제한

AI는 일반 작업에서 통합 `Rule.md`를 자동으로 읽지 않습니다. 사용자가 Rule 자체의 검토·개정·동기화를 요청한 경우에만 `Rule.md`와 `human-rule-map.yaml`을 읽습니다.

> `[통합 정책 ID: HUMAN-11.2 | 노드: governance.human-reference | 경로: .agent-governance/governance/human-reference.md]`

### 11-3. 정책 변경의 동시 반영

정책 변경은 통합 Rule, 대상 노드, 노드의 `human_rule_sections`, 관련 traceability map, manifest의 Rule 해시·거버넌스 버전을 같은 변경 단위에서 갱신해야 합니다. 새 노드를 만들면 manifest의 `nodes` 등록과 필요한 router route도 함께 갱신합니다.

> `[통합 정책 ID: HUMAN-11.3 | 주 노드: governance.rule-sync | 보조 노드: governance.human-reference | 경로: .agent-governance/governance/rule-sync.md]`

### 11-4. 불일치 차단

Rule과 노드가 불일치하면 어느 한쪽을 묵시적으로 우선하지 않습니다. 불일치 거버넌스 버전의 활성화를 차단하고 사용자 판단을 요청합니다.

> `[통합 정책 ID: HUMAN-11.4 | 주 노드: governance.human-reference | 보조 노드: core.precedence | 경로: .agent-governance/governance/human-reference.md]`

### 11-5. 양방향 추적성

통합 Rule의 모든 말단 조항은 규칙 ID, 노드 ID, 실제 경로 포인터를 가져야 합니다. `human-rule-map.yaml`과 각 노드의 `human_rule_sections`가 이를 양방향으로 연결합니다. AI는 포인터를 임의 해석하지 않고 정규 YAML 파서 기반 거버넌스 도구의 `sync-plan`과 `validate` 결과로 대상과 정합성을 확인합니다.

> `[통합 정책 ID: HUMAN-11.5 | 주 노드: governance.rule-sync | 보조 노드: governance.human-reference | 경로: .agent-governance/governance/rule-sync.md]`

### 11-6. Staging과 사용자 승인

루트 Rule 변경 전에 `Staging/Rule.md`를 작성하고 의미 동등성, 포인터, 가독성, 롤백을 검증한 뒤 사용자 승인을 받습니다. 사용자가 Staging 통합 Rule에 직접 추가했거나 명시적으로 승인한 정책은 운영 병합 과정에서 누락하거나 이전 초안으로 덮어쓰지 않으며, 가리키는 실행 노드·추적성 원장·manifest 해시와 버전에도 같은 의미와 변경 상태를 유지합니다.

> `[통합 정책 ID: HUMAN-11.6 | 주 노드: governance.human-reference | 보조 노드: operations.staging, workflow.staging-merge | 경로: .agent-governance/governance/human-reference.md]`

### 11-7. Rule 변경의 결정적 동기화 절차

사용자가 `Rule.md`의 항목을 수정하면 AI는 변경된 섹션 번호를 식별하고 거버넌스 도구의 `sync-plan`으로 포인터 대상 노드와 필수 갱신 파일을 산출합니다. 그 결과에 따라 대상 노드의 정책 의미와 `human_rule_sections`, `human-rule-map.yaml`, manifest의 Rule SHA-256·거버넌스 버전을 함께 갱신합니다. 새 노드나 새 작업 유형이 생긴 경우에만 manifest 노드 목록과 router를 추가 갱신합니다. 모든 YAML·노드·포인터·해시를 `validate`로 실제 파싱하고 오류 0건을 확인하기 전에는 해당 거버넌스 버전을 활성화하거나 운영에 병합하지 않습니다. 변경 섹션을 결정할 수 없거나 미등록 섹션이면 추측하지 않고 fail-closed로 중지합니다.

> `[통합 정책 ID: HUMAN-11.7 | 노드: governance.rule-sync | 경로: .agent-governance/governance/rule-sync.md]`

### 11-8. 변경 탐지·반영 확인·동시성 차단

Rule을 수정하려는 AI는 먼저 Staging 작업 디렉터리에서 `sync-status`를 실행하여 추가·변경·삭제된 모든 섹션을 확인합니다. 반환된 `currentRuleHash`를 동기화 계획과 최종 검증의 `--expected-rule-sha`에 그대로 지정하여, 계획 수립 뒤 Rule이 다시 바뀐 경우 적용을 차단합니다. 변경이 있으면 그 전체 섹션 집합으로 `sync-plan`을 실행하고, 출력된 대상 노드의 정책 본문·추적성 map·섹션 기준선·각 노드의 `source_section_digest`를 함께 갱신합니다. 도구는 의미 문장을 자동 작성하지 않으며, 추가된 섹션에 매핑이 없거나 삭제로 인해 참조 섹션이 사라지면 AI가 소유 노드를 판단·수정할 때까지 fail-closed로 중지합니다.

> `[통합 정책 ID: HUMAN-11.8 | 주 노드: governance.rule-sync | 보조 노드: governance.human-reference, workflow.staging-merge | 경로: .agent-governance/governance/rule-sync.md]`

---

## 문서 상태

- 상태: 운영 활성 사용자 참조본
- AI 자동 로딩: 금지
- 운영 루트 반영: 승인 및 반영 완료
- 원본 범위: 루트 `Rule.md`, `VALIDATION_METHODOLOGY.md`, `GEMINI.md`
- 실행 규칙 원본: `.agent-governance/` 노드 트리
