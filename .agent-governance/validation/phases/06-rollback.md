---
id: validation.phase.06-rollback
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.6.0, VAL-PHASE.6.1, VAL-PHASE.6.2, VAL-PHASE.6.3, VAL-PHASE.6.4]
source_entrypoints: []
human_rule_sections: ["10-7", "10-7-1", "10-7-2", "10-7-3", "10-7-4"]
source_section_digest: 457885F0C58AAA56F3EC9E11CAC4B46FFEA778ACAD1E957F8382E4911001BC7C
always_load: false
may_relax_parent: false
---

# 6단계: 롤백과 역방향 파급

병합 직후 치명적 오류가 발견된 상황에서 안전한 복귀가 가능한지 검사한다.

- DB Up 변경뿐 아니라 Down 또는 동등한 복구 절차가 가능한가.
- 코드 롤백 후 신규 데이터 때문에 기동 실패가 발생하는가.
- 캐시·세션·클라이언트 저장소 잔여물이 롤백 후 오류를 만드는가.
- 환경변수·인프라와 코드가 결합되어 부분 롤백 충돌이 생기는가.
- 복구 대상, 백업, 검증, 중단 시간과 실패 시 2차 복구 경로가 명확한가.


