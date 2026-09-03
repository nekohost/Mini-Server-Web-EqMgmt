---
id: validation.phase.08-ai-meta
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.8.0, VAL-PHASE.8.1, VAL-PHASE.8.2, VAL-PHASE.8.3, VAL-PHASE.8.4]
source_entrypoints: []
human_rule_sections: ["10-9", "10-9-1", "10-9-2", "10-9-3", "10-9-4"]
source_section_digest: 9C0CF35BB0902BA7CB8C7C91F496CC7C1AF6F555CB846B04F69137EF237CD3EF
always_load: false
may_relax_parent: false
---

# 8단계: AI 메타 거버넌스

AI 작업자가 목적 달성을 빌미로 컨텍스트와 저장소를 오염시키지 않았는지 검사한다.

- 분석용 scratch 파일을 보존 정책에 맞게 정리했는가.
- 로그와 아티팩트에 환각, 억지 주장, 무관한 맥락을 넣지 않았는가.
- Rule·Validation·진입점 통제를 표현 변경이나 우회로 회피하지 않았는가.
- 승인을 재촉하지 않고 객관적·명확한 문구를 사용했는가.
- 실제 작업자 이름, 작업 모드, 승인 범위를 올바르게 식별했는가.


