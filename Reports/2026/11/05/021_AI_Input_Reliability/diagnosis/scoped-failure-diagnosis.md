# nekohost 응답 실패 읽기 전용 진단

작성: Codex 진단 하위 작업자. 증거 관측 시각: 2026-11-05 22:30~22:32 KST. 부모 작업021의 읽기 전용 진단 범위다. 운영 요청 재실행·취소, 모델 호출, 코드·설정·DB·서비스 변경을 수행하지 않았다. 이 문서는 대화 원문·추론·검색어 원문·인증값을 포함하지 않는다.

## 절차와 범위

AGENTS를 읽고 recorder ensure 성공(watcher11268), profile legacy/runtime-thread-id-conflict(verified=false), governance1.8.1 validate44노드 오류/경고0, review/security/handoff/inspect-external context24노드/2pack 전체를 확인했다. Plan/Task/Report021과 이전020 및018/019 관련 근거를 읽었다. Git 읽기는 GIT_OPTIONAL_LOCKS=0 원칙을 적용했다. SSH eqmgmt-backup의 equipment.db와 instance/ai/assistant.sqlite3는 SQLite URI mode=ro 및 query_only=ON으로만 읽었다. 사용자 LoginId=nekohost에 대응하는 owner의 대화/job과 그 job에 정확히 연결된 /internal/ai/jobs/<id>/finish 기록만 조사했다. test05 설정 비교는 부모가 별도 지정한 theme/layout_skin 두 enum만 읽었다.

## 관측 수량과 현재 상태

- nekohost 전체11작업: chat10(done6/failed3/cancelled1), probe1(done1).
- 실패 코드는 INVALID_TOOL_CALL1, WEB_SEARCH_REQUIRED1, STREAM_INCOMPLETE1. 취소1은 USER_CANCELLED다.
- 020 최종 코드가 운영에 적용된 21:54:45 KST 이후 이 계정의 새 작업은0이다. 과거 실패만으로 최신020 실행 코드의 회귀라고 판정할 수 없다.
- 22:32:33 KST 전체 계정의 active(queued/running/recovery_required)0, released가 아닌 guard0, reserved_chars 합계0. nekohost guard29개는 모두 released다.
- own worker는 active/running, MainPID952960, 활성 시각21:54:45 KST다. own retention timer도 active/waiting이다. 서비스 상태만 읽었으며 전환하지 않았다.
- 조사한 실제 chat route는260Strata/Qwen3.8 Flash Next(qwen3.8-flash-next-iq3_xxs), adapter=strata, context_tokens65536, profile_revision3이다. chat/tools=true, enabled/verified levels=[off,low,medium,xhigh], reasoning_version2다. 실패3개는 xhigh였다. 공급자 자격증명은 출력하거나 저장하지 않았다.

## 실제 실패와 확인 가능한 원인

| 시작 KST | job | 관측 | 판정 |
|---|---|---|---|
| 20:59:21.339 | 20bfa5ee075f4f3a8e2b56ebb8edfd65 | 20:59:31 첫 완료 단계에서 web_search1회/결과5건. 20:59:43 다음 완료 단계에서 web_search2회를 동시에 제출하여 INVALID_TOOL_CALL, steps2, 전체21.799초. | 두 호출 모두 현재 고정 schema에 맞지만 한 단계1회 계약 위반이며 이미1회 실행해 남은1회에 대해2회를 제출한 총3회 요청이다. 한도2를 늘려 성공시킬 근거가 없다. |
| 20:58:16.603 | 133f9f3017c340358afa985cfae55e3e | 20:58:27 outcome=complete, calls0, content0, reasoning265자. WEB_SEARCH_REQUIRED, steps1, 전체10.736초. | 당시 legacy required route에서 모델이 실제 검색 호출을 생략했다. 검색 결과가 없었던 네트워크 오류가 아니다. 최신020의 auto 첫 단계 plan_web_search 강제 경로는 이 당시 route와 다르다. |
| 17:33:11.665 | d1d124c69b1c465c92c8fc0122142bcb | 17:33:21 첫 단계 search_catalog3회 완료. 17:33:42 다음 단계 outcome=recovery_required/STREAM_INCOMPLETE, calls0, content0, reasoning2197자. 17:46:40 own acknowledge-finished 뒤 failed/released. | 실제 스트림 실패는 시작 약30.46초 후다. 약808.696초 전체 시간 중 약778초는 종료 미확인 상태 보존 구간이었다. 당시 worker journal은 ValueError/recovery_required만 남겼다. EOF/형식/도구 인덱스 등 구체적 ValueError 원인이나 upstream finish_reason은 보존되지 않아 단정할 수 없다. |

20:59의 공개 검색 인수는 원문 대신 다음 구조만 확인했다. 첫 호출은 query:str(24자), max_results:int(5), 후속 두 호출은 query:str(52자/63자), max_results:int(각5)다. provider/scope는 생략되어 auto/web 기본이다. 세 query는 모두 서로 달랐다. 각 인수를 현재 normalized_tool_arguments로 읽기 전용 검증해 통과했다. 후속 두 검색은 dispatch 전 거부되어 외부 검색을 실행하지 않았다.

정확한 상관관계는 access_logs150063(첫 검색 완료/queued),150135(두 검색 제출/INVALID_TOOL_CALL),149889(검색 생략/WEB_SEARCH_REQUIRED),133940(카탈로그 첫 단계/queued),134092(스트림 미확인/recovery_required),135009(own 종료 확인)이다. 17:33 실패의 worker journal 시각은08:33:42.128450 UTC이고 PID896770, 예외 유형ValueError다. 요청 원문·응답 원문·lease를 복사하지 않았다.

이 계정에서 LENGTH_LIMIT, CONNECTION_TIMEOUT, CONNECTION_FAILED, UPSTREAM_REJECTED 또는 보관 한도 오류는 관측되지 않았다. 17:33의 ValueError를 네트워크 timeout 또는 출력 길이 제한으로 바꿔 설명하면 근거를 벗어난다. 실패를 성공으로 바꾸거나 기존 guard를 다시 변경할 필요도 없다.

## 현재 코드와 최소 개선 방향

1. utils/ai_assistant/__init__.py1013~1014는 한 단계 검색2개 이상을 INVALID_TOOL_CALL로 막는다. web_search.py18은 전체 MAX_SEARCHES=2이며 Domain의 현재 context 검사(domain.py140~142)는 이미2회 실행한 뒤의 세 번째 단일 호출을 막는다. 모델의 정적 SYSTEM(policy.py63)에는 총2회 지침이 있지만 claim(__init__.py791~804)은 단계별 남은 횟수를 전달하거나 소진 시 검색 도구를 제거하지 않는다. 확인된 개선 여지는 동적 남은 횟수·한 단계1회 명시, 남은 예산을 초과한 전체 batch의 I/O 전 WEB_SEARCH_LIMIT 거부, 소진 뒤 검색 도구 제거 및 위조 호출의 서버 거부다. 전체 schema 검증·개인정보·출처 correlation·예약/guard·장비 변경 확인은 그대로 유지해야 한다.
2. 최신020의 search_planning(web_search.py116~120)은 auto 첫 단계에서 정확히1개 plan_web_search만 허용하므로 첫 단계 다중 호출은 이미 차단한다. needed=true 검색은 예산1회를 사용하고 다음 단계에1회만 남는다. 현재 후속 web_search batch에는 기존 제한이 계속 적용된다. 이번 역사적2회 batch를 그대로 허용하면 전체3회가 되므로 적절하지 않다.
3. 한 finish에서2검색을 순차 실행하는 확장은 현재 근거만으로 필요하지 않다. 각 검색 deadline8초와 worker.post read timeout15초(worker.py96)가 겹치면 첫 finish가 끝나기 전 동일 finish 재전송을 유발할 수 있다. test_ai_web_search.py302~307도 한 finish의 외부 작업 수를 제한한다. 한 단계1회 계약을 유지하면서 모델이 남은 예산을 이해하게 하는 수정이 작다.
4. STREAM_INCOMPLETE는 DONE 미확인 상태를 보존해야 한다. 실패 원인을 추정해 guard를 해제하거나 정상 생성에 전역 timeout을 추가하지 않는다. 향후 원인 분석을 위해 고정 비민감 스트림 종료/프로토콜 사유를 추가 기록하는 개선은 가능하지만 이번17:33 근본 원인이 확인된 수정이라고 부를 수 없다.

회귀에서는 legacy required/off 및 auto true/false,1회 뒤2회 batch의 외부 I/O0/정확한 WEB_SEARCH_LIMIT, 남은1회 정상 처리,2회 뒤 검색 도구 부재와 위조 거부, 첫 planner 중복/생략 거부, 검색 실패 후 장비 확인 카드0, 모든 terminal 경로의 reserved_chars0/guard released를 확인한다. 현재 정책상 허용되는 느린 모델 생성·자기 요청 drain·종료 미확인 guard 보존은 회귀로 지켜야 한다. 실제 user job을 재실행하지 않는다.

### 부모의 후속 bounded feedback 설계 검토

위의 전체 초과 batch 거부는 최초 최소안이다. 부모는 더 나아가 한 finish에서 유효한 첫 검색1개만 실행하고 남은 검색 호출에는 명시적인 미실행 제어 결과를 같은 call ID로 반환하는 방안을 검토했다. 이는 실행/미실행을 정확히 구분하고 다음 조건을 유지하면 이전 실패를 줄이는 대안이 될 수 있다. 이 진단 문서는 해당 코드의 구현·검증 완료를 주장하지 않는다.

- 첫 auto planner는 기존 정확히1개 계약을 유지하고, 후속 web_search에만 제어 결과를 제공한다.
- 제어 결과는 고정된 별도 kind, executed=false, reason enum, remaining 정수로 작게 제한한다. results/engine/searched_at을 생성하지 않는다. public_searches와 evidence_chars의 기존 kind=web_search 조건이 이 결과를 실제 출처/검색량으로 계산하지 않아야 한다.
- batch 전체의 schema·도구 이름·unique call ID를 검증한 뒤 최대1회만 실제 I/O를 실행한다. 첫 실제 검색의 privacy/provider/timeout 실패는 여전히 terminal이며 미실행 결과로 숨기지 않는다.
- route/auto-false/off·현재 사용자 권한·lease·취소·삭제 및 비공개 상세 조회 taint를 제어 결과 분기로 우회하지 않는다. 예산만 부족한 경우와 아예 검색 권한이 없는 경우를 구분한다.
- 검색2개와 장비 변경 준비가 섞인 batch에서 필요한 검색 일부를 생략한 채 확인 카드를 준비하면 기존 search-first 계약이 약해질 수 있다. all-web_search batch로 적용 범위를 좁히거나 미완료 검색 뒤 업무 준비를 하지 않는 명시적인 방어가 필요하다.
- 남은1회에서2검색을 받은 회귀는 실제 추가 I/O1회, 실제 출처 총2개, 제어 결과의 출처/charge0, 원래 인수와 call ID 보존, 후속 정상 답변, guard/예약 해제를 확인해야 한다. 제어 결과를 모델이 무시하고 반복하면 기존 단계 한도에서 명확히 종료하며 모델 요청을 자동 재실행하지 않는다.

## 보내기 영역 조사의 설정 비교

equipment.db user_settings의 실제 JSON 컬럼은 PreferencesJSON이다. nekohost는 theme=system, layout_skin=edge를 저장했다. test05는 설정 행이 없어 layout_skin=standard fallback을 사용한다. theme의 실제 색은 현재 브라우저 localStorage/시스템 설정에 따라 달라질 수 있다. 이 차이는 edge 스킨에서의 hit-test를 추가할 근거이며, 설정만으로 겹침 원인을 확정한 결과는 아니다.

## Validation1~8

1. 거버넌스: preflight·legacy 전체 pack·부모021 작업 범위를 읽고 읽기 전용 진단 및 이 sanitized 문서 작성만 수행했다.
2. 의도: 사용자 본인 대화의 실패 원인을 입력 UI 문제와 혼동하지 않고 분류했다. 최신 실행 뒤 사용자 새 작업0은 관측 사실이며 현재 화면 원인의 증명은 아니다.
3. 논리: 전체 검색2/단계1, batch와 완료/미확인 구분, 실패 발생 시각과 recovery 유지 시간을 분리했다.
4. 운영: 운영 DB는 ro/query_only, source·설정·서비스 변경 및 모델 실행0이다. Windows Flask import/기동0이다.
5. 보안: 개인 대화·추론·검색어·lease·키 원문을 출력/저장하지 않았다. 부모 지정 계정 설정은 두 enum만 읽었다.
6. 복구: 데이터 변화가 없어 복원 조치는 해당 없음이다. 과거 실패/취소와 현재 released 상태를 보존했다.
7. UX: edge/system 저장값을 hitbox 담당자에게 전달했다. 실제 사용자 화면 재현과 합성/다른 계정 결과를 구별해야 한다.
8. 메타: 모델 공급자 제한·과거 코드·현재020 예방 경로·아직 확인할 수 없는 프로토콜 원인을 구별했다. 추론을 확정 원인으로 기록하지 않았다.
