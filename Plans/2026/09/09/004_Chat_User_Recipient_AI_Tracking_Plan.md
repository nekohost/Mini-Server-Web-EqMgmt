---
artifact_id: PLAN-20260909-004
work_id: WORK-20260909-CHAT-RECIPIENT-TRACKING
created_at: 2026-09-09T14:36:06.542+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/09/006_Chat_User_Recipient_AI_Tracking_Task.md
  - ../../../../Reports/2026/09/09/011_Chat_User_Recipient_AI_Tracking_Staging_Validation_Report.md
---
# [계획서] Chat 대화 기록의 사용자 발언 수신 대상 AI 명시화 계획

- 작성일: 2026-09-09
- 작업 모드: 거버넌스 규칙 개정 및 대화 기록기 고도화 계획 (Plan)
- 관련 계획 ID: `004`
- 관련 Task: `Tasks/2026/09/09/006_Chat_User_Recipient_AI_Tracking_Task.md`
- 상태: **계획 수립 완료, 사용자 검토 및 승인 대기** (구현 차단 유지)

---

## 1. 개요 및 배경

### 1) 현행 상태 및 문제점
- 현재 `Chat/YYYY/MM/DD.md`에 기록되는 사용자 발언 헤더는 `## 사용자 YYYY-MM-DD HH:mm:ss.000` 형식으로 통일되어 있습니다.
- 단일 AI(Antigravity/Gemini)만 사용하던 과거에는 문제가 없었으나, 현재는 **사용자 - Codex - Gemini(Antigravity) - Claude** 등 다중 AI와 동시 협업하는 환경으로 확장되었습니다.
- 그 결과, 대화 로그만 보았을 때 해당 사용자 발언이 **누구(어떤 AI)를 향한 지시·질문이었는지**를 직관적으로 판별하기 어려운 문제가 발생하고 있습니다.

### 2) 개선 목표
- 사용자 발언 기록 시 발언을 수신한 대상 AI를 헤더에 명시적으로 표기하여 다중 협업 대화의 가독성과 문맥 추적성을 극대화합니다.
- 기존의 하위 에이전트 표기 규격(`## 부모 → Gemini 하위 에이전트`)과 자연스럽게 조화를 이루는 일관된 헤더 표기 체계를 확립합니다.

---

## 2. 사용자 검토 및 결정 필요 사항 (User Review Required)

### 📌 핵심 결정 1: 사용자 발언 헤더 표기 포맷 선택
대화 기록 가독성을 위해 아래 3가지 안 중 권장안(안 1)을 제안합니다:
- **(권장) 안 1. 화살표형 표기**: `## 사용자 → Gemini YYYY-MM-DD HH:mm:ss.000` / `## 사용자 → Codex ...`
  - 하위 작업 위임 표기(`## 부모 → <AI> 하위 에이전트`)와 완벽히 대칭되며, 누구를 향한 지시인지 가장 직관적임.
- **안 2. 괄호형 표기**: `## 사용자 (Gemini) YYYY-MM-DD HH:mm:ss.000` / `## 사용자 (Codex) ...`
- **안 3. 대괄호형 표기**: `## 사용자 [Gemini] YYYY-MM-DD HH:mm:ss.000` / `## 사용자 [Codex] ...`

### 📌 핵심 결정 2: 과거 기록의 소급 적용 여부
- **(권장) 신규 발언부터 점진 적용**: 기존 파일(8월~9월 대화)의 대규모 Git 변경 churn 및 hash 변동을 방지하기 위해 신규 발언부터 적용.
- **전체 소급 변환**: 과거 기록까지 일괄 변환 스크립트를 통해 전체 `Chat/`을 갱신 (원하실 경우 별도 안전 마이그레이션 지원).

---

## 3. 세부 구현 계획

### 1단계: 거버넌스 규칙 개정 및 동기화 (`Rule.md` 및 원장)
1. **`Rule.md` 제6-1-1조 개정**:
   - 기존: `사용자는 ## 사용자 YYYY-MM-DD HH:mm:ss.000 형식을 사용한다.`
   - 개정안: `사용자는 다중 AI 협업 환경에서 수신 대상을 명시한 ## 사용자 → <대상AI> YYYY-MM-DD HH:mm:ss.000 형식을 기본으로 하며, 기존 ## 사용자 ... 단독 표기도 호환하여 인정한다.`
2. **노드 및 원장 동기화**:
   - `.agent-governance/records/conversation-integrity.md` 수정
   - `node .agent-governance/tooling/governance-tool.mjs sync-status` 확인 후 `rule-section-baseline.yaml`, `human-rule-map.yaml`, `manifest.yaml` 갱신

### 2단계: 대화 기록기 어댑터 수정 (`.agent-governance/tooling/conversation-recorder/`)
1. **`core.mjs`**:
   - `eventAlreadyRecorded`에서 기존 `## 사용자` 및 신규 `## 사용자 → <대상AI>` 양방향 legacy 호환 검증 보장.
2. **`antigravity.mjs`**:
   - `conversationEvents()`의 사용자 이벤트 생성 시:
     `speaker: isSubagent ? '부모 → Gemini 하위 에이전트' : '사용자 → Gemini'`
3. **`codex.mjs`**:
   - `parseCodexTranscript()`의 사용자 이벤트 생성 시:
     `speaker: isSubagent ? '부모 → Codex 하위 에이전트' : '사용자 → Codex'`
4. **`claude.mjs`**:
   - 향후 지원 시 `사용자 → Claude` 사전 정의.

### 3단계: 단위 테스트 및 검증
- `conversation-recorder.test.mjs`에 `사용자 → <AI>` 헤더 파싱, provenance 유지, 기존 기록과의 중복 방지 테스트 추가.
- `node .agent-governance/tooling/governance-tool.mjs validate` 정규 파서 검증.

---

## 4. Validation 1~8 사전 검증

| 단계 | 검증 항목 | 판정 | 상세 근거 |
| :--- | :--- | :---: | :--- |
| **1단계** | 거버넌스 준수성 | **통과** | Rule 제6조의 개정 절차(`rule-sync`)를 정식 준수하고 원장 해시와 동시 반영하도록 설계됨. |
| **2단계** | 사용자 의도 달성도 | **통과** | 다중 AI 환경에서 발언 수신 대상을 명확히 식별하고자 하는 사용자 의도를 100% 충족. |
| **3단계** | 정적 논리 호환성 | **통과** | 헤더 정규식(`^## [^\n]+ <시간>`)이 이미 가변 speaker를 지원하므로 삽입 위치 계산 알고리즘에 부작용 없음. |
| **4단계** | 운영 병합 영향도 | **통과** | 기존 Chat 블록의 provenance ID 매칭은 speaker 텍스트와 무관하게 고유 해시로 동작하므로 기존 기록 보존됨. |
| **5단계** | 보안 및 예외 케이스 | **통과** | 화살표(`→`)는 일반 유니코드 기호로 Markdown 구조나 렌더러에 악영향을 주지 않음. |
| **6단계** | 롤백 가능성 | **통과** | Git 커밋 단위를 통해 어댑터 및 Rule 롤백이 즉시 가능. |
| **7단계** | 휴먼 에러 방지 | **통과** | 사용자가 수동 입력하지 않고 플랫폼 어댑터가 자동 태깅하므로 오기입 위험 전무. |
| **8단계** | AI 메타 거버넌스 | **통과** | 승인 없는 임의 코드 수정을 차단하고 계획서 승인 절차를 엄격히 준수. |

---

## 5. 향후 일정 및 진행 조건

사용자께서 제시된 표기 포맷(안 1 권장: `## 사용자 → <대상AI>`) 및 과거 기록 처리 방식(신규 적용 권장)을 확인하시고 승인해 주시면, Task를 활성화하여 Staging 및 거버넌스 동기화 구현을 진행하겠습니다.
