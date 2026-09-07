---
id: core.task-modes
version: 1
parent: core.kernel
source_rules: []
source_validations: []
source_entrypoints: [ENTRY-GEMINI.3, ENTRY-GEMINI.4, ENTRY-GEMINI.5]
human_rule_sections: ["9-3", "9-4", "9-5"]
source_section_digest: 2718530E2C1423C2360BF8CF3893DE101FF8742E7D0AF94DE96C89A91A3A4AB0
always_load: true
may_relax_parent: false
---

# 작업 모드

## 질문·설명

관련 자료를 읽고 답변한다. 파일 변경이나 외부 반영을 수행하지 않는다.

## 제안·검토·계획

근거, 긍정적 측면, 위험, 제약, 실행 조건을 아티팩트로 보고한다. 사용자가 구현을 별도로 승인하기 전에는 코드를 변경하지 않는다.

## 구현·수정

승인된 계획을 확인하고 Task를 순차적으로 수행한다. 운영 코드보다 Staging 검증을 먼저 수행하며, 비파괴 정적 검사를 포함한다.

## 삭제·덮어쓰기·운영 반영

정확한 대상을 확인하고 복구 수단과 영향을 보고한 뒤 필요한 재확인을 받는다.

## 모호한 요청

안전한 읽기·분석은 계속할 수 있다. 결과를 크게 바꾸는 선택이나 파괴적 작업은 질문으로 해소한다.


