---
artifact_id: REPORT-20261106-004
work_id: RELEASE-20261106-LOGIN-PORTAL-COPY
owner: Codex
status: in-progress
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
