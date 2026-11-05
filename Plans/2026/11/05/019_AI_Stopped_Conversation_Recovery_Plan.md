---
artifact_id: PLAN-20261105-019
work_id: FIX-20261105-AI-STOPPED-CONVERSATION
owner: Codex
status: completed
approval: reported-operational-defect
---

# 중단된 AI 대화의 보내기 잠금 복구

사용자가 nekohost 대화의 STREAM_INCOMPLETE 안내 이후 보내기 버튼이 동작하지 않는 결함 확인을 요청했다. 본인 대화와 현재 서버 상태를 읽기 진단하고, 재현되는 클라이언트 동기화 결함을 필요한 범위에서 수정·검증한다. 관련 AI 기능의 운영 반영 승인은 이전 지시를 따른다. 다른 사용자나 외부 서비스의 요청 종료를 추측하거나 취소하지 않는다.

## 확인한 사실과 재현 범위

`일반업무 세션`의 마지막 요청은 현재 failed/STREAM_INCOMPLETE이며 guard released, 예약0이다. 이전018 작업에서 해당 own-request의 실제 종료를 확인한 뒤 안전한 기존 절차로 해제됐다. 대화·오류·추론 기록은 보존돼 있다. 모델과 xhigh 설정은 유효하고 보관량/빈도 제한도 원인이 아니다. 사용자 화면의 실제 버튼 상태는 추가 확인을 요청했으며, 서버의 현재 상태와 사용자가 보던 화면을 동일하다고 단정하지 않는다.

현재 클라이언트의 주기/포커스 상태 확인은 제목·휴지통 revision만 비교한다. job이 recovery_required에서 failed로 바뀌고 lifecycle_revision이 그대로면, job polling의 통신 실패/중단이 남은 화면을 교정하지 않는다. 이 조건을 실제 후보 DOM과 합성 전송에서 먼저 재현한다. 새로 열 때 이미 failed인 경우, 계속 recovery_required인 경우, 종료 확인 후 다음 요청, 이전 poll 지연, 다른 대화 전환을 구분한다.

## 구현 계약

1. 현재 로그인 소유자의 서버 snapshot에서 **동일한 선택 대화·동일 job의 terminal 상태가 확인된 경우만** 오래된 activeJob 잠금을 동기화한다. unknown/running/draining/recovery_required 또는 snapshot에 없는 job은 추측해 해제하지 않는다.
2. 오류 영역의 읽기 전용 `상태 다시 확인`으로 재동기화 경로를 제공한다. 자동 재전송·새 추론·관리자 ACK·guard 수정은 하지 않는다. 통신 실패 이유는 남기며 버튼은 재시도 가능해야 한다.
3. 동기화 시 작성 중 초안·검색 opt-in·읽던 위치/추론 펼침을 유지한다. 미완성 응답·오류를 정상 완료로 바꾸지 않는다. 종료 확인 전에는 잠금 이유를, failed 확인 후에는 새 요청이 가능함을 구분해 설명한다.
4. 이전 선택의 지연된 poll이 새 선택/다음 job의 조회를 막거나 덮어쓰지 않도록 poll 소유권을 선택/job 단위로 제한한다. 모델 생성 시간 제한은 추가하지 않는다.
5. Staging→실제 Linux 합성/스크린샷→원문·SHA 보존→root 병합/동일 검사→정적 자산 운영 반영으로 수행한다. Python/DB/worker의 수정·재시작 없이 가능하면 유지한다. 기존 dirty 자료는 전부 보존한다.

## 검증

실패/정상/미확인 종료·snapshot read 실패·오래된 poll·대화 전환·초안/출처 보존·한 번의 명시적 제출만 발생함을 실제 Chromium에서 검사한다. 기존 UI와234개 Linux 회귀도 확인한다. 운영에서는 해당 대화 상태/서비스·자산 SHA를 읽기 확인하고, nekohost 계정을 위조하거나 이전 요청을 자동 재실행하지 않는다. 배포 rollback은 이전 정적 자산 commit을 복원하며 최신 DB를 되돌리지 않는다.
