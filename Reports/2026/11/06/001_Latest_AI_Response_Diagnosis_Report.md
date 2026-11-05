---
artifact_id: REPORT-20261106-001
work_id: DIAGNOSE-20261106-LATEST-AI-RESPONSE
owner: Codex
status: completed
scope: read-only-production-diagnosis
---

# 가장 최근 AI 요청 중단 원인 진단

사용자는 nekohost의 가장 마지막 질문에 응답이 없었던 원인 조사를 요청했다. 운영 상태·해당 계정의 대화/job/step/guard 및 정확히 연결되는 로그를 읽기 전용으로 조사한다. 실제 질문 원문·추론·검색어·인증값은 이 공개 문서에 복사하지 않는다. 코드/설정/DB 수정·요청 재실행/취소·종료 ACK·모델/서비스 제어는 범위에 포함하지 않는다.

Recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate44노드 오류/경고0, context24노드/2pack/requiredInputs0 및 capability를 확인했다. profile 명령의 첫 잘못된 파일 경로는 MODULE_NOT_FOUND로 실패했고, AGENTS의 정확한 governance-tool profile 명령으로 정정해 성공한 뒤 진행했다. 기존9개 dirty와 과거 untracked를 보존한다.

진단 순서는 최신 소유 질문 식별→현재 실행 상태/출력량→정확한 job 로그/코드 계약→원인·잔여 영향·조치의 증거 대조다. 검증1~8은 결과와 함께 기록한다.

## 결론

조사 당시 nekohost의 최신 질문은 일반업무 세션의 두 Qwen 모델 비교표 요청이었다. job `a7a1641800fd4fa0849e2c245893ed08`, user message107/assistant message108, conversation `7453b790d9cc4f619afb53e6f8cbeeae`로 연결된다. 질문·추론 원문은 이 문서에 포함하지 않는다.

모델의 첫 자동 검색 판단 단계가 구조화 도구 호출 없이 종료되어 서버가 `WEB_SEARCH_PLAN_REQUIRED`로 즉시 실패 처리했다. 직접 원인은 worker가 보고한 complete 결과의 calls=[]이며, 서버가 요구한 정확히1개의 plan_web_search 호출과 맞지 않는 것이다. 모델/상위 Strata가 그 호출을 누락한 더 깊은 내부 이유는 장비관리 측 로그만으로 확정할 수 없다. 원본 SSE 종료 사유나 실제 wire 요청 전체를 보관한 추적은 확보하지 않았다.

| 항목 | 확인값 |
|---|---|
| 접수 |2026-11-06 00:05:45.272696 KST|
| 종료 |2026-11-06 00:05:57.077071 KST|
| 접수~종료 |11.804초|
| 연결/모델 |Strata / qwen3.8-flash-next-iq3_xxs|
| 추론 수준 |xhigh|
| 자동 검색 |auto·allowed=true|
| 첫 claim |required_tool=plan_web_search, tools=[plan_web_search], messages17, max_tokens4096|
| worker 완료 보고 |outcome=complete, calls0, content0자, reasoning741자|
| 서버 판정 |failed / WEB_SEARCH_PLAN_REQUIRED|
| 저장된 오류 |AI가 질문의 검색 필요 여부를 확정하지 못해 이 작업을 중단했습니다. 잠시 후 다시 요청해 주세요.|
| 잔여 상태 |reserved_chars0, guard released, cancel0|

## 근거 대조

1. `equipment.db`의 현재 LoginId로 소유자를 조회하고, AI DB에서 그 소유자의 최신 user 메시지를 created/id 역순으로 확인했다. 종료 직전 재조회에서도 동일 job이 최신이었다. 두 DB는 URI mode=ro/PRAGMA query_only=ON으로만 읽었다.
2. access_logs166293(00:05:45)의 claim 응답은 required_tool과 도구 목록 모두 plan_web_search를 명시한다. 현 worker.py는 이 값을 함수 지정 tool_choice로 payload에 넣으며 transport.py는 payload를 JSON 직렬화해 전송한다. 이는 실행 중인 검증 source 계약이며 별도 upstream wire 캡처라고 주장하지 않는다.
3. access_logs166365(00:05:57)의 finish 요청은 complete/calls=[]/content0/reasoning741이었다. HTTP200은 내부 완료 보고의 정상 전달이며 모델 답변 성공이 아니다. 같은 행의 응답 본문은 success=true/state=failed/error_code=WEB_SEARCH_PLAN_REQUIRED다.
4. 서버 `utils/ai_assistant/__init__.py:993` 이후 planning 검사에서 calls 길이가1이 아니면 위 오류를 발생시킨다. app-start.log의00:05:57.070 WARNING도 같은 job/code/type=WebSearchError를 기록했다. 오류는 검색 서비스 I/O 전에 발생하므로 실제 외부 검색은 실행되지 않았다.
5. finish 요청의 worker_error_code=INVALID_RESPONSE는 complete 분기에서 남는 기본 필드다. 서버에서 정한 최종 실패 코드는 WEB_SEARCH_PLAN_REQUIRED이며, 이 기본 필드를 별도의 추가 장애로 해석하지 않는다.
6. 앞선 동일 세션·동일 모델/xhigh의 job `157228d9576740a5aeed4e8255d60821`은00:04:05.650694~00:05:05.525449(59.875초) 정상 완료했다. 첫 finish 감사165913에 plan_web_search1개/needed=true가 있었고 다음 finish166217에 답변258자가 저장됐다. xhigh에서 도구 호출이 항상 불가능하다는 주장은 반증된다.
7. worker MainPID990857은23:31:01부터 active/running이며 NRestarts0이다. 해당11.8초 구간 journal 경고/오류는 없었고 실제 중단 경고는 웹 서버에 있었다. 현재 read timeout은1800초이므로 이번11.804초 실패를840/1800초 시간 초과로 설명할 수 없다.
8. 최신 상태는 전체 active jobs0·released가 아닌 guard0·예약 문자 합0이다. 현재 큐/미확인 종료 잠금 때문에 답변을 기다리는 상황이 아니다. guard나 job을 수정하지 않았다.

## 코드·운영 범위

운영 HEAD는 `1d711824000c049586603ebc18285a412abf03fa`다. worker와 finish route SHA는 직전021 원문과 일치한다. 이번 조사는 명령을 통한 읽기와 이 진단 문서 작성만 수행했다. 서비스 재시작, provider 호출/설정 변경, 모델 요청 재전송, DB 보정, ACK, 실패 기록 변경, 코드 변경은 없었다. 원본 감사/질문/추론은 서버에 보존돼 있다. 감사 조회 첫 쿼리에서 rowid가 INTEGER PRIMARY KEY 이름으로 노출되는 SQLite Row 특성으로 IndexError가 발생해 SELECT rowid AS audit_id로 정정했으며, 데이터 변경은 없었다.

보완해야 할 지점은 필수 검색 판단 호출을 누락한 완료 응답의 처리다. 현재는 검색 여부가 확정되지 않으면 바로 작업을 종료한다. 앞으로 모델/adapter의 강제 함수 선택 준수 여부를 실제 xhigh·비교 질문에서 확인하고, upstream 종료가 확인된 이 상태에 한해 제한된 구조화 응답 보정 단계를 두는 방안을 검토할 수 있다. 검색을 실제 수행했다고 꾸미거나 미확인 실행을 중복 요청하는 방식은 피해야 한다. 이 문서는 보완 구현·배포 완료를 주장하지 않는다.

## Validation1~8

1. 거버넌스: preflight·legacy context24개를 읽었고 승인된 읽기 전용 진단과 필수 Task/Report 기록만 수행했다. 기존9개 dirty와 untracked를 보존한다.
2. 의도: 과거20:59 실패 대신 실제 최신00:05:45 질문을 식별해 응답 누락 원인을 확인했다. 신규 구현/배포로 확대하지 않았다.
3. 논리: claim의 정확히1개 필수 도구와 finish의0개·server 검사 분기를 대조했다. 인접 같은 xhigh 성공 요청으로 전역 실패 가설을 교차 확인했다.
4. 운영: DB는 read-only/query_only, 로그·서비스는 조회만 수행했다. 현재 실행 중인 자체/외부 요청을 중단하거나 새 모델 요청을 만들지 않았다.
5. 보안: 필요한 소유 질문/job으로 조회를 한정하고 인증값·원문 추론·질문·IP를 문서에 복사하지 않았다. 내부 HTTP200과 실제 state를 분리해 보안 검증 실패를 성공으로 숨기지 않는다.
6. 복구: 운영 변경이 없어 롤백은 해당 없음이다. 기존 실패/감사 원문과 종료·잠금 해제 상태를 보존했다.
7. UX: 답변0·추론741자와 실제 실패 사유가 DB에 남고 현재 잠금이 해제된 것을 확인했다. 브라우저 오류 표시가 사용자에게 실제 보였는지는 별도로 조작하지 않았다.
8. 메타: 시간 초과/프로바이더 다운/xhigh 미지원으로 단정하지 않았다. 모델/Strata 내부 호출 누락 원인과 raw SSE 종료 사유는 미확인으로 구분한다. scratch·추가 의존성·하위 에이전트·모델 재호출은 없다.
