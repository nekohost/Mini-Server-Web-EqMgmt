---
id: validation.phase.07-human-error
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.7.0, VAL-PHASE.7.1, VAL-PHASE.7.2, VAL-PHASE.7.3, VAL-PHASE.7.4]
source_entrypoints: []
human_rule_sections: ["10-8", "10-8-1", "10-8-2", "10-8-3", "10-8-4"]
source_section_digest: B3C3858446845544EF8D556C3588E692A564ECBFBB13EBEA9E864EAB26D421EF
always_load: false
may_relax_parent: false
---

# 7단계: 휴먼 에러와 UX 방어

사용자가 잘못 조작해도 복구 가능하고 이해 가능한 흐름인지 검사한다.

- 잘못된 동선에 비활성화 사유와 오류 피드백이 제공되는가.
- 다음 단계로 갈 수 없는 데드엔드 UI가 있는가.
- 삭제·덮어쓰기 등 파괴적 액션 전에 이중 확인이 있는가.
- 필수값 누락과 범위 오류를 프론트엔드에서 1차 검증하는가.
- 재시도, 취소, 뒤로 가기, 중복 클릭이 데이터나 상태를 훼손하는가.


