---
id: records.timestamps
version: 4
parent: records.conversation-integrity
source_rules: [RULE-6.1.7, RULE-6.4.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["6-1-7", "6-4-4"]
source_section_digest: D931A65A1C6F0F6491A2734942FC398188D41614C405AE9F3BD1EEF2136A5324
always_load: false
may_relax_parent: false
---

# 대화 시각

플랫폼이 원본 이벤트의 offset 포함 source timestamp를 제공하는 경우 이를 검증한 뒤 `Asia/Seoul` 밀리초 형식으로 변환하며 날짜 파일 선택과 정렬에 같은 값을 사용한다. 이 경우 세션 폴더 날짜, 파일 mtime, 기록기 실행 시각이나 모델의 추정 시각으로 실제 발생 시각을 대신하지 않는다. source timestamp를 제공하는 플랫폼에서 offset이 없거나 값이 유효하지 않아 정확한 시각을 확정할 수 없으면 해당 이벤트를 오류로 격리하고 원본 cursor를 전진시키지 않는다.

다만 ChatGPT + Remote Desktop Commander처럼 플랫폼에서 정확한 source timestamp 자체를 제공하지 않는 환경은 `RULE-6.1.7`의 명시적 예외로 취급한다. 이 경우 해당 대화 턴에서 확인 가능한 가장 마지막 도구 호출 시각을 우선 사용하고, 그것도 사용할 수 없으면 확인 가능한 가장 마지막 답변 시각으로 갈음하여 KST 헤더와 시간순 정렬 기준으로 사용한다.

실제 과거 시각을 확보할 수 없는 기존 항목은 `RULE-6.4.4`에 따라 임의 시각을 만들지 않고 확인 기준 시각과 `이전에 기록됨`을 사용한다. 이 과거 기록 예외는 위의 `RULE-6.1.7` source timestamp 미제공 플랫폼 fallback과 구분한다.
