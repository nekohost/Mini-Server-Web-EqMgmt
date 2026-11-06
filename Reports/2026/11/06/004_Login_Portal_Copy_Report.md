---
artifact_id: REPORT-20261106-004
work_id: RELEASE-20261106-LOGIN-PORTAL-COPY
owner: Codex
status: completed
---

# 로그인·포털 문구 변경 검증

## 구현 전 Validation1~8

1. Recorder ensure 성공/watcher11268, profile legacy/runtime-session-mismatch·verified=false, validate1.8.1/44노드 오류0을 확인했다. context는 직전 작업에서 읽은 동일 버전32노드/3pack·필수 입력0으로, 기존9개 dirty를 보존하고 Staging부터 작업한다.
2. 로그인 표시 제목/브라우저 제목을 장비관리 시스템으로 맞추고 포털의 지정 안내 문단만 제거한다. 다른 화면 명칭이나 로그인/메뉴 기능으로 범위를 확대하지 않는다.
3. 정적 문구 변경이므로 새 테스트 없이 기존 Linux 템플릿 렌더/포털 화면 검사와 원문 대조를 수행한다. Python·JS 로직·상태·쿼리는 변경하지 않는다.
4. 두 템플릿만 운영에 반영한다. 현재 source/두 DB/환경/단위 백업과 실제 DB 사본 보존을 확인한 뒤 idle 자체 서비스만 전환한다.
5. 로그인 입력 필드·CSRF·인증·점검·비밀번호 재설정 조건은 그대로 보존한다. 계정/키/실제 데이터는 Git에 포함하지 않는다.
6. 검토 원문 ZIP/SHA와 이전 Git/source·현재 DB로 복귀할 수 있다. schema나 계정 설정 변경은 없고 정확한 이번 후보만 정리한다.
7. PC·모바일에서 제목과 제거한 문단을 확인하고 기존 입력 폼/메뉴의 동선·줄바꿈을 점검한다. 운영 일반 시험 계정으로 로그인 확인을 수행한다.
8. 별도 하위 에이전트·새 라이브러리·불필요한 전체 AI 시험을 도입하지 않는다. 실제 적용/검증과 진행 중 단계를 구분하고 기존 기록을 보존한다.

## Staging 검증·병합

로그인 h1과 브라우저 title을 바꾸고 포털 안내 p 한 개를 제거했다. Linux의 격리 Flask/Jinja 렌더에서 새 제목·안내 제거와 로그인 필드/포털 메뉴·위젯 유지를 확인했다. 생산 앱·DB는 열지 않았다. 기존 포털 회귀는390/1440px·light/dark4화면·272개 검사가 통과했다.1440px 화면도 시각 검토했다. [렌더 근거](004_Login_Portal_Copy/stage-render-verification.json),[포털 화면 검사](004_Login_Portal_Copy/stage-portal-browser/results.json).

검토 원문 두 템플릿과 기존 검증 entrypoint 총3개를 reviewed-source.zip(SHA256 a164248286006a7b6783f304d83298121e1da960afad9eeb79f1b9e15aa18f15)에 보존했다. 변경 템플릿2개만 root에 병합했고3개 원문 SHA가 root와 일치했다. 동일한 문구 변경이므로 별도 새 테스트나 전체 AI 회귀를 만들지 않았다. ZIP/후보/root를 대조한 뒤 정확한 후보3개만 정리했다. [원문 목록](004_Login_Portal_Copy/source-manifest.json),[병합·정리](004_Login_Portal_Copy/merge-and-cleanup.json).

## 운영 반영과 실제 화면

runtime commit `982b9ff100713d509fdbf75452a406209325ff22`를2026-11-06 14:29:37 KST에 활성화했다. 고정 release 경로 `20261105-ai-ux-copy-20261106T052608-27a684`의 이전 source·환경·단위·프로세스·두 DB14개를 현재PC 사용자 전용 사본과 SHA 대조했다. 실제 DB 사본의 업무18개·AI17개 테이블 및 기존 job50/메시지100/lifecycle7행과 감사 보존, 익명 인증 경계를 확인했다. 공유 모델이나 다른 서비스는 제어하지 않았다.

첫 배포 전 원문 대조에서 login.html의 Windows CRLF와 서버 Git LF의 바이트 차이로 검증이 중단됐다. 활성화 전에 원문 ZIP의 CRLF→LF 결과가 정확한 Git blob과 같고 서버의3개 파일이 그 blob과 같음을 재확인했다. portal/검증 entrypoint에는 차이가 없었다. 줄바꿈만 정규화해 대조했고 코드·문구·점수 기준을 바꾸지 않았다. [배포](004_Login_Portal_Copy/deployment.json),[백업 대조](004_Login_Portal_Copy/private-backup-verification.json).

운영 로그인 화면의 h1 `장비관리 시스템`과 브라우저 title `로그인 - 장비관리 시스템`을 확인했다.1280×720 PC·412×915 모바일에서 잘림/가로 넘침이 없고 기존 입력 폼·비밀번호 재설정·회원가입 동선이 보였다. 일반 시험 계정으로 실제 로그인해 포털에 도달했다. 메인 포털에는 지정 안내 문단이 없고5개 일반 메뉴/기존 장비 위젯이 유지됐다. 포털도 같은 PC·모바일 크기에서 가로 넘침 없이 확인했고 관측 console error0, viewport는1280×720으로 복원했다. 계정 설정이나 AI 요청을 생성하지 않았다. [UI 측정](004_Login_Portal_Copy/production-ui-verification.json),[로그인 PC](004_Login_Portal_Copy/production-login-pc.jpg),[로그인 모바일](004_Login_Portal_Copy/production-login-mobile.jpg),[포털 PC](004_Login_Portal_Copy/production-portal-pc.jpg),[포털 모바일](004_Login_Portal_Copy/production-portal-mobile.jpg).

검증 후 기존 업무/AI/감사 행 누락0·AI 기존 열 변경0을 확인했다. 업무 기존 행의 변경은 실제 로그인한 시험 계정의 SessionToken1개였다. 모든 계정의 PreferencesJSON/UpdatedAt은 정확히 같고 private 환경/세 단위 SHA가 유지됐다. web1086976/worker1086986·NORMAL·worker/retention active·active jobs/guards/예약0이었다. [보존 근거](004_Login_Portal_Copy/production-preservation.json).

## 구현 후 Validation1~8

1. 거버넌스: Recorder/profile의 legacy·verified=false 사유와1.8.1/44노드 오류0, 동일32노드/3pack·필수 입력0을 적용했다. 기존9개 dirty와 과거 untracked를 보존한다.
2. 의도: 로그인 표시/브라우저 제목과 지정 포털 문단만 변경했다. 다른 화면 명칭·인증/메뉴·위젯은 변경하지 않았다.
3. 논리: 격리 Linux 렌더와 기존 포털4화면272개 검사, root 대조와 실제 로그인으로 확인했다. 문구 변경에 새 단위 시험이나 전체 AI 회귀를 추가하지 않았다.
4. 운영: 현 백업14개 SHA/실제 DB 사본 보존을 확인한 뒤 idle 자체 web/worker를 전환했다. schema·외부 의존성·공유 모델 변경이 없다.
5. 보안: 로그인 폼·CSRF·세션 경계와 private 설정/키를 유지했다. 비밀 원문/DB를 Git 증거에 넣지 않았다.
6. 복구: 원문 ZIP/SHA·이전 Git/source·환경·단위·현재 DB를 서버/현재PC에 보존했다. 정확한 후보3개만 정리하고 원문 줄바꿈 차이는 명시했다.
7. UX: 운영 로그인/포털의 PC·모바일4화면을 촬영·검토하고 새 문구/안내 제거·입력/메뉴·가로 넘침 없음을 확인했다.
8. 메타: 불필요한 에이전트·새 기능·추가 AI 요청 없이 요청 범위만 완료했다. 완료 문서/증거는 한정 commit/push 후 서버 fast-forward로 동기화하며 runtime3개와 PID를 유지한다. 최종 동기화 영수증은 private release에 별도 보존한다.
