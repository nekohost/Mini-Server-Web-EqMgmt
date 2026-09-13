---
artifact_id: REPORT-20260913-003
work_id: WORK-20260913-ROADMAP-BATCH-RELEASE
created_at: 2026-09-13T12:05:36+09:00
---

# 제안 일괄 운영 반영 검증

## 진입 및 범위

recorder ensure 성공. validate 43노드, 오류0/경고0. 첫 context는 `UNMATCHED_PATH: scripts`로 실패하여 일반 구현을 시작하지 않고 catalog/router와 실제 경로를 조회했다. 루트 scripts/는 없고 운영 CLI는 tools/database_release.py에 있다. 새 CLI 두 개의 실 배치 대상을 기존 tools/로 정정하며 규칙을 수정하지 않는다. validate와 전체 intent를 유지한 새 context 성공 후 세 pack의 모든 노드를 읽었다.

현재 사용자의 승인 범위: 기존 스테이징 제안 8묶음의 운영·Git·백업 Linux 적용 및 그 검증/수정 반복. 실제 데이터 삭제/초기화, 무관한 Staging 삭제, 주 서버 배포, systemd 전환은 하지 않는다.

읽기 전용 서버 점검: 기준 commit 일치, tracked clean, 기존 untracked 두 항목 보존. 기존 PID 55646/cwd/executable 확인. DB v2, integrity ok, FK 위반0, 사용자2/장비1/옵션1/노드12/감사5, 상태 ACTIVE1, Flask3.1.3, 여유 약95GB. 비밀과 사용자 행 내용은 출력하지 않았다.

검증과 실행 결과는 아래에 실제 수행 순서대로 추가한다.

## 병합 전 Validation 1→8

1. 거버넌스: recorder/validate/context 재개 조건 충족. Staging overlay와 운영 소스를 분리하고 apply_patch로만 편집한다. tools/ 정정은 실제 운영 도구 위치를 따른 것이며 미등록 작업을 다른 이름으로 숨기거나 규칙을 축소하지 않는다. Flask는 이미 설치된 3.1.3을 사용하여 의존성 추가 설치가 필요 없다.
2. 사용자 의도: 9개 제안 번호/8묶음 구현을 백업 서버까지 반영한다. 기존 제조사·공식 모델명·수정 선택·옵션 관리·점검/DB 백업 보존을 회귀 대상으로 한다. 다른 계획은 건드리지 않는다.
3. 정적 논리: 상태 revision, SQLite writer transaction, 인증 두 버킷, 필터 AND 권한, CSV 확정 재검증, 파일 보상·원본 보관, 발송 UNKNOWN을 검토했다. 기존 tools/database_release.py는 v2 down과 테이블 전체 동일 비교를 전제로 하므로 v3에서 거짓 실패/부적절한 down을 유발한다. 새 테이블 존재를 허용하되 기존 테이블 원래 컬럼 지문을 엄격 비교하고 v3 down 거부를 확인하도록 Staging에서 보정한다. 사본 앱의 첨부 경로도 격리한다.
4. 운영 영향: app import가 migration을 수행하므로 Linux 실제 DB 실행 전에 반드시 임시 DB 전체 회귀와 온라인 사본 보존 검증을 거친다. v3 변경을 원자적 커밋으로 배포하고 Git HEAD를 대조한다. 기존 수동 실행을 유지하고 검증된 정확한 PID만 교체한다.
5. 보안/경계: 새 변경 API의 로그인/CSRF/DB 역할 재확인, 파일명/용량/권한, CSV 수식·승인 카탈로그 검증, 인증 만료 한도를 확인했다. 공개 장비의 내부 상태 이력은 owner/admin만 받는다. 프록시 실제 경로와 메일 설정은 비밀 값을 출력하지 않고 서버에서 확인한다. 서명 검사를 백신 검사로 주장하지 않는다.
6. 복구: private online snapshot, 기존 업무 컬럼 지문, transaction rollback 및 v3 down 거부를 사용한다. 신규 기한·파일이 생긴 뒤 구버전 DB로 덮어쓰지 않는다. 테스트 실패는 서비스 변경 없이 Windows 후보 보정 후 재배포한다. Staging README/manifest는 Reports에 보존하고 이번 후보만 구조화 삭제한다.
7. 휴먼에러: 미리보기→명시 확정, 상태 사유/revision, 삭제 후 원본 보관, 잘못된 날짜/스킨 오류와 수신 동의 기본 false를 확인했다. 서버 테스트로 권한·재시도·경합을 실행 검증하고 브라우저 실사용 여부는 별도로 보고한다.
8. AI 메타: 별도 세션 위임 없이 Codex가 기존 실행을 승계한다. 현재 검사 결과와 미실행 Linux 테스트를 구분하며 사용자 데이터를 시험용으로 변경하지 않는다. 추가 확인 질문은 하지 않지만 실패를 성공으로 바꾸지 않고 동일 승인 범위 안에서 보정한다.

판정: CLI 경로 및 배포 검사 v3 호환 보정 후 정적 검사·소스 승격 진행 가능. 서비스 적용은 Linux 검증 통과까지 보류한다.

## 운영 소스 승격

기준선 SHA 35개 항목 대조 후 후보29개를 구조화 병합했다(원래28 + v3 배포도구1). Staging JS/VM 31/31, SSH stdin AST17/Jinja8 구문 통과(app import 없음), 운영 루트 JS/VM31/31, diff --check 통과. CRLF/LF 정규화 후 운영29개와 후보가 완전히 동일함을 대조했다. 입력 직렬화/도구 출력 크기 문제로 구문 검사·소스 읽기를 재시도한 일이 있으나 미확인 내용을 병합하지 않았다.

README/manifest는 이 Reports 폴더의 003_Roadmap_Batch_Release_Contract.md 및 003_Roadmap_Batch_Release_Manifest.json으로 영구 보존했다. 이번 Staging 후보37개만 apply_patch로 정리했다. 무관한 기존 Staging은 유지하며 구현은 운영 소스와 Git 이력으로 복구 가능하다. Linux 실행 결과는 아직 대기 중이다.

## Linux 검증

a08f52b551b358d5c5f5457f94e4617e3fa7b9b4 commit/push 및 백업 서버 fast-forward pull/HEAD 일치 완료. 격리 unittest 86/86 PASS(13.557초). 출력의 의도된 감사 실패·복원 실패 주입은 성공 시험에 포함되며 운영 장애가 아니다. 임시 파일 ResourceWarning 1건은 시험 정리 경고로 남았고 테스트 실패는 없다.

실제 DB 온라인 사본 `release-check-20260913T031253Z-957ab0e01b2642058f407ec263a6519f.db`에서 v3 앱 초기화, 기존16개 테이블 모든 원래 컬럼/행 지문 일치, integrity/FK, v3 down 거부, migration 반복 no-op PASS. 사본은 private releases/roadmap-20260913 아래 보존한다. 운영 DB는 아직 v2이며 기존 프로세스를 유지했다.

메일 환경 4개 키가 구성되었음을 값 노출 없이 확인했고, 서버 시간대 +09:00 및 cron active/기존 사용자 crontab 없음 확인. 매일09:00 기한 알림의 고정 템플릿을 tools/에 추가한다. 이 기능의 예약 가동이며 제외한 systemd 서비스화는 하지 않는다. 실행 전 dry-run, 수신 동의/인증 주소 조건, 설치 직전 기존 crontab 재확인과 백업을 적용한다. 알림 CLI의 lock/점검 검사로 복원 중에는 발송하지 않는다.

변경 영향 Validation 3→8 재검토: 예약 명령은 검증된 정확한 Python/DB/점검 경로만 호출(3); 기존 실행/시간대 유지(4); umask077/비밀 미기재/명시 동의만 발송(5); 기존 crontab private 사본 및 식별자 줄만 제거 가능한 복구(6); 자동 재시도 중복 없음(7); 예약 가동과 실제 발송 건수를 별도 보고(8).
