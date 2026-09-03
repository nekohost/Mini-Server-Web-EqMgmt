---
id: validation.orchestration
version: 1
parent: validation.kernel
source_rules: []
source_validations: [VAL-CORE.1]
source_entrypoints: [ENTRY-GEMINI.5, ENTRY-GEMINI.8]
human_rule_sections: ["9-5", "9-8", "10-1-1"]
source_section_digest: 1D14777FE198B194995AC65ED4DFD01C9FF0E8A61F9144141040B61B890161D3
always_load: false
may_relax_parent: false
---

# 순차 검증 오케스트레이션

1. 검증 전에 `task.md` 아티팩트 또는 동등한 Task 목록을 만든다.
2. 1단계부터 8단계까지 순서대로 한 단계씩 수행한다.
3. 각 단계의 근거, 긍정적 결과, 위험, 차단 조건, 추가 발견을 종합 검증 보고서에 누적한다.
4. 단계 자체를 생략할 수 없다. 관찰 대상이 없으면 근거와 함께 `해당 없음`으로 기록한다.
5. 차단 조건이 발견되면 자동으로 구현이나 다음 승인 단계로 넘어가지 않는다.
6. 자기 참조 무한 반복을 막기 위해 한 사이클은 원본 대비 전수 검증 1회와 교차 시나리오 검증 1회로 제한한다. 수정이 생기면 영향받은 단계부터 후속 단계까지 재검증한다.

## 완료 조건

- 1~8단계가 순서대로 기록되었다.
- 미해결 위험과 사용자 결정 사항이 분리되었다.
- 종합 결론이 단계별 증거와 일치한다.


