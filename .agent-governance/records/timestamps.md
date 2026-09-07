---
id: records.timestamps
version: 2
parent: records.conversation-integrity
source_rules: [RULE-6.1.7, RULE-6.4.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["6-1-7", "6-4-4"]
source_section_digest: E3FEE45494BC6603EBAE38BE5856881B1E64147CFC6710CBA11184DC0C3366BE
always_load: false
may_relax_parent: false
---

# 대화 시각

대화 헤더 시각은 `Asia/Seoul` 기준 밀리초 형식으로 기록하며, 시간순 저장의 비교 기준으로 사용한다. 로그의 `Z`가 실제 UTC인지 이미 KST로 기록된 값인지 현재 KST와 비교하여 검증한 뒤 변환한다. 기계적으로 9시간을 더하지 않는다.

실제 시각을 확인하기 전에는 현재 플랫폼에서 접근 가능한 세션 원문·대화 메타데이터·트랜스크립션을 먼저 점검한다. 확인할 수 있는 실제 시각이 있는데도 확인할 수 없다고 말하거나 임의 시각으로 대체해서는 안 된다.

실제 과거 시각을 확보할 수 없는 기존 항목은 임의 시각을 만들지 않고 확인 기준 시각과 `이전에 기록됨`을 사용한다. 이 예외를 새로운 대화의 시각 추정이나 확인 가능한 시각의 미확인 주장에 사용하지 않는다.
