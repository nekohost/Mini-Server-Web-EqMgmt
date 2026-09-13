---
artifact_id: PLAN-20260913-002
work_id: WORK-20260913-ROADMAP-BATCH-STAGING
created_at: 2026-09-13T00:40:52+09:00
---

# 제안 8개 기능 묶음 스테이징 실행

사용자 승인: 제안 관련 미구현 기능을 추가 질문 없이 스테이징까지 구현한다. 별도 계획 대상(app.py 주석 재구축, 변경형 WebMCP, systemd 배포)은 제외한다. 이 문서는 새 제안이 아니라 기존 PLAN-20260911-004의 실행·검증 추적용이다.

기준 HEAD: 62a933f9e0e1c81dc25b050d823604a6c6db6956. 운영 소스·DB·Git 이력·서비스는 변경하지 않는다. 모든 후보는 Staging/Roadmap_Batch_20260913 아래에 둔다.

## 구현 순서와 계약

1. 002: 공통 타입·길이·실제 날짜·JSON·신규 비밀번호 검증을 기존 가입/계정/장비/마스터/노드/옵션 요청에 연결한다. 기존 로그인 비밀번호 정책은 바꾸지 않는다.
2. 007: SQLite 공유 버킷으로 인증 요청의 계정+IP 및 IP 한도를 원자적으로 소비한다. 429/Retry-After, 만료 청소, 프록시가 아닌 실제 peer 신뢰 경계를 명시한다. 영구 잠금은 없다.
3. 022/033: ACTIVE/LOANED/REPAIR/DISPOSED 전이, revision 경합 검사, 기존 독립 감사 이력 재사용, 상세 패널 및 실제 상태 통계.
4. 023: 공통 SQL 권한 조건에 복합 필터·페이지·허용 정렬을 AND 결합한다. 기존 배열 API는 보존하고 paginated=1 계약을 추가한다. 모델명은 공식명/전체 노드 경로 모두 검색한다.
5. 010: static 외부 opaque 저장키, PNG/JPEG/PDF 제한 및 서명 검사, 매 다운로드 권한, 삭제 시 논리 보존. 전체 ZIP 백업 manifest와 검증/복구 도구 후보를 포함한다. 기존 DB-only 복원은 필요한 첨부가 없으면 거부한다.
6. 008: 선택 기한 컬럼, KST 날짜 배지, 명시적 수신 동의, 검증된 주소, 일별 발송 원장과 단일 CLI 예약 작업. 실제 메일은 보내지 않는다. 외부 메일 성공 후 응답 유실은 자동 중복 재발송하지 않는 불확실 상태로 남긴다.
7. 019: 기존 PreferencesJSON에 standard/edge 허용값과 공통 레이아웃 클래스, 마이페이지 설정. 테마·기존 설정 보존.
8. 026: BOM CSV, 권한/필터 일치 export, 수식 방어, 미리보기→확정 토큰, 승인된 option_id, 최대 500행/1MiB, 원자적 적용·중복 방지.

## DB/통합/검증

스키마 v3: equipments의 revision·보증일·교체일, equipment_files, auth_rate_buckets, equipment_imports, equipment_notification_log. 감사 원장은 기존 equipments_audit_log를 재사용한다. v0/1/2→3 경로와 계약 검증을 함께 수정하며 자동 DROP/데이터 보정은 하지 않는다. migration 전 private snapshot, 신규 기능 자료가 생긴 후에는 v2 DB로 덮어쓰기 금지; v3 데이터 보존 상태로 기능 비활성화하는 운영 복구를 사용한다.

통합 검토에서 users.notification_verified_email을 추가했다. 기존 이메일 변경은 email_verifications를 소비하기 때문에 검증된 현재 주소를 보존해야 한다. 인증 한도는 실패 후 비원자적 증가 대신 모든 시도를 원자적으로 소비한다(로그인 10/계정+IP, 60/IP/15분). 첨부 한도는 파일10MiB/활성50개/업로더별 보관본 포함512MiB, CSV 1MiB/500행, 전체 ZIP2GiB로 확정했다. 기존 새 옵션 inline 등록의 승인 우회를 기존 save_option 서비스로 연결하고, 알림/복원은 같은 Linux flock으로 직렬화한다. v3 기능 중지/복구는 점검 모드·알림 중지와 v3 호환 코드 유지가 전제이며 자동 v3 down은 제공하지 않는다.

기존 카탈로그 복원, 제조사+공식명 표시, 옵션 삭제, 점검/백업을 회귀 대상으로 유지한다. 정적 Python AST·JS 문법/VM·Jinja 구문·연결 검사를 실시하고 Linux용 격리 DB/API 테스트를 작성한다. 실제 Flask/DB/브라우저 테스트는 이번 정적 스테이징 완료와 별개이며 실행하지 않은 검사는 통과로 보고하지 않는다.

관련 Task: ../../../../Tasks/2026/09/13/002_Roadmap_Batch_Staging_Task.md

관련 Report: ../../../../Reports/2026/09/13/002_Roadmap_Batch_Staging_Report.md
