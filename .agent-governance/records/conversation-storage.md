---
id: records.conversation-storage
version: 5
parent: records.conversation-integrity
source_rules: [RULE-6.1.5, RULE-6.1.6, RULE-6.2.1, RULE-6.2.2, RULE-6.2.3, RULE-6.2.4, RULE-6.2.5, RULE-6.2.6, RULE-6.2.7, RULE-6.2.8, RULE-6.2.9, RULE-6.2.10, RULE-6.2.11, RULE-6.2.12, RULE-6.2.13, RULE-6.4.1, RULE-6.4.2, RULE-6.4.3]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-6.1.6-PLATFORM]
human_rule_sections: ["6-1-5", "6-1-6", "6-2-1", "6-2-2", "6-2-3", "6-2-4", "6-2-5", "6-2-6", "6-2-7", "6-2-8", "6-2-9", "6-2-10", "6-2-11", "6-2-12", "6-2-13", "6-4-1", "6-4-2", "6-4-3"]
source_section_digest: F95B7216FE845C9C0C15093F7D32EDAE04993F271A95D61FA8BC86EF3D8B2FDC
always_load: false
may_relax_parent: false
---

# 대화 저장

대화는 전용 writer가 실제 이벤트 시각에 따라 `Chat/YYYY/MM/DD.md`에 날짜별로 저장한다.

1. 사용자·표시 commentary·final의 자동 기록은 별도 승인 없이 수행한다.
2. 전용 Node writer만 `Chat/`, `Chat/Subagents/`, `Chat/.state/`를 변경한다.
3. 각 이벤트는 provider·thread·source 식별자로 만든 provenance ID를 가지며 중복 쓰지 않는다.
4. 이벤트 발생 시각의 KST 날짜 파일을 사용하고 과거 이벤트는 기존 블록을 바꾸지 않은 채 시간순 위치에 삽입한다.
5. 임시 파일 `fsync`와 원자적 rename 뒤 Chat 반영을 확인하고 receipt·source fingerprint를 저장한다.
6. 하위 에이전트 원문은 companion에 분리하고 주 대화에는 한 작업당 receipt를 둔다.
7. companion은 최대 64KiB 순번 파일로 나누며 허용된 원문 스트림을 보존한다.
8. 실패한 플랫폼의 cursor를 전진시키지 않으며 다음 reconcile에서 같은 이벤트부터 재시도한다.
9. 삭제나 덮어쓰기 요청은 별도 확인 대상이며 자동 기록은 기존 블록을 보존하는 원자적 교체만 사용한다.
10. 전용 writer 밖의 수동 복구는 현재 플랫폼 capability와 `tools.conversation-exception` 절차를 따른다.
11. recovery exception 중에는 기능 구현·운영 병합·무관한 일반 파일 변경으로 범위를 확대하지 않으며 복구 성공 전 일반 작업으로 복귀하지 않는다.
12. 프로젝트 owner 상태의 외부 reference와 비독립 execution은 Mini-Server 기록 맥락에 속한다. full scope switch 이후의 독립 owner 원문은 이 프로젝트 기록에 중복 저장하지 않고, nested handoff 상세는 대상 scope에 맡기며 부모에는 최소 receipt만 남긴다.
13. 현재 source adapter에 per-turn owner 신호가 없으면 내용 의미만으로 기존 원문을 삭제·이동하지 않고 capability 제한을 보고한다.
