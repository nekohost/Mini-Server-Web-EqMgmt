# [Rule 후보 개정안] Rule.md 제6-3-1조 및 conversation-integrity 노드

- 대상 섹션: `6-3-1` (사용자 헤더)
- 보조 섹션: `6-1-3` (실제 AI 이름과 KST 헤더)
- 연관 노드: `records.conversation-integrity` (`.agent-governance/records/conversation-integrity.md`)

---

## 1. Rule.md 제6-3-1조 개정안

```markdown
#### 6-3-1. 사용자 헤더

사용자 항목은 다중 AI 협업 환경에서 수신 대상을 명시한 `## 사용자 → <대상AI> YYYY-MM-DD HH:mm:ss.000` 형식을 기본으로 사용합니다. (예: `## 사용자 → Gemini ...`, `## 사용자 → Codex ...`)
단일 AI 시절의 기존 `## 사용자 YYYY-MM-DD HH:mm:ss.000` 단독 표기도 호환하여 인정하며, 기존 기록을 불필요하게 소급 수정하지 않습니다.

> `[규칙 ID: RULE-6.3.1 | 노드: records.conversation-integrity | 경로: .agent-governance/records/conversation-integrity.md]`
```
---

## 2. Rule.md 제6-1-3조 (현행 유지 또는 필요 시 상호 참조)

```markdown
#### 6-1-3. 실제 AI 이름과 KST 헤더

현재 작업자는 다른 AI 이름을 무비판적으로 복사하지 않고 실제 모델명을 사용합니다. `## Codex YYYY-MM-DD HH:mm:ss.000`, `## Claude ...`, `## Gemini ...`처럼 `Asia/Seoul` 기준으로 기록합니다.

> `[규칙 ID: RULE-6.1.3 | 주 노드: workflow.multi-agent-handoff | 보조 노드: records.conversation-integrity | 경로: .agent-governance/workflow/multi-agent-handoff.md]`
```

---

## 3. records.conversation-integrity 노드 개정안

```markdown
# 대화 기록 무결성

사용자 메시지와 AI의 최종 응답 및 중간 안내를 Markdown, 코드 블록, 링크까지 원문 그대로 기록한다. 제안한 코드·설정·명령도 실제 대화와 토씨 하나 다르지 않게 포함한다.

- 사용자는 다중 AI 협업 환경에서 `## 사용자 → <대상AI> YYYY-MM-DD HH:mm:ss.000` 형식을 기본으로 사용하며, 기존 `## 사용자 ...` 단독 표기도 호환하여 인정한다.
- AI는 현재 실제 작업자 이름을 사용한다. 다른 모델명을 복사하지 않는다.
- 적용된 변경과 검토·실행 대기 제안을 명확히 구분한다.
- 제안에는 실행 환경, 대상, 선행 조건을 포함한다.
- 코드 블록은 언어를 지정한다.
- 비밀번호, 토큰, 개인키, 개인정보는 원문 대신 `<비밀번호>` 같은 자리표시자로 치환한다.

플랫폼이 정확한 원문이나 시각을 제공하지 않으면 임의로 만들어 기록하지 말고 기능 제한을 보고한다.
```
