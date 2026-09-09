---
id: workflow.plans
version: 1
parent: core.task-modes
source_rules: [RULE-7-PREAMBLE, RULE-7.2.1, RULE-7.2.2, RULE-7.2.3, RULE-7.2.4]
source_validations: [VAL-PREAMBLE, VAL-CORE.1]
source_entrypoints: []
human_rule_sections: ["7", "7-2-1", "7-2-2", "7-2-3", "7-2-4", "10", "10-1-1"]
source_section_digest: 85669724B649984EE83B85BE5C51CF7C6B047094320682C85344114DEB1BB7CE
always_load: false
may_relax_parent: false
---

# 기획 문서

기능 추가, 버그 수정, 아키텍처 개편 전에 Plan을 작성한다. 영구 계획은 `Plans/YYYY/MM/DD/NNN_<작업명>_Plan.md` 형식으로 연·월·일 계층에 보존하고 조율한다. 순번은 일자별 `001_`부터 세 자리 숫자로 배정하며 파일명에서 날짜 접두사는 생략한다.

Task는 Plan 본문에 합치지 않고 `Tasks/YYYY/MM/DD/NNN_<작업명>_Task.md`에 독립 파일로 분리하여 보존하며 공통 `work_id`로 연결한다. 검증 및 점검 보고서는 `Reports/YYYY/MM/DD/NNN_<작업명>_Report.md`에 보존한다.

계획 수립 직후 실제 코드 작성이나 운영 병합 전에 Validation 1~8단계를 순서대로 수행한다. 계획 승인만으로 파괴적 작업이나 이후 단계 전체의 권한이 발생하지 않는다.


