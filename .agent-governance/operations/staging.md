---
id: operations.staging
version: 1
parent: core.kernel
source_rules: [RULE-5.1.3, RULE-7.3.1, RULE-7.3.2]
source_validations: [VAL-PHASE.1.3]
source_entrypoints: []
human_rule_sections: ["5-1-3", "7-3-1", "7-3-2", "10-2-3"]
source_section_digest: 7B3BAE182FC1CF7FFA10ECD7D5381C6945E6FD7F565B57C89963FF7E789F1360
always_load: false
may_relax_parent: false
---

# Staging 격리

운영 코드 `app.py`, `templates/` 등을 수정하기 전에 `Staging/`에서 안전한 복사본이나 모의 결과물을 작성하여 검토한다.

Staging은 독립 실행 환경이 아니라 정적 판단, 검토, 보고서 작성용 안전망이다. Windows에서 Staging 애플리케이션을 직접 구동하지 않는다. 운영 병합과 정리는 `workflow.staging-merge`를 따른다.


