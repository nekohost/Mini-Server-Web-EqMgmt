---
artifact_id: PLAN-20261105-005
work_id: RELEASE-20261105-AI-UX
parent_work_ids: [STAGING-20261105-AI-UX-TRASH, STAGING-20261105-AI-COMPACT-LAYOUT]
owner: Codex
created_at: 2026-11-05
status: in-progress
---

# AI 도우미 승인 후보 운영 병합·배포

사용자 승인: “운영소스로 반영 및 서버까지 반영”. 검증된 현재 Staging 전체(기존1~7번 및 공간 절약 배치)를 Windows 운영 소스에 병합하고 GitHub의 승인 commit을 현재 운영 백업서버에 배포한다. 작업 owner는 장비관리이며 공유 Strata나 다른 서비스 요청을 제어하지 않는다.

1. 후보44개 fingerprint와 root baseline/현재 Git 변경을 확인하고 현재 서버 HEAD·프로세스·서비스·AI 요청 상태·설정 메타데이터를 읽는다. 비밀 값이나 대화/장비 내용을 출력하지 않는다.
2. 기존 대화/장비 DB의 온라인 일관 백업을 서버 private release 경로에 만들고, 실제 DB 사본에서 메뉴 재배치와 AI v3→v4 가산 이전·무결성·기존 행 보존을 확인한다. 현재 설정/메뉴/기존 키를 보존한다. 초기 설치용 activate는 이미 설치된 운영환경에 무조건 재사용하지 않는다.
3. 승인된 후보를 apply_patch로 root에 병합한다. template/CSS/JS 및 backend/v4/worker/guard를 같은 변경 단위로 적용하고 source hash·구문·관련 정적 검증을 수행한다. 배포 보조 수정이 필요하면 같은 Staging에 준비·검증한 뒤 병합한다.
4. 이번 변경만 commit/push한다. 기존 다른 dirty 변경은 보존하고 이력 원장은 원문/상태를 보존하며 해당 기능 완료를 추가한다. 해당 Staging 후보는 완전한 보존본·해시를 영구 산출물에 남긴 뒤 승인 병합 정리 범위에서만 정리하며 다른 Staging은 건드리지 않는다.
5. 서버에서 fast-forward pull/commit 일치를 확인한다. 신규 접수를 잠시 제한하고 장비관리 자체의 진행 요청을 정상 종료한 뒤 웹/워커를 같은 버전으로 전환한다. 정지 시 실제 PID·cwd·실행 파일·소유자를 확인하며 공유 모델을 중단하지 않는다.
6. private DB/epoch/환경 경로를 앱·워커·retention에서 일치시키고 v4·업무 행·설정/메뉴 보존과 health를 검사한다. 옛 장비관리 전용 Strata Nginx include는 정확한 백업 후 deny로 교체하여 nginx -t/reload하고, manifest의11개 옛 공개 자산만 보존본 뒤 회수한다. 키 파일·license/Git 이력·다른 사이트/공유 서비스는 유지한다.
7. retention timer는 v4와 정확한 private 경로를 검증한 뒤 설치·활성화한다. 기존 항목은 모두 상태를 확인하고 실제 만료 삭제가 있다면 대상과 원장/복구 경계를 별도로 확인한다. 사용자 장비 데이터나 기존 대화를 초기화하지 않는다.
8. 실제 HTTPS 로그인/익명 거절·관리자 메뉴·AI 목록·짧은 읽기 전용 대화·표·모바일/PC 화면·휴지통 표시를 확인하고 검증 PNG/상태를 보고한다. 로그인/sudo 등 사람이 반드시 수행할 입력만 필요할 때 요청한다.

복구는 현재 프로세스/환경/코드 commit·업무 DB/AI DB·메뉴/점유/epoch·삭제 결정 원장을 분리해 보존하고 새 요청 접수 전에 검증한다. v4 이후의 대화 삭제를 과거 DB 복원으로 무단 재노출하지 않는다. 운영 DB 조회·가산 migration·자기 서비스 재시작은 이번 명시 배포 승인과 기존 승인 기능을 적용하는 범위에서 수행한다.
