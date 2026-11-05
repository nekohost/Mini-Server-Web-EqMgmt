---
artifact_id: REPORT-20261105-021
work_id: RELEASE-20261105-AI-INPUT-RELIABILITY
owner: Codex
status: in-progress
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
