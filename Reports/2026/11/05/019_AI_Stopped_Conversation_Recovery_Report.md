---
artifact_id: REPORT-20261105-019
work_id: FIX-20261105-AI-STOPPED-CONVERSATION
owner: Codex
status: completed
approval: reported-operational-defect
---

# 중단된 대화 입력 잠금 진단·검증

최종 결과: 2026-11-05 18:53:19 KST 실행 commit `98c7ab61a1566892053499cbf26e6780b5236a19`를 운영에 반영했다. 서버의 종료 확인이 화면의 오래된 보내기 잠금에 반영되지 않는 경로를 재현·교정했고, 미확인 실행 차단은 유지한다. 기존 실패/대화 원문을 보존했다. 전체 새로고침 후 새 JS/CSS를 읽고 같은 대화에서 다음 지시를 보낼 수 있는 상태다. 사용자 브라우저의 직접 버튼 조작 결과는 이 보고 작성 시 추가 회신이 없어 확인했다고 주장하지 않는다.

nekohost의 `일반업무 세션` 마지막 요청이 STREAM_INCOMPLETE를 기록한 뒤 현재 failed/guard released인 것을 읽기 확인했다. 대화·추론·원래 오류는 보존돼 있으며 진행 요청/예약0, 현재 모델·xhigh 유효, 보관7,025자/64,000,000자다. 이 전환은018의 실제 own-request 종료 확인 뒤 이루어졌다. 이번 요청에서 DB/guard를 다시 변경하지 않는다. 관측 당시 서버 상태만으로 사용자 브라우저의 원인을 확정하지 않으며 버튼 상태/새로고침 결과를 추가 질의했다.

## 구현 전 Validation1~8

1. 거버넌스: recorder ensure 성공·legacy/runtime-session-mismatch와1.8.1 validate/context31개 및 pack 원문을 확인했다. Plan/Task019를 먼저 작성한다. Windows에서 앱을 import/실행하지 않고 source는 구조화 편집한다. 기존9개 tracked dirty와 untracked는 보존한다.
2. 의도: 중단된 기존 대화에서 다음 지시를 보낼 수 없는 결함을 조사하고 재현되는 클라이언트 잠금 경로를 교정한다. 기존 요청 자동 재실행이나 실패를 성공으로 바꾸는 작업은 없다.
3. 논리: lifecycle revision이 변하지 않는 job terminal 전환과 poll 지연/통신 실패, 선택 경합을 각각 검사한다. 오직 현재 인증 snapshot의 동일 job terminal 확인만 잠금 교정 근거로 쓴다.
4. 운영 영향: 정적 JS/template 중심의 변경을 우선하고 모델·큐·DB 스키마·worker는 유지한다. 기존 실행 요청에 전역 timeout을 추가하지 않는다. 동작 중인 외부 모델/다른 서비스는 제어하지 않는다.
5. 보안: 기존 소유자 GET/CSRF/account context와 선택 revision 검사를 따른다. UI의 확인 동작이 관리자 종료 ACK나 서버 guard 해제로 확대되지 않도록 전송 내역도 검사한다.
6. 복구: 후보 원문/SHA·기존 dirty 해시·운영 정적 자산 기준을 보존한다. rollback은 source만 복원하고 최신 대화·감사/삭제 원장은 과거 DB로 덮지 않는다.
7. UX: 중단 원인과 종료 확인 필요/확인 후 새 요청 가능 상태를 구분하고, 초안·추론 열림·검색 opt-in·스크롤 및 확인 재시도를 유지한다. 좁은 화면/테마 실제 Chromium 화면을 확인한다.
8. 메타: 사용자 화면의 정확한 재현 여부, 합성에서 발견한 경로, 현재 서버 확인을 구분해 보고한다. 과거 STREAM_INCOMPLETE 자체의 근본 원인은 이 진단만으로 단정하지 않는다.

## 재현·후보 검증

기존 production JS를 사용한 실제 Chromium390px/dark에서 동일 lifecycle_revision0의 recovery_required→failed snapshot이 들어와도 보내기 잠금이 남는 것을 재현했다. [수정 전 결과](019_AI_Stopped_Conversation_Recovery/before/results.json)의 `terminal snapshot releases stale composer lock timed out`는 의도한 실패이며 기존 root 소스는 당시 그대로였다.

Staging은 같은 job의 terminal snapshot 확인 때만 전체 저장 메시지를 다시 읽고 activeJob 잠금을 동기화한다. job 누락/미확인 종료/조회 실패는 잠금을 유지한다. 오류 영역의 읽기 전용 상태 확인과 선택/job별 poll 소유권을 보강했다. 초안·검색 opt-in·전체2994자 추론·추론 펼침을 보존하고 이전 poll이 늦게 와도 새 요청을 덮거나 막지 않는다. 관리자 ACK/cancel/guard 수정·자동 inference POST는 없다.

기존 오류 원문은 DB/감사에 그대로 남긴다. failed/STREAM_INCOMPLETE의 현재 화면에서는 더 이상 맞지 않는 마지막 ‘이전 요청의 종료 확인이 필요합니다.’ 안내만 현재 확인 결과로 대체하고 실패 사유는 유지한다. 종료 미확인 화면에는 기존 차단/관리자 문의가 계속 적용된다.

Staging Linux backend234개(실패/오류/skip0), 기존 UI4화면642개, 최종 회복 UI12화면204개를 통과했다. 마지막12화면은320/390/1440px×라이트/다크를 최신 template/이전 캐시 template에서 각각 실행한 결과다. 자산 배포 중 이전 template을 캐시한 web 프로세스에서도 JS가 동일한 상태 확인 제어를 보완한다. 실제 Chromium 프레임/화면으로 검사했고 실제 운영 계정·모델·DB는 쓰지 않았다.

첫 화면 검토에서 상태 확인 버튼의 여러 줄 접힘을 발견해 보존한 뒤, 버튼은 한 줄/최소36px, 좁은 영역은 줄바꿈하도록 보완했다. 최종320/390/1440px 다크 화면을 직접 확인했다. [390px](019_AI_Stopped_Conversation_Recovery/staging-compatible/screen-003.png),[1440px](019_AI_Stopped_Conversation_Recovery/staging-compatible/screen-005.png). 최종 후보6개 원문은 ZIP과 SHA256 manifest로 보존했다. 이 시점에서는 운영 반영 전이며 이어서 root 병합/동일 검증·정적 자산 반영을 수행한다.

## Root 병합과 반영 준비

검토 후보6개를 root에 구조화 병합하고 모든 파일의 SHA256이 ZIP manifest와 같음을 확인했다. merged-root Linux234개(70.988초/실패·오류·skip0), 회복 UI12화면204개, 기존 UI4화면642개가 통과했다. Python AST/JS 구문/scoped diff check도 통과했다. 새로운 테스트는 합성 snapshot·poll 경쟁을 검증하며 운영 inference 요청을 만들지 않는다.

기존9개 tracked dirty는 원본 해시와 대조했다. FEATURES/PROPOSALS는 이번 새 절 외의 원문이 같고, 나머지7개는 전체 바이트가 같다. Git index에는 새 절만 분리해 넣는다. 다른 untracked 파일과 서버의 기존 `.venv.incomplete-20260907/`는 보존한다. [보존 확인](019_AI_Stopped_Conversation_Recovery/dirty-preservation.json).

운영 이전3개 원문·job/메시지 해시·HEAD/PID 기준선을 private0700/0600 경로와 현재PC 사용자 전용 ACL 경로에 보존하고 tar/SHA·baseline JSON을 양쪽에서 일치시켰다. 이번에는 Python·DB·worker·maintenance를 변경하지 않는 정적 자산 배포다. 기존 template 캐시도 시험했으므로 web PID915380/worker PID915399를 유지한다. 새로고침 시 정적 자산의 HTTP `Cache-Control: no-cache` 재검증으로 새 JS/CSS를 읽는다. [백업 확인](019_AI_Stopped_Conversation_Recovery/private-backup-verification.json).

## 운영 결과와 사후 Validation1~8

서버는 정확한 실행 commit으로 fast-forward했고 JS/CSS/template3개의 파일 SHA와 공개 JS/CSS2개의 HTTP200/SHA가 검토 후보와 같았다. web PID915380/worker PID915399, NORMAL/worker active를 유지했고 재시작·진행 요청 중단은 없다. 해당 job은 failed/STREAM_INCOMPLETE·예약0으로 그대로이며 이전 오류 SHA와 두 메시지의 content/reasoning SHA가 private 기준선과 모두 같다. 실행 점유 guard0, tracked clean을 확인했다. 실제 nekohost 대화에 새 요청을 대신 보내거나 계정 cookie를 위조하지 않았다. [운영 검증](019_AI_Stopped_Conversation_Recovery/production-verification.json).

1. 거버넌스: Plan/Task→Staging→검증→원문/해시→root 동일성/재검증→운영 순서를 지켰다. 정확한 후보6개 파일만 정리했고 별도 기존 자료와9개 dirty를 보존했다.
2. 의도: 기존 대화에서 다음 지시를 못 보내는 화면 잠금 경로를 교정했다. 과거 모델의 불완전 응답은 실패로 유지하며 원래 질문을 자동 재실행하지 않는다.
3. 논리: 수정 전 실패를 재현한 동일 조건이 수정 후 통과한다. snapshot 누락/조회 실패/미확인 종료·지연 poll·다른 대화 전환·하나의 명시적 POST를 구분해 검증했다. backend234개와 UI846개 검사에 실패가 없다.
4. 운영: 검토 source3개와 공개 자산2개, 프로세스/PID/NORMAL을 확인했다. Python runtime/DB/worker·타 서비스 큐 변경과 전체 생성 timeout은 없다.
5. 보안: 소유자 인증 GET와 account/선택 경합 검사를 유지했다. 수동 확인은 admin ACK/cancel/guard release를 호출하지 않는다. 서버의 terminal 확인 없이 잠금을 해제하지 않는다.
6. 복구: 이전 운영 source3개를 양쪽 private 원문으로 보관했다. 적용이 필요하면 이전 정적 자산 commit을 복원하며 최신 대화·감사·삭제 원장을 과거 DB로 덮지 않는다.
7. UX: 원래 실패 사유와 현재 종료 확인 안내, 초안/검색/추론·수동 재시도를 유지했다. 버튼 접힘 문제를 보완하고320/390/1440px 라이트/다크 및 이전 template 캐시 화면을 확인했다.
8. 메타: 실제 DB/서비스/HTTP 검증과 합성 browser의 재현을 구분했다. nekohost 브라우저의 직접 재입력·실물 모바일 터치·과거 STREAM_INCOMPLETE 근본 원인까지 검증한 것으로 확대하지 않는다.

최종 원장은 FEATURES22·PROPOSALS의 이번 작업 절·운영 안내에 반영했다. 기존 미실현/보류 기능과 원래 실패 기록은 변경하지 않았다. 완료 증거 문서 commit은 실행 소스를 바꾸지 않고 서버에 동기화한다.
