---
id: context.deployment-topology
version: 1
parent: context.project
source_rules: [RULE-1.2, RULE-2.6, RULE-2.7]
source_validations: []
source_entrypoints: []
source_human: [HUMAN-2.6-BACKUP]
human_rule_sections: ["1-2", "2-6", "2-7"]
source_section_digest: 7DD56DBD1BE15BF8F9BEF55A4F152D1AB0E9F32389DF8CF9138B7933D0EA2DCF
always_load: false
may_relax_parent: false
---

# 배포 토폴로지

개발 흐름은 Windows PC에서 소스 작성과 Git Push를 수행하고, GitHub를 거쳐 Linux Lite 미니서버가 Git Pull로 배포받는 구조다.

- 미니서버: `192.168.0.166`
- 백업 서버: `192.168.0.24`
- Flask 포트: `5000`
- 내부 접속 URL: `http://192.168.0.166:5000`

백업 서버 주소는 사용자가 Staging 통합 Rule에 직접 추가한 운영 정보다. 운영 규칙으로 병합할 때 누락하거나 이전 값으로 덮어쓰지 않고, 통합 Rule과 이 노드 양쪽에 동일하게 유지한다.

서버 주소는 운영 정보이므로 외부 공개 문서나 로그에 불필요하게 확산하지 않는다.


