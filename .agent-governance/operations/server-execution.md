---
id: operations.server-execution
version: 1
parent: context.deployment-topology
source_rules: [RULE-5.1.2, RULE-5.1.4]
source_validations: []
source_entrypoints: []
human_rule_sections: ["5-1-2", "5-1-4"]
source_section_digest: 02FC361E4A1BECB7507FC35EE83D9F1320574AD627B6E7D94109CA051B708FDB
always_load: false
may_relax_parent: false
---

# Linux Lite 실행과 테스트

모든 실제 구동과 동작 테스트는 미니서버 `192.168.0.166`에 SSH로 접속하여 수행한다.

기본 흐름은 `git pull origin main`, 기존 프로세스의 안전한 종료, `python3 app.py`, `http://192.168.0.166:5000` 확인이다. 프로세스 종료나 배포는 현재 실행 상태와 대상을 먼저 확인하며, 사용자 승인 범위를 넘는 운영 반영을 수행하지 않는다.


