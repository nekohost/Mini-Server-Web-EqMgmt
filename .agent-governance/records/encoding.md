---
id: records.encoding
version: 2
parent: records.conversation-storage
source_rules: [RULE-6.1.8, RULE-6.1.9]
source_validations: []
source_entrypoints: []
human_rule_sections: ["6-1-8", "6-1-9"]
source_section_digest: A2CE40BE73A777463EBFAF0E3DE6E86A6BDF3D613EFACD1F11A5A36504934861
always_load: false
may_relax_parent: false
---

# Windows 대화 기록 인코딩

전용 기록기는 Node 파일 API에 `utf8`을 명시하고 shell 명령 문자열로 대화 본문을 전달하지 않는다. companion 분할은 JavaScript 코드 포인트 경계를 사용하며 각 파일의 실제 UTF-8 크기를 64KiB 이하로 제한한다.

수동 PowerShell 복구에서는 한글 원문을 명령에 직접 하드코딩하지 않고 UTF-8 중간 파일을 사용한다. Markdown을 PowerShell 문자열로 다룰 때 큰따옴표 확장 Here-String `@"..."@`을 사용하지 않으며 필요한 경우 작은따옴표 리터럴 Here-String `@'...'@`을 사용한다.


