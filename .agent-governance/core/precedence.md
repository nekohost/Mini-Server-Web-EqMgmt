---
id: core.precedence
version: 1
parent: core.kernel
source_rules: []
source_validations: []
source_entrypoints: [ENTRY-GEMINI.1, ENTRY-GEMINI.2, ENTRY-GEMINI.3]
human_rule_sections: ["9-1", "9-2", "9-3"]
source_section_digest: 9ECB5674699A4C3F3317DB41A8B3BE4BB3AFCBE6584B1FC292D1C39789EAB76D
always_load: true
may_relax_parent: false
---

# 규칙 우선순위와 충돌 처리

적용 순서는 플랫폼 시스템·개발자 지시, 안전 커널, 프로젝트 공통 노드, 작업 유형 노드, 기술·경로 노드, 승인된 작업 계획, 현재 요청의 세부 조건이다.

같은 계층에서는 대상과 조건이 더 구체적인 규칙을 적용한다. 하위 노드가 상위 안전 규칙을 완화하거나 두 규칙을 동시에 만족시킬 수 없으면 실행을 중지하고 다음을 보고한다.

1. 충돌한 규칙 ID와 문구
2. 요청된 행위와 충돌 지점
3. 실행할 경우의 영향
4. 안전하게 진행하기 위해 필요한 사용자 결정

규칙 파일을 읽지 못하거나 manifest와 실제 파일이 다르면 성공으로 간주하지 않는다.


