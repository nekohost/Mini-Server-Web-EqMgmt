---
artifact_id: REPORT-20261105-021
work_id: RELEASE-20261105-AI-INPUT-RELIABILITY
owner: Codex
status: completed
approval: explicit-end-to-end-and-subagents
---

# AI 입력·응답 신뢰성 검증

기준 HEAD는5fa8f23이다. 사용자는 계획·Staging·검증·운영 적용·운영 검증과 GPT-6.1 Sol Max/xHigh 협업을 명시 승인했다. 이전020의 Google 미해결 항목은 별도 상태로 유지한다.

## 구현 전 Validation1~8

1. 거버넌스: recorder ensure 성공/watcher11268, legacy/runtime-session-mismatch(verified=false),1.8.1 validate44노드 오류/경고0,context34노드/3pack/requiredInputs0을 읽었다. Plan/Task부터 작성하며 현재9개 기존 dirty와 untracked를 보존한다. source 편집은 apply_patch, Staging 우선, Windows 앱 import 금지를 따른다.
2. 의도: 버튼의 전체 hit 영역, 계정별 Enter 설정과 Shift 반대 동작, nekohost의 실제 실패 개선이 전부 범위다. 기본 Enter는 줄바꿈이다. 기존 자동 검색/소유자/감사·업무 확인을 유지하고 불필요한 다른 기능은 확장하지 않는다.
3. 논리: 겹침/레이아웃·submit/keydown 순서와 IME·반복/중복/진행 중 상태를 검사한다. 설정 변경은 다른 사용자/현재 접수 snapshot에 영향을 주지 않으며 실패 원인별로 회귀를 추가한다.
4. 운영: 기존 계정 설정 경로를 우선 재사용한다. schema 변경은 필요가 확인되면 추가 방식만 사용하고 현재 DB 사본에서 기존 행/감사를 보존하는지 확인한다. 실제 Linux 기동 전 임의 서버 즉석 수정을 하지 않는다.
5. 보안: 설정은 인증된 현재 사용자에 한정하고 고정 enum·CSRF를 검증한다. 키보드가 기존 비활성/접수/권한을 우회하지 않게 한다. 실패 진단은 해당 계정의 필요한 구조/오류만 읽으며 인증값·대화 사적 원문을 Git에 남기지 않는다.
6. 복구: 변경 전 source/dirty 기준과 보존 원문/SHA를 남긴다. 현재 운영의 source·설정·DB를 private 백업하고 실패 시 최신 데이터/감사를 유지하는 코드 롤백을 사용한다. 실제 사용자 요청을 임의 취소/재실행하지 않는다.
7. UX: 버튼 전체 영역·모바일 터치, Enter/Shift 안내·IME 오전송, 저장 여부·설정 유지·진행 중 초안·오류 후 보내기 회복과 PC/모바일 화면을 확인한다. 최소 높이 미만의 기존 스크롤 계약은 유지한다.
8. 메타: 요청한 모델/추론 수준으로 분담하고 각 에이전트의 preflight와 파일 경계를 확인한다. 합성/실제 모델·원인 수정/잔여 공급자 제한을 구분해 기록하며 실패를 숨기거나 무조건 성공을 약속하지 않는다.

## 조사와 구현 범위 확정

GPT-6.1 Sol xHigh는 버튼/template/CSS, Max는 개인 설정/키보드, Max는 읽기 전용 실패 진단으로 나눴다. 각 recorder/profile/validate/context와 부모 문서를 확인했고 하위 profile은 legacy/runtime-thread-id-conflict(verified=false)였다. [계정 한정 진단](021_AI_Input_Reliability/diagnosis/scoped-failure-diagnosis.md)은 nekohost 전체11작업 중 chat10(done6/failed3/cancelled1)·probe1done,020 배포 이후 새 작업0을 확인했다. 최근 과거 실패는 검색 없는 required 완료, 검색1회 후 추가2회 batch, 스트림 ValueError이며 최신020 회귀라고 단정하지 않는다. 당시 종료 미확인 보존까지 포함한808.696초를 프리필 timeout으로 해석하지 않는다.

설정은 기존 user_settings.PreferencesJSON에 ai_enter_action=newline/send를 추가하고 schema/app.py 변경 없이 현재 사용자 설정 API로 저장한다. nekohost는 system/edge, test05는 설정 행이 없어 기본 standard라는 차이를 버튼 검증에 포함했다. 부모 IAB의 기본 PC/mobile 접힌 상태9개 hit-test는 모두 button/child였고 현재까지 사용자가 본 부분 클릭 문제를 직접 재현했다고 주장하지 않는다.

검색 실패 개선은 동적 잔여 횟수·한도0 도구 제거, 검색 전용 batch의 한 단계1회 실제 I/O와 나머지 미실행 제어 결과로 한정한다. 총 횟수/예산을 늘리지 않고 원본 호출·실제 결과·미실행을 구분한다. mixed 업무 batch는 기존처럼 실행 전에 거부한다. SSE는 명시적 종료 표식의 EOF 경계만 검사/보완하며 표식 없는 스트림은 미확인 종료로 유지한다. 구 오류 기록은 보존한다.

## 통합 검사와 폴드 외부 화면 보완

첫 통합 Staging은265개 backend/58.613초·오류/실패/skip0을 통과했다. input-preferences8화면384개, hitbox12화면1,152개, 기존UI16화면2,538개도 통과했다. 이후 교차 검토가 찾아낸 최초 목록 지연과 새 대화 생성 지연의 전송 경합을 별도 회귀로 보완했다. 현재 source는 최초 자동 열기를 시작 시 선택/사용자 동선과 연결하고 새 대화 생성 중 composer 잠금을 즉시 적용한다. 이 JS 수정과 다음 모바일 보완 후 영향 화면은 다시 검사한다.

사용자는 갤럭시 Z 폴드7 외부 화면·확대 없음이라고 답했다. [삼성 공식 스펙](https://www.samsung.com/sec/smartphones/galaxy-z-fold7/specs/)의 외부6.5인치/1080×2520은 물리 규격이며 CSS viewport는 브라우저·밀도·도구막대에 따라 다르므로 직접360/384/412/430px를 검사한다. iframe 크기만 바꾸던 기존 fixture와 달리 실제 top-level 모바일 CDP/touch를 사용했다. 설치된Chromium152는 최신 tip-of-tree의 가상 키보드 geometry override를 구현하지 않았고 viewport crop/visible-size만으로 JS visualViewport가 줄지 않았으므로 키보드 실재현으로 계산하지 않았다.

실제 모바일 viewport 자체를 줄인4화면(360/384 light,412/430 dark·양 skin)에서 재현했다. 412px·12줄 입력·540px 높이에서는 viewport 가용439px보다 기존 최소575px가 커 전송 버튼이 y555.91~599.91에 있어0/9 hit였다. 높이576px에서는 상단 터치1건·하단 터치0건으로 요청한 부분 클릭 형태를 확인했다. 문서 자체를 스크롤하면 모두 복구되지만 대화 내부 스크롤은 전송부를 드러내지 않았다. 이 축소 높이 원인을 수정하며 물리 삼성 키보드가 직접 원인이었다고 단정하지 않는다.

최종 viewport 함수는 모바일 composer 포커스·배율1 조건에서 실제 가용 높이를 사용하고 대화48px·입력 최소52px를 확보한다. 412×540에서 assistant439px·입력96px·대화48.77px·보내기 y419.91~463.91로44px 전부를 보이는 영역에 둔다. 터치 종료 직후 크기 잠금을 풀면 합성 click 전에 버튼이 이동하는 추가 결함을 발견해 native activation까지 유지했다. 취소·외부 종료·blur 정리와600ms UI 유실 복구는 모델 생성 제한과 무관하다. 최종384/412 dark·두 skin의184개,320/412/1440 light/dark의582개 버튼 검사를 통과했다. 이전 실패 화면과 결과도 보존한다.

개인 설정은 기존 현재 사용자 JSON에서 다른 키를 유지하며 고정 enum만 원자적으로 변경한다. 기본 Enter 줄바꿈/Shift+Enter 보내기와 반대 설정, IME 조합·반복·변경 중 잠금·접수 snapshot·뒤늦은 목록·새 대화 생성 경합을 회귀로 검사했다. 실제 한국어 하드웨어 IME 검증으로 확대하지 않는다. 최종 통합 영향 검사로 input412의118개, viewport142개, 기존UI642개, 회복144개를 통과했다. 일부는 마지막 pointer activation 수정 전 검사이며 최종 원문에서는 버튼184+582를 다시 확인했다.

통합 원문18개를 reviewed-integration-source.zip(SHA256 6367fe9acf64b9e238c855e74e04b78a6d5a21dd5717cfc1b12fc565e17aa8a6)에, 구성요소33개를 별도 ZIP/manifest에 보존했다. root18개가 원문 hash와 모두 일치하고 Python AST/JS 문법 검사 및 Linux265개 전체 검사를50.152초·실패/오류/skip0으로 통과했다. 정확한 manifest 경로·SHA를 확인해 이번 후보 파일만 정리한다. 이 검사는 실제 운영 DB를 열지 않는다.

## 운영 배포와 실제 검증

런타임 commit715bc40fef7b849071ec8dbf2f7af3271478a187을2026-11-05 23:31:02 KST에 활성화했다. 장비관리 자체의 미종료 작업0을 두 번 확인한 뒤 web/worker만 전환했다. Strata·다른 서비스는 제어하지 않았다. [배포 결과](021_AI_Input_Reliability/deployment.json)의 web990847/worker990857, NORMAL·worker/retention active를 확인했다. 새 schema는 추가하지 않았고 AI v4를 유지했다.

private release `20261105-ai-ux-input-021-20261105T142934-2718ff`에 이전 코드·환경/설정·세 단위·두 DB·프로세스 환경을 보존했다. 현재PC 사용자 전용 `C:/Users/nkhst/.codex/private-releases/`의 같은 이름 사본14개가 서버 원본 SHA와 전부 일치한다. private 내용은 Git에 넣지 않았다. 실제 두 DB 사본 기동에서 업무18개/AI17개 테이블과 기존 lifecycle3행·감사·모든 구 AI 행을 보존했고 접수 재개 전 원본도 다시 대조했다. [비공개 백업 대조](021_AI_Input_Reliability/private-backup-verification.json).

test05의 일반 UI에서 Enter=send/Edge를 저장하고 reload 유지, Shift+Enter 줄바꿈과 Enter 전송을 확인했다. 이후 newline으로 저장해 Enter 줄바꿈/Shift+Enter 전송을 확인했다. 마지막 standard/newline으로 복원하고 재로그인 유지까지 확인했다. test04는 설정을 변경하지 않고 기본 standard/newline을 확인했다. API 합성 검사의 두 계정 권한·CSRF·고정 enum·다른 JSON 키 보존과 실제 UI 검증을 구분한다.

| 실제 검증 요청 | 입력 방식/구성 | 결과 | 접수~완료 |
|---|---|---|---:|
| 공개 합성 인사 | Enter 보내기, Qwen3.8 Flash Next/off | 단일 job done, 검색0회 |12.288초|
| 공개 Flask 저장소 검색 | 기본 모드 Shift+Enter, 같은 모델/off | 단일 job done, 실제 GitHub 출처3건·공식 저장소 답변 |16.247초|
| 12줄 모바일 입력 | Edge·412×540·배율1, 보내기 하단350/486 클릭 | 단일 job done, 검색0회·확인 응답 |14.103초|

위 시간은 자동 검색 판단을 포함한 두 모델 단계와 내부 접수 대기를 합한 요청 전체 시간이다. 실제 모델은 이번 세 요청에서 다중 검색 batch를 만들지 않았으므로 그 실패의 재현/수정 판정은 표적 회귀에 따른다. 실제3개 모두 error_code=null, reserved_chars=0, guard released이며 전체 미종료 작업도0이다. 구 사용자 job을 재실행하거나 실패 기록을 바꾸지 않았다. [실제 요청/입력 증거](021_AI_Input_Reliability/production-verification.json).

운영의 긴 입력·412×540 화면은 가용439px에 assistant439px·입력160px, 보내기 y445.5~489.5/44px로 맞았다. 버튼 안9/9 지점이 가려지지 않았으며 실제 하단 클릭으로 한 번만 접수했다. 412×915 모바일·1440×900 PC·개인 설정을 눈으로 검토했다. 최종 보이는 축소 화면은 기본 Standard에서도 별도 저장했고 시험 초안과 임시 viewport를 해제했다. [축소 높이](021_AI_Input_Reliability/production-mobile-compact.jpg),[모바일](021_AI_Input_Reliability/production-mobile.jpg),[PC](021_AI_Input_Reliability/production-pc.jpg),[개인 설정](021_AI_Input_Reliability/production-personal-settings-final.jpg). 물리 단말·삼성 키보드를 직접 조작한 결과는 아니다.

[운영 무결성](021_AI_Input_Reliability/production-integrity.json)은18개 소스와 공개 CSS/JS3개의 SHA 일치, private 설정/단위 불변, 구 업무/AI 행 유실0·감사 보존을 확인한다. 검증 후 바뀐 구 업무 값은 두 시험 계정 로그인 SessionToken, AI는 연결 확인 시각2개·정상 출력의 문자 사용량1행뿐이다. 장비 업무 행과 기존 대화/job/실패/출처는 그대로다. Google 미해결·공급자/모델의 불완전 응답 가능성과 과거 ValueError의 정확한 종료 형태 불명은 유지한다.

## 구현 후 Validation1~8

1. 거버넌스: 승인된 분담·Staging 우선·원문18/구성33개 ZIP·hash·정확한 후보33개 정리·root 검증을 완료했다. 기존9개 dirty 원문과 과거 untracked는 이번 commit에 넣지 않는다.
2. 의도: 모바일 부분 클릭, 기본/선택 Enter 동작, 계정 실패 진단과 확인된 제어 결함을 구현·운영 검증했다. 다른 보류 기능은 확장하지 않았다.
3. 논리: 한 번의 접수·IME/반복/상태 잠금·지연 목록/새 대화 경합, 실제 검색/미실행 구분·전체2회/단계1회·명시적 EOF 종료를 회귀로 검증했다. 실제3요청도 단일 접수/종료를 확인했다.
4. 운영: Linux에서만 실제 앱을 실행하고 현재 DB 사본18/17개와 원본의 구 행을 보존했다. schema4·키/단위·같은 DB 경로·worker/retention active·NORMAL을 확인했다.
5. 보안: 현재 사용자 설정 enum/CSRF·JSON 병합과 검색 권한/민감 값/취소/휴지통을 유지한다. 인증값·진단 사적 원문은 Git에 넣지 않고 감사 원문과 구 실패는 보존한다.
6. 복구: 이전 source/설정/두 DB와 현재PC private 사본14개·SHA를 확보했다. 사용자 요청/외부 서비스는 취소하지 않았으며 롤백이 필요할 때 구 코드와 최신 데이터를 보존할 기준을 마련했다.
7. UX: 최종 모바일184개·일반 버튼582개와 운영 PC/모바일/개인 설정·저장/reload/재로그인·기본/반대 키·하단 클릭/입력 복귀를 확인했다. 물리 폴드7와 실제 한국어 IME는 별도 미검증으로 둔다.
8. 메타: 요청 모델/추론 override로 분담했으나 runtime profile 검증 실패를 모델 확정 증거로 사용하지 않는다. 모든 과거 실패가 제거됐다고 주장하지 않고 원인 불명 스트림/Google·외부 공급자 한계를 구분한다. 최종 문서 commit은 같은 런타임 hash를 유지하는 ff-only 동기화로 마무리한다.
