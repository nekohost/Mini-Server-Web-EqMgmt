---
id: governance.context-routing
version: 1
parent: core.task-modes
source_rules: []
source_validations: []
source_entrypoints: []
source_human: []
human_rule_sections: ["9-1", "9-3"]
source_section_digest: A0B5971556C4B8EF5F00E17284C704A1F370256EA53713F19E556902FCB08F4D
always_load: false
may_relax_parent: false
---

# Context 입력·실패 진단 계약

1. catalog로 작업 종류와 경로를 확인한다. 관련 intent를 하나로 축소하지 않는다.
2. --path는 실제 작업 대상, --reference-path는 읽기 전용 참고·영향 대상이다. 참고 선언과 context 성공은 수정 권한을 부여하지 않는다.
3. DB/UI 필수 노드는 intent로 선택하고 정규화한 경로를 독립 검증한다. Staging 실제 후보를 그대로 선언하며 원본을 자동 추측하거나 통과 목적으로 무관한 경로를 추가하지 않는다.
4. 미등록 intent, 등록된 intent의 경로 불일치, 미분류 경로, 외부 scope 누락, section 누락, 정책 불일치를 diagnostics로 구분한다.
5. 실패 시 일반 구현은 중단한다. 기존 승인 범위의 읽기 전용 진단과 근거 있는 입력 오류 정정·재시도는 가능하며 매번 승인을 요구하지 않는다. 실패 pack·수동 축소 노드를 사용하지 않는다.
6. validate와 새 context가 성공하고 전체 pack을 읽은 뒤 기존 승인 범위에서만 재개한다. 실제 미등록 작업·권한 부족·규칙 충돌·정책 변경 필요를 자동 해소하지 않는다.
7. 오류와 정정 근거를 기록하고 같은 실패의 무한 재시도를 금지한다. 모든 context가 이 노드를 선택하며 pack 분할에서는 본문을 누락하지 않는다.
