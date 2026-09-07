---
id: validation.phase.04-production-impact
version: 1
parent: validation.orchestration
source_rules: []
source_validations: [VAL-PHASE.4.0, VAL-PHASE.4.1, VAL-PHASE.4.2, VAL-PHASE.4.3, VAL-PHASE.4.4, VAL-PHASE.4.5]
source_entrypoints: []
human_rule_sections: ["10-5", "10-5-1", "10-5-2", "10-5-3", "10-5-4", "10-5-5"]
source_section_digest: F497DEA0581DDEDC493C796216E4340F538CD241D6D1952C2FD9E6B152AE6646
always_load: false
may_relax_parent: false
---

# 4단계: 운영 병합 영향

격리 결과물이 운영 루트에 병합될 때의 사이드이펙트를 평가한다.

- 신규 라우트 주소와 기존 우선순위가 충돌하는가.
- API나 기능이 기존 권한 제어 밖으로 노출되는가.
- 레거시 코드를 침범하며 확장하는가.
- 전역 변수나 글로벌 상태 변경이 다른 기능에 파급되는가.
- 기존 테스트와 동작을 깨는 Breaking Change가 있는가.
- 배포 순서, 설정, DB 버전이 어긋나는 부분 병합 위험이 있는가.


