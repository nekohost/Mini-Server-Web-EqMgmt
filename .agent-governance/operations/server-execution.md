---
id: operations.server-execution
version: 2
parent: context.deployment-topology
source_rules: [RULE-5.1.2, RULE-5.1.4]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-5.1.2-ORDER]
human_rule_sections: ["5-1-2", "5-1-4"]
source_section_digest: ED1C92249CA827CDB2745044189A1A431DF399DD2F7D6D45666C4DD76A22B254
always_load: false
may_relax_parent: false
---

# Linux Lite 실행과 테스트

모든 실제 구동과 동작 테스트는 미니서버 또는 사용자가 검증 대상으로 지정한 백업 Linux 서버에 SSH로 접속하여 수행한다.

`운영 소스 반영`은 Windows 프로젝트 루트에 승인된 Staging 변경을 병합하는 단계다. `Linux 서비스 적용`은 Git 원격의 승인 commit을 Linux 서버에 pull하고 서비스를 시작·재시작하는 단계다. Linux 실행 검증이 아직 수행되지 않았다는 이유만으로 사용자 승인된 운영 소스 반영이나 Git push를 선행 차단하지 않는다.

표준 순서는 Staging 구현, Staging 정적 검증, 사용자 승인, Windows 운영 소스 병합, 운영 소스 정적 재검증, Staging 정리, commit·push, Linux pull과 commit 일치 확인, Linux 격리 검증, 서비스 시작·재시작과 브라우저/API 확인이다.

Linux 검증 실패 시 서버에서 즉석 수정하지 않는다. Windows Staging으로 돌아가 수정·정적 검증·승인·운영 소스 병합·push·pull 순서를 다시 수행한다. 프로세스 종료나 배포는 현재 실행 상태와 대상을 먼저 확인하며, 사용자 승인 범위를 넘는 운영 반영을 수행하지 않는다.
