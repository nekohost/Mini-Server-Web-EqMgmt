---
id: records.timestamps
version: 3
parent: records.conversation-integrity
source_rules: [RULE-6.1.7, RULE-6.4.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["6-1-7", "6-4-4"]
source_section_digest: 5A67606AE6FF570F314C7E4738519B1E8FBEC5D4B87A81B2B83F5C0905118C0F
always_load: false
may_relax_parent: false
---

# 대화 시각

대화 헤더 시각은 플랫폼 원본 이벤트의 offset 포함 timestamp를 검증한 뒤 `Asia/Seoul` 밀리초 형식으로 변환하며 날짜 파일 선택과 정렬에 같은 값을 사용한다.

세션 폴더 날짜, 파일 mtime, 기록기 실행 시각이나 모델의 추정 시각을 발언 시각으로 대신하지 않는다. offset이 없거나 유효하지 않은 timestamp는 오류로 격리하고 해당 원본 cursor를 전진시키지 않는다.

실제 과거 시각을 확보할 수 없는 기존 항목은 임의 시각을 만들지 않고 확인 기준 시각과 `이전에 기록됨`을 사용한다. 이 예외를 새로운 대화의 시각 추정에 사용하지 않는다.
