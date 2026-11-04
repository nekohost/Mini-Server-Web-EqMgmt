---
artifact_id: TASK-20261104-012
work_id: RELEASE-20261104-USER-AI
owner: Codex
created_at: 2026-11-04
status: in-progress
---

# AI 도우미 운영 반영·실제 검증

사용자가 승인한 011 최종 후보를 운영 루트/Git/Linux 서버에 반영하고 실제 HTTP·모델 및 운영 브라우저 화면을 검증한다. 기존 업무 자료·다른 작업자의 dirty 변경·공유 Strata 서비스는 보존한다.

- [x] recorder/profile/context 및 현재 운영 호스트/HEAD/PID 확인.
- [x] 운영 관리자 브라우저 로그인 확인. 비밀번호는 사용자 직접 입력.
- [x] 운영 DB·환경 설정·AI 자료 백업 및 로컬 수신, 배포 전 사전 Validation.
- [ ] 승인된 파일만 운영 루트 병합·정적 대조·선택 commit/push. 병합·대조 완료, Linux 회귀 재실행 중.
- [ ] Linux pull/commit 대조·의존성·실제 DB 사본 격리 기동/보존 검증.
- [ ] 보호 설정/키 연결, 현재 프로세스 정상 종료 후 앱/자체 worker 적용.
- [ ] 실제 모델 응답·도구 조회·일반 사용자 경계·오류 및 운영 화면 screenshot 검증.
- [ ] 실제 결과/백업/복구·원본 보존·후속 Validation·완료 이력 기록.

현재 서버는 eqmgmt-backup의 `/home/nekohost/services/Mini-Server-Web-EqMgmt`, HEAD `cd93b1a61e130b6a7c1201414cf4a5aac15035c5`, 앱 PID 632016이다. 실제 조작 직전 다시 확인한다. sudo 무입력 인증은 불가하며 기존 Strata 키는 root 전용 파일에 있어 필요한 보호 키 연결은 준비 완료 후 사용자 직접 인증으로 처리한다.
