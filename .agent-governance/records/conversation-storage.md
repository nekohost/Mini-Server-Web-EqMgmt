---
id: records.conversation-storage
version: 3
parent: records.conversation-integrity
source_rules: [RULE-6.1.5, RULE-6.1.6, RULE-6.2.1, RULE-6.2.2, RULE-6.2.3, RULE-6.2.4, RULE-6.2.5, RULE-6.2.6, RULE-6.2.7, RULE-6.2.8, RULE-6.2.9, RULE-6.2.10, RULE-6.2.11, RULE-6.2.12, RULE-6.4.1, RULE-6.4.2, RULE-6.4.3]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-6.1.6-PLATFORM]
human_rule_sections: ["6-1-5", "6-1-6", "6-2-1", "6-2-2", "6-2-3", "6-2-4", "6-2-5", "6-2-6", "6-2-7", "6-2-8", "6-2-9", "6-2-10", "6-2-11", "6-2-12", "6-4-1", "6-4-2", "6-4-3"]
source_section_digest: FBB37634AD3C13C9B243E12F896930D580BA7481FAD07CB1588267B418E9EBEB
always_load: false
may_relax_parent: false
---

# 대화 저장

대화는 전용 writer가 실제 이벤트 시각에 따라 `Chat/YYYY/MM/DD.md`에 날짜별로 저장한다.

1. 사용자·표시 commentary·final의 자동 기록은 별도 승인 없이 수행한다.
2. 전용 Node writer만 `Chat/`, `Chat/Subagents/`, `Chat/.state/`를 변경한다.
3. 각 이벤트는 provider·thread·source 식별자로 만든 provenance ID를 가지며 기존 표식 또는 동일 시각·speaker·원문과 일치하면 다시 쓰지 않는다.
4. 이벤트 발생 시각의 KST 날짜 파일을 사용하고 과거 이벤트는 기존 블록을 바꾸지 않은 채 시간순 위치에 삽입한다.
5. 임시 파일 `fsync`와 원자적 rename 뒤 Chat 반영을 확인하고 receipt·source fingerprint를 저장한다.
6. 하위 에이전트 원문은 companion에 분리하고 주 대화에는 한 작업당 receipt를 둔다.
7. companion은 최대 64KiB 순번 파일로 나누며 모든 조각을 이어 붙였을 때 허용된 원문 스트림이 보존되어야 한다.
8. 실패한 플랫폼의 cursor를 전진시키지 않으며 다음 reconcile에서 같은 이벤트부터 재시도한다.
9. 삭제나 덮어쓰기 요청은 별도 확인 대상이다. 자동 기록의 원자적 파일 교체는 기존 블록을 보존하는 승인된 저장 구현이다.
10. 전용 writer 밖의 수동 복구는 현재 플랫폼 capability와 `tools.conversation-exception` 절차를 따른다.
