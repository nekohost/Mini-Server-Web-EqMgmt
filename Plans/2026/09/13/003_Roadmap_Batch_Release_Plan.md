---
artifact_id: PLAN-20260913-003
work_id: WORK-20260913-ROADMAP-BATCH-RELEASE
created_at: 2026-09-13T12:05:36+09:00
---

# 제안 일괄 구현 운영·백업 서버 반영

사용자의 최신 명시 승인으로 002 스테이징 후보를 운영 소스, commit/push, 백업 Linux 서비스까지 적용한다. 추가 승인 질문 없이 검증 실패는 같은 범위의 Staging 수정→정적 검사→병합→push/pull→Linux 재시험으로 해결한다. 별도 계획(전체 주석 재구축, 변경형 WebMCP, systemd 서비스화)은 제외한다.

기준 commit: 62a933f9e0e1c81dc25b050d823604a6c6db6956. 원격 tracked 변경 없음, 기존 untracked 백업/가상환경 보존. 실제 DB v2, integrity/FK 정상, 사용자2/장비1/옵션1/노드12/장비감사5. 확인된 프로세스만 종료·재기동한다.

순서: Task 생성 → Validation 1~8 → manifest 기준선/후보 검토 → 운영 CLI를 기존 tools/ 경로에 배치하고 배포 점검 도구를 v3에 맞춤 → Staging 정적 검사 → 28개 후보 및 필요한 배포 보정 운영 병합 → 정적 재검사 → 이번 후보만 정리(README/manifest는 Reports에 보존) → commit/push → Linux pull/HEAD 대조 → 격리 전체 회귀·실제 DB 온라인 사본 migration 및 원래 컬럼 지문 보존 검증 → 서비스 교체 → 실제 DB/HTTP 및 알림 dry-run → 완료 이력/결과 commit/push/pull.

DB 변경은 utils/roadmap_schema.py의 명시 DDL로 equipments revision/기한, users 검증 주소, 네 테이블·인덱스·트리거를 transaction으로 추가하고 sys_migrations/PRAGMA를 v3으로 함께 올린다. 기존 업무 행을 삭제하거나 공식명을 추정하지 않는다. 서비스 교체 직전 private online snapshot 및 기준 지문을 보존한다. v3 데이터 발생 후 자동 down/옛 DB 덮어쓰기는 하지 않으며 현재 DB·첨부를 보존한 v3 호환 수정 전진을 기본 복구로 한다. 초기 migration 실패는 transaction rollback 후 원인 수정, 불확실 상태에서는 쓰기를 재개하지 않는다.

알림은 기존 Graph 설정의 존재 여부만 검사하고 비밀은 출력하지 않는다. 검증 주소·명시 수신 동의 및 dry-run을 확인한다. 예약 가동은 기존 기능 범위에서 검증된 CLI/운영 방식으로만 구성하며 systemd 전환은 하지 않는다. 실제 UI 실사용과 자동 테스트를 구분하여 기록한다.

연결 문서: Tasks/2026/09/13/003_Roadmap_Batch_Release_Task.md, Reports/2026/09/13/003_Roadmap_Batch_Release_Report.md.
