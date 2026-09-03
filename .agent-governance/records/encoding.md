---
id: records.encoding
version: 1
parent: records.conversation-storage
source_rules: [RULE-6.1.8, RULE-6.1.9]
source_validations: []
source_entrypoints: []
human_rule_sections: ["6-1-8", "6-1-9"]
source_section_digest: CB69B6712956A7A90C6C16D641F0D28D63CC0F119127944EA95BECFA209D6BA1
always_load: false
may_relax_parent: false
---

# Windows 대화 기록 인코딩

PowerShell을 통한 Chat append가 필요하면 한글을 명령 문자열에 직접 하드코딩하지 않는다. IDE 편집 API로 UTF-8 중간 파일을 만든 후 `Get-Content -Encoding UTF8`로 읽어 append하는 방식을 사용한다.

Markdown을 PowerShell 문자열로 다룰 때 큰따옴표 확장 Here-String `@"..."@`을 사용하지 않는다. 백틱과 제어 문자가 변형되지 않도록 변수 확장이 없는 작은따옴표 리터럴 Here-String `@'...'@`을 사용한다.


