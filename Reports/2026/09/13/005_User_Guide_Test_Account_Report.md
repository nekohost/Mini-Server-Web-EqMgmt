---
artifact_id: REPORT-20260913-005
work_id: WORK-20260913-USER-GUIDE-TEST-ACCOUNT
---

# 사용 가이드용 일반 사용자 계정 생성 검증

## 실행 전 상태

- 백업 서버 DB schema version 3, `integrity_check=ok`, 외래키 위반 0건, 사용자 2명.
- 후보 LoginId `guide_test_user`는 존재하지 않는다.
- users 테이블은 LoginId unique index를 가지며 Role·Password가 필수다. 이메일과 인증 이메일은 NULL을 허용한다.
- user 역할은 현재 허용 메뉴 4개를 가진다. 구체적인 메뉴 목록은 로그인 후 가이드 작성 과정에서 확인한다.

## Validation 1→8

1. 거버넌스: 기존 코드·스키마를 변경하지 않는 승인된 운영 데이터 추가다. Task를 먼저 만들고 보고서에 순차 검증한다. Staging 코드 후보가 없어 코드 Staging은 해당 없음이다.
2. 사용자 의도: 이메일을 수신할 수 없는 일반 사용자 테스트 계정을 만들어 관리자 계정만으로 볼 수 없던 사용자 화면을 문서화할 수 있게 한다. 관리자 권한을 부여하지 않는다.
3. 정적 논리: LoginId 충돌을 선검사하고 INSERT와 감사 로그를 단일 IMMEDIATE transaction으로 묶는다. 비밀번호는 `secrets`로 생성하고 Werkzeug 해시를 저장한다. WAL 상태에서도 일관된 사본을 위해 SQLite backup API를 사용한다.
4. 운영 영향: 사용자 1명과 감사 로그 1건만 추가한다. 코드·메뉴 권한·기존 계정·세션·DB 버전은 변경하지 않는다. 새 계정은 일반 사용자 기본 권한을 그대로 받는다.
5. 보안: 평문 비밀번호를 명령 출력·Git·보고서·대화에 기록하지 않는다. 서버 0700 디렉터리의 0600 파일에만 둔다. 이메일 필드는 NULL로 두어 타인의 주소를 사용하거나 인증 상태를 위조하지 않는다.
6. 복구: 변경 전 private 온라인 백업을 보존한다. 사용 전에는 참조가 없는 생성 계정과 생성 감사 행을 정확한 UserId로 제거할 수 있다. 사용 후 전체 DB를 과거 사본으로 덮어쓰지 않는다.
7. 휴먼 에러: 일반 계정임을 이름·닉네임에 표시하고 고유 LoginId를 사용한다. 자격증명 경로만 사용자에게 안내한다. 비밀번호를 잊으면 관리자 비밀번호 초기화 기능을 사용한다.
8. AI 메타: 계정 생성 목적과 실행 범위를 문서화하며 실제 평문 비밀번호와 기존 사용자 정보는 기록하지 않는다. 생성 검증과 향후 브라우저 사용 가이드 검증을 구분한다.

판정: 차단 조건 없음. 온라인 백업 후 계정 생성 가능.

## 실행 결과

- 생성 계정: UserId 3, LoginId `guide_test_user`, Role `user`, 활성·미삭제 상태.
- Email과 `notification_verified_email`은 NULL이다. 타인 이메일이나 허위 인증 상태를 만들지 않았다.
- 계정 INSERT와 `REGISTER` 감사 로그 1건을 한 트랜잭션으로 기록했다. 기존 사용자는 2명에서 3명으로 증가했다.
- 비밀번호는 Werkzeug 해시 검증을 통과했다. 평문은 출력하지 않았으며 아래 0600 자격증명 파일에만 있다.
- 자격증명: `/home/nekohost/.local/share/mini-server-eqmgmt/test-accounts/guide_test_user.credentials` (0600, 상위 디렉터리 0700).
- 변경 전 온라인 백업: `/home/nekohost/.local/share/mini-server-eqmgmt/test-accounts/backups/equipment-before-guide_test_user-20260913T124855-2b484480.db` (0600).
- 생성 후 `integrity_check=ok`, 외래키 위반 0건. DB schema version 3을 유지했다.
- 실제 `https://nekohost.org` 로그인 GET/POST 200 및 로그인 성공을 확인했다. 포털에는 `my_equipment`, `public_equipment`, `dashboard` 세 메뉴가 노출됐다.
- `/admin_center` 직접 접근은 권한 거부 스크립트와 포털 복귀만 반환했고 관리자 템플릿은 노출하지 않았다. `/api/users`는 403을 반환했다. 검증 세션은 로그아웃했다.

## 결론

일반 사용자 사용 가이드 작성용 계정 생성과 권한 검증이 완료됐다. 이메일 인증·비밀번호 찾기·기한 알림 수신은 이 계정의 시험 범위가 아니다. 자격증명은 Git과 대화 기록에 포함하지 않는다.
