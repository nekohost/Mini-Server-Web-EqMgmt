---
artifact_id: REPORT-20261104-003
work_id: REVIEW-20261104-USER-AI-STATIC
created_at: 2026-11-04
owner: Codex
mode: static-review
status: complete-with-findings
related_artifacts: [PLAN-20261104-003, TASK-20261104-003]
---

# 장비관리 AI Staging 정적검사

## 범위와 방법

직전 대화의 F01~F12/Q01~Q15/L01~L08 35개 기준을 적용한다. Staging 후보 15파일과 기존 호출 계약을 읽고 AST/JS 구문·상태 전이·인가·트랜잭션·입출력·실패 흐름을 정적으로 검사한다. 소스/운영 DB를 변경하거나 앱/모델/동작 시험을 실행하지 않는다. 기존 49/29개 통과 시험과 이번 정적 판정은 구분한다.

## 순차 검토

| 단계 | 근거·긍정적 결과 | 위험·차단 조건·추가 발견 |
| --- | --- | --- |
| 1. 거버넌스 | recorder 정상, legacy(runtime-session-mismatch), validate v1.8.1/44노드 오류·경고 0, context 2 pack 확인. Task/Plan을 검사 전에 생성했다. 후보 15개 파일 hash가 기존 검증 기록과 모두 일치한다. Python AST 9개와 JS 구문 2개가 통과했다. | 앱/모델/DB를 실행하지 않는다. 구문 통과를 논리·보안 합격으로 대체하지 않는다. 함수별 메타 주석의 필수 세 항목 누락이 자동 목록에 나타나 Q15에서 검토한다. 코드 수정·병합은 검사 범위가 아니다. |
| 2. 사용자 의도 | F01~F12의 독립 템플릿·대화·추론 분리/접힘·세 가지 추론값·일반 질문·11개 고정 도구·본인 업무·카탈로그 신청·수동 파일/CSV·내부 큐 경로를 식별했다. 일반 사용자 actor와 삭제/관리자 도구 제외가 명시되어 있다. | 기능이 선언되어 있다는 이유로 충족 판정하지 않는다. 확인 내용·단계 전환·실패 처리·현재 권한의 실제 코드 흐름을 3~7단계에서 대조한다. 승인 전 특수 임시 카탈로그 복합 생성은 기존 제외 범위를 유지한다. |
| 3. 논리 | 큐 단일 claim의 unique index/짧은 transaction, 6회 모델 단계/4개 도구/8개 제안, 불변 제안/원자적 업무 영수증을 확인했다. | 완료 보고의 일부 입력 오류는 lease를 종료하지 못해 전체 내부 큐를 막는다. 다단계 추론은 finish에서 이전 단계를 덮어쓴다. 대화 목록 100개/메시지 60개에 다음 페이지가 없으며, 보관 한도는 질문 접수만 검사하고 생성/결과 저장은 검사하지 않는다. 세부 발생 경로와 중요도를 결함 목록에 기록한다. |
| 4. 운영 영향 | 기존 서비스의 사용자 actor·바인딩 SQL·카탈로그 승인 대기·상태/CSV/파일 계약 및 기본 false 기능/쓰기 flag를 대조했다. 장비 schema DDL과 root 병합은 없다. | 후보 app.py의 전역 접근 로그 제외 목록에 신규 /api/ai 및 /internal/ai 경로가 없다. 대화·추론 및 CSV 확인 토큰/worker lease가 일반 payload 수집 대상으로 들어가는 통합 결함을 확인 중이다. 또한 공통 장비 validator의 정규화 반환값을 버리는 경로가 있어 실제 저장 계약과 일치하지 않는다. |
| 5. 보안 | 각 사용자 route의 login/browser 재검증, 서버 account_key/메뉴/소유권, worker loopback+별도 key, Origin/CSRF, 폐기·삭제·관리자/임의 명령 도구 제외, HMAC 제안과 현재 revision/옵션 검증, textContent/허용 내부 링크를 확인했다. | 전역 로그의 수집→push_access_log→_write_logs_to_db 경로에는 신규 AI payload에 대한 제거/마스킹이 없다. CSV 확인 토큰·worker lease·개인 대화/추론이 access_logs 저장 대상으로 흘러가므로 Q10은 미충족이다. 운영 로그나 실제 토큰은 열람하지 않았다. |
| 6. 복귀 | 취소 시 자체 작업만 draining/cancelled로 전환하고 이미 확정한 영수증을 보존한다. 종료 불명확 시 재발신을 막고 명시적 자체 요청 종료 확인으로만 큐를 해제한다. 공유 Strata stop/unload/restart는 없다. | 실제 모델 취소/서버 복귀는 실행하지 않아 미확인이다. 종료가 명확한 완료 보고의 형식 오류까지 running으로 남는 결함은 복구 필요 상태와 구별해 수정해야 한다. 백업/복원·실제 요청 종료 식별은 기존 운영 적용 전 조건으로 남긴다. |
| 7. UX | 독립 DOM/응답 textContent/허용 Markdown·링크, 추론 details, 모바일 media query, 변경 전후/서버 결과·CSV 요약, 중복 클릭 비활성화와 세션 전환 DOM 제거를 확인했다. | 단계가 바뀔 때 answerStarted가 초기화되어 사용자가 다시 펼친 추론을 재차 닫을 수 있다. 100개 이전 대화/60개 이전 메시지를 불러올 경로가 없어 저장 한도 안의 과거 기록이 화면에서 끊긴다. 실제 화면/키보드/보조기기 사용성은 이번 정적검사에서 재실행하지 않는다. |
| 8. 메타 | F12+Q15+L8=35개 판정을 근거와 연결했다. 전수 소스/계약 대조 후 단계 전환·형식 오류·한도 경계·로그 통합의 교차 시나리오를 1회 검토했다. 검사 전후 후보 15개 및 기존 앱/사용자 변경 13개 파일 hash가 같고, 신규 17 route와 root app/기존 utils의 리터럴 route 충돌은 0이다. | P1 2건/P2 4건/P3 1건, 정적 충족 24/부분 10/미충족 1로 보고한다. 이전 49/29 시험 성공을 이번 정적 합격으로 대체하지 않았다. 소스/DB/설정/Git/기존 검증 기록은 그대로이며 새 Plan/Task/Report만 작성했다. 실제 모델·운영 환경은 미확인이고 운영 병합 판단은 보류다. |


## 결함 목록

P1은 운영 전 필수 수정, P2는 구체적 기능/품질 결함, P3는 유지보수 기준 미달이다. 아래 발생 경로는 소스에서 추적했으며 동작 시험의 재현 결과로 표기하지 않는다.

### D01 [P1] 신규 AI 본문과 확인 토큰이 일반 접근 로그에 저장됨

- 기준: Q10; Q14 통합 확인
- 위치: [app.py:329](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/app.py:329), [app.py:342](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/app.py:342), [app.py:1342](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/app.py:1342), [utils/ai_assistant/__init__.py:393](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:393), [utils/ai_assistant/__init__.py:575](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:575)
- 원인: 후보의 after_request_func는 /api/admin/database/, /api/equipment/csv/, /api/equipment/.../files만 민감 경로로 제외한다. /assistant, /api/ai/, /internal/ai/는 제외하지 않으며 request.get_data/response.get_data를 RequestPayload/ResponsePayload에 전달한다. push_access_log와 _write_logs_to_db에도 제거/마스킹이 없다.
- 발생 조건: 로그 수집이 켜진 일반 운영에서 claim 응답의 lease, CSV preview 응답의 확인 token, 대화/추론 조회 응답 및 /assistant HTML의 CSRF 값이 access_logs 저장 대상으로 들어간다. Authorization 헤더의 전체 worker/Strata key가 기록된다고 주장하지 않는다.
- 영향: 개인 대화·일회성 확인 정보가 별도 운영 로그에 중복 보관되고 로그 조회 권한/백업/보존 범위로 확장된다. 로그 본문 증가는 AI 보관 한도와도 별개다.
- 수정 방향: 세 AI 경로 전체를 메타데이터 전용 로그로 분류하고 요청/응답 본문을 저장하지 않는다. 기존 전역 hook까지 포함한 회귀 검증을 추가한다.
- 기존 검증의 범위: 기존 fixture는 별도 Flask 앱에 AI와 원본 login_required만 설치하고 전역 접근 로그 hook을 실행하지 않는다(test_equipment_ai.py:74~94).

### D02 [P1] 완료된 모델 응답의 형식 오류가 전체 내부 큐를 막음

- 기준: F11, F12, Q12, Q13
- 위치: [utils/ai_assistant/__init__.py:447](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:447), [utils/ai_assistant/__init__.py:458](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:458), [utils/ai_assistant/worker.py:195](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/worker.py:195), [utils/ai_assistant/store.py:205](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:205)
- 원인: finish의 calls 수/필드/ID 중복/빈 문자열 검사 등이 작업 종료 처리 밖에서 예외를 반환한다. 예외 handler는 HTTP 오류만 반환하며 job lease/state를 종료하지 않는다. worker는 finish 오류를 로그만 남기고 claim 루프로 복귀한다.
- 발생 조건: SSE DONE과 tool_calls 종료 사유를 받은 뒤 도구 호출 두 개가 같은 id를 가지면 두 번째 id 검사에서 400으로 끝난다. running 상태는 유지되고 Store.claim은 계속 None을 반환한다. 앱/모델을 실행한 재현은 아니며 소스 분기로 추적했다.
- 영향: 잘못된 모델 응답 하나로 장비관리의 모든 후속 AI 요청이 운영자 복구 전까지 대기한다. 사용자에게는 완료된 오류가 계속 실행/연결 대기로 보인다.
- 수정 방향: 종료가 확인된 응답의 전체 구조를 도구 처리 전에 검증하고, 검증/처리 실패도 해당 job을 명시적으로 failed로 마감한다. 실제 종료 불명확 요청의 recovery_required 방어는 유지한다.
- 기존 검증의 범위: 기존 완료 helper는 항상 성공 응답을 기대하며, malformed completed tool-call이 전체 queue를 해제하는지 검사하지 않는다(test_equipment_ai.py:137).

### D03 [P2] 여러 단계의 추론이 덮어써지고 접힘이 반복될 수 있음

- 기준: F03, F04
- 위치: [utils/ai_assistant/store.py:212](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:212), [utils/ai_assistant/store.py:236](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:236), [utils/ai_assistant/worker.py:111](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/worker.py:111), [utils/ai_assistant/__init__.py:432](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:432), [static/js/equipment_ai.js:14](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/static/js/equipment_ai.js:14)
- 원인: claim은 이전 reasoning을 보존하고 event는 이어 붙이지만, 각 worker.run_job의 total_reasoning은 새 목록이다. finish는 이 단계의 reasoning으로 전체 메시지를 교체한다. UI도 generation 변경 시 answerStarted를 초기화한다.
- 발생 조건: 1단계 추론 A→도구 조회→2단계 추론 B/최종 답변이면 event 도중 A+B였던 DB가 finish에서 B로 바뀐다. 이미 A 길이만큼 읽은 r cursor와도 어긋날 수 있다. 중간 content 후 사용자가 펼친 영역은 새 generation의 첫 content에서 다시 닫힐 수 있다.
- 영향: 다시 열었을 때 앞 단계 추론이 사라지거나, 라이브 화면과 저장된 화면이 달라지고 수동 펼침 유지 조건이 깨진다.
- 수정 방향: 단계별 추론과 확정 스냅샷을 구분해 중복 없이 누적하고 cursor를 같은 기준에 묶는다. 자동 접힘 여부는 턴 전체의 사용자 조작 상태와 함께 관리한다.
- 기존 검증의 범위: 기존 추론 시험은 한 단계 보존/후속 질문 미재주입을 확인한다. 브라우저 시험도 동일 generation이며 다단계 누적을 검사하지 않는다.

### D04 [P2] 저장한 과거 대화와 메시지를 끝까지 열 수 없음

- 기준: F02
- 위치: [utils/ai_assistant/store.py:94](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:94), [utils/ai_assistant/store.py:103](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:103), [utils/ai_assistant/store.py:187](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:187), [static/js/equipment_ai.js:229](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/static/js/equipment_ai.js:229), [static/js/equipment_ai.js:242](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/static/js/equipment_ai.js:242)
- 원인: 보관 대화는 200개까지 허용하나 목록은 최근 100개만 반환하고 cursor/page가 없다. 메시지는 마지막 60개만 반환하며 UI에 이전 기록 가져오기 경로가 없다.
- 발생 조건: 계정의 101번째 이후로 밀린 대화는 목록에서 사라지고, 긴 대화의 앞부분은 저장되어 있어도 재접속 화면으로 읽을 수 없다. 임의의 opaque ID를 알고 직접 API를 호출하는 것은 정상 UI 복구 경로가 아니다.
- 영향: 사용자별 영구 보관과 이전 대화 이어보기 목표가 저장 한도 안에서도 불완전하다. 데이터가 삭제되었다고 주장하지 않는다.
- 수정 방향: 대화 목록/메시지 모두 owner 조건을 유지한 cursor 페이지와 UI의 이전 기록 불러오기를 제공한다.
- 기존 검증의 범위: 현재 fixture는 작은 대화 목록/짧은 history만 사용한다.

### D05 [P2] 답변과 실행 결과 저장이 보관 한도를 넘을 수 있음

- 기준: L05; Q12
- 위치: [utils/ai_assistant/store.py:128](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:128), [utils/ai_assistant/store.py:231](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:231), [utils/ai_assistant/__init__.py:430](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:430), [utils/ai_assistant/__init__.py:364](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:364)
- 원인: 보관 문자열과 디스크 여유 검사는 enqueue에서 질문을 추가할 때만 한다. append·finish 스냅샷·확정 결과 메시지 저장에는 같은 계정 한도 검사나 응답 공간 예약이 없다.
- 발생 조건: 31,999,990자가 보관된 계정에서 5자 질문은 접수된다. 이어 100자 답변을 저장하면 32,000,000자 기준을 넘는다. 모든 자원 사용이 무한하다고 주장하지 않으며, 출력/도구 수 제한은 별도로 존재한다.
- 영향: 설정한 보관 상한이 생성/확정 단계에서 지켜지지 않고 진행 중 디스크 여유 감소도 재확인하지 않는다.
- 수정 방향: 새 작업의 출력 예산 예약 또는 모든 메시지 저장 경로의 원자적 사용량 계산을 적용한다. 확정된 업무·영수증은 보존하고 한도 도달 상태를 안전하게 마감한다.
- 기존 검증의 범위: 기존 보관 시험은 질문 자체가 한도를 넘는 접수 거절만 다룬다(test_equipment_ai.py:481).

### D06 [P2] 공통 장비 입력 정규화 결과를 저장에 사용하지 않음

- 기준: F07
- 위치: [utils/ai_assistant/domain.py:198](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/domain.py:198), [utils/ai_assistant/domain.py:207](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/domain.py:207), [utils/ai_assistant/domain.py:211](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/domain.py:211), [utils/ai_assistant/domain.py:214](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/domain.py:214)
- 원인: equipment_fields는 복사된 dict에 날짜/문자열 정규화를 적용해 반환하지만 validate_equipment는 두 호출의 반환값을 버리고 원래 payload/dates에서 저장 값을 만든다.
- 발생 조건: 구입일 '2026-11-01 '은 공통 validator에서 정상 ISO 값으로 정리되어 검증되지만, AI 어댑터가 DB에 넘기는 값에는 뒤 공백이 남는다. 시리얼의 앞뒤 공백도 기존 정규화 결과와 달리 중복 비교/저장에 사용된다.
- 영향: 기존 수동/CSV 경로와 다른 값이 저장 입력으로 전달되어 날짜 표시·기한 계산 또는 시리얼 중복 판정이 달라질 수 있다. 실제 운영 DB의 결과를 실행 확인한 것은 아니다.
- 수정 방향: 기존 값과 수정 값을 합친 후 공통 validator의 반환값을 실제로 사용하고, 확인 카드와 확정 저장에 동일한 정규화 스냅샷을 사용한다.
- 기존 검증의 범위: 기존 fixture의 정식 날짜/공백 없는 시리얼만으로는 드러나지 않는다. 공통 계약 근거는 루트 utils/roadmap_validation.py:108~149.

### D07 [P3] 일부 검증 함수와 화면 helper의 메타 주석 기준 누락

- 기준: Q15
- 위치: [tests/run_assistant_fixture.py:15](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/tests/run_assistant_fixture.py:15), [tests/assistant_browser_fixture.py:94](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/tests/assistant_browser_fixture.py:94), [tests/test_equipment_ai.py:35](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/tests/test_equipment_ai.py:35), [static/js/equipment_ai.js:53](C:/Project/Mini-Server-Web-EqMgmt/Staging/20261104-user-ai-assistant/overlay/static/js/equipment_ai.js:53)
- 원인: Python AST로 각 함수 docstring의 Role/Dependencies/Impact를 확인하면 검증 파일 19개 함수에서 하나 이상이 빠진다. JS 일반 helper도 Role만 있는 경우가 다수다. 핵심 모듈/stream 추적 주석과 생산 Python 함수의 세 항목은 별도로 존재한다.
- 발생 조건: 예: run_assistant_fixture.main, assistant_browser_fixture.run_browser 및 내부 route, test fixture helper는 역할만 설명한다. 새 KO 감사가 끝났다는 허위 기록은 없다.
- 영향: 실행 결함은 아니지만 인계 시 의존성/수정 영향 추적이 프로젝트의 함수별 기준에 못 미친다.
- 수정 방향: 역할뿐 아니라 실제 의존성·영향을 필요한 함수별로 보완하고 EN/KO 감사 상태를 그대로 구분한다. baseline만 바꾸어 누락을 숨기지 않는다.
- 기존 검증의 범위: 이전 정적 점검은 docstring의 존재 여부만 확인해 세 항목의 누락을 구분하지 않았다.

## 35개 기준별 판정

‘정적 충족’은 코드 경로가 기준에 부합한다는 뜻이며 실제 모델·운영 환경의 실행 성공을 보장하지 않는다. ‘부분 충족’은 기본 경로가 있으나 명시한 예외가 남은 경우, ‘미충족’은 필수 보호 조건의 위반을 확인한 경우다.

| 번호 | 기준 | 판정 | 코드 근거와 한계 | 확인 위치 |
| --- | --- | --- | --- | --- |
| F01 | 독립 AI 화면 | 정적 충족 | 별도 /assistant 템플릿·자산·설치 함수. Strata iframe/vendor를 사용하지 않음. | `templates/equipment_ai.html:1; utils/ai_assistant/__init__.py:233` |
| F02 | 사용자별 대화 보관/이어보기 | 부분 충족 | 소유권/저장은 있으나 100개 대화·60개 메시지 이후를 조회할 경로가 없음(D04). | `utils/ai_assistant/store.py:94,187` |
| F03 | 추론 실시간/별도 보관 | 부분 충족 | reasoning/content는 분리되지만 후속 단계 완료가 이전 추론을 덮어씀(D03). | `utils/ai_assistant/__init__.py:430; worker.py:111` |
| F04 | 추론 자동 접힘 한 번/수동 재열기 유지 | 부분 충족 | 동일 단계에서는 유지. generation 전환마다 answerStarted가 초기화되어 재접힘 가능(D03). | `static/js/equipment_ai.js:14,288` |
| F05 | 세 가지 추론 선택 | 정적 충족 | low→none, medium→medium(기본), high→xhigh로 닫힌 선택. | `utils/ai_assistant/policy.py:12; templates/equipment_ai.html` |
| F06 | 일반 질문 응답 | 정적 충족 | 일반 질문 허용 system 지시와 도구 없는 응답 완료 경로가 있음. 답변 품질은 실행 의존. | `utils/ai_assistant/policy.py:16; __init__.py:476` |
| F07 | 일반 사용자 장비 업무 | 부분 충족 | 소유/상태/옵션 검증은 있으나 공통 validator의 정규화 결과가 버려짐(D06). | `utils/ai_assistant/domain.py:198,211,214` |
| F08 | 카탈로그 신청/본인 신청 조회 | 정적 충족 | 기존 서비스를 Role=user로 호출. 본인 신청 조건 및 승인 대기 반환. | `utils/ai_assistant/domain.py:151,314` |
| F09 | 변경 전 확인/실제 결과 | 정적 충족 | CSRF 확인 endpoint·불변 제안·원자적 영수증 및 서버 결과 카드. 로그 노출은 Q10에서 별도 불합격. | `utils/ai_assistant/__init__.py:338; domain.py:239` |
| F10 | 파일/CSV/개인 설정 | 정적 충족 | 수동 선택·현재 권한·기존 검증/owner-bound CSV·허용 설정 키. 임의 경로/파일 취득 도구 없음. | `utils/ai_assistant/__init__.py:497,552,603; domain.py:325` |
| F11 | 장비관리 내부 대기열 | 부분 충족 | 단일 발신·단계 뒤로 재진입·확인 대기 해제는 있으나 완료 형식 오류로 전체 내부 큐가 막힘(D02). | `utils/ai_assistant/store.py:27,205; __init__.py:455` |
| F12 | 취소/실패/복구 상태 | 부분 충족 | 자체 취소·불명확 종료 복구 경로는 있으나 명확히 완료된 응답의 일부 오류가 running으로 남음(D02). | `utils/ai_assistant/worker.py:195; __init__.py:455` |
| Q01 | 서버 기준 인증/현재 권한 | 정적 충족 | 서명 cookie·실시간 SessionToken/활성/메뉴 검증. 역할·사용자 번호를 요청 인자에서 받지 않음. | `utils/ai_assistant/__init__.py:123; domain.py:30` |
| Q02 | 사용자 데이터 분리 | 정적 충족 | 대화/작업/proposal account_key+owner, 장비/파일 own, CSV 사용자 조건을 확인. 전역 로그는 Q10에서 별도 지적. | `utils/ai_assistant/store.py:83,167; domain.py:75` |
| Q03 | 계정 전환/복원 대응 | 정적 충족 | UserId+CreatedAt 계정 식별, 유지보수 revision/토큰 위임, 화면 context 변경 시 DOM 제거. | `utils/ai_assistant/domain.py:48,65; static/js/equipment_ai.js:82` |
| Q04 | 일반 사용자 범위 강제 | 정적 충족 | 관리자도 Role=user actor. 삭제/폐기/소유권 이전·관리자 도구가 고정 목록에 없음. | `utils/ai_assistant/domain.py:57; policy.py:161` |
| Q05 | 도구/인자/실행 범위 제한 | 정적 충족 | 고정 11개 도구, 닫힌 schema/타입/크기, 바인딩 SQL. 임의 실행·URL·FS 도구 없음. | `utils/ai_assistant/policy.py:116,145; domain.py:107` |
| Q06 | 프롬프트 조작과 서버 권한 분리 | 정적 충족 | 본문·메모의 지시로 actor/도구/권한이 확장되지 않음. 실제 모델의 대응 품질은 별도 실행 확인. | `utils/ai_assistant/policy.py:17; domain.py:112` |
| Q07 | 브라우저/작업자 인증 분리 | 정적 충족 | 브라우저 Origin/CSRF와 worker loopback+독립 Bearer를 분리. worker key만으로 confirm 불가. | `utils/ai_assistant/__init__.py:145,151,338` |
| Q08 | 확인 내용 무결성 | 정적 충족 | 제안 HMAC/만료·현재 메뉴·장비 revision·선택 옵션 snapshot 재검증. | `utils/ai_assistant/domain.py:263,267,292,298` |
| Q09 | 중복 실행 방지/원자성 | 정적 충족 | 업무 변경·감사·실행 영수증 한 transaction, receipt 조회 후 재시도 결과 복구, 예외 rollback. | `utils/ai_assistant/domain.py:248,255,273` |
| Q10 | 안전한 출력/비밀 보호 | 미충족 | DOM 출력·예외 메시지는 제한되나 전역 접근 로그가 신규 AI 본문/토큰을 수집(D01). 내부 HTTP 통신 보호도 운영 확인 필요. | `app.py:1342,1346,1355` |
| Q11 | 세션 수명/권한 철회 | 정적 충족 | passive session interface와 타이머 예외·job 만료/철회 검사. 자동 poll이 cookie를 계속 연장하지 않음. | `utils/ai_assistant/__init__.py:47,163; static/js/session_timer.js:142` |
| Q12 | 자원 점유/경합 제어 | 부분 충족 | 생성 중 DB transaction 없음, poll 중첩 방지/오류 backoff 있음. D02 큐 해제 누락과 D05 저장 한도 누락은 미해결. | `utils/ai_assistant/store.py:59; static/js/equipment_ai.js:273` |
| Q13 | 이해 가능한 상태/오류 | 부분 충족 | 안전한 메시지/서버 결과/CSV 요약은 있으나 D02에서 완료된 실패를 계속 생성/연결 대기로 표시. | `utils/ai_assistant/__init__.py:182; static/js/equipment_ai.js:216` |
| Q14 | 기존 기능 보존/복귀 | 정적 충족 | 기능/쓰기 기본 false, 장비 DDL 없음, 자체 작업만 정리/확정 데이터 보존. 실제 복원·운영 연동은 별도 확인. | `utils/ai_assistant/__init__.py:66; README.md` |
| Q15 | 유지보수/주석 추적 | 부분 충족 | 모듈 책임과 핵심 EN revision은 분리. 검증 도구 19개 함수 메타 항목 및 JS 다수 helper의 의존성/영향 설명 누락(D07). KO 감사는 미완료로 구분. | `overlay/tests/*.py; static/js/equipment_ai.js:53` |
| L01 | 미완료/발신 수 제한 | 정적 충족 | unique index 발신 1, 미완료 사용자 2/전체 20. D02는 이 제한 때문에 가용성 피해가 전체로 이어짐. | `utils/ai_assistant/store.py:27,134` |
| L02 | 접수 빈도/재전송 | 정적 충족 | 10회/분·200회/일, 중복 키 내용 해시 검증을 rate 검사보다 먼저 수행. | `utils/ai_assistant/store.py:119,125` |
| L03 | 질문/추론/답변 크기 | 정적 충족 | 질문 8,000자, 저장된 추론 100,000자/답변 64,000자 상한. 다단계 내용 보존 오류는 F03에서 지적. | `utils/ai_assistant/__init__.py:290,430; store.py:234` |
| L04 | 모델/도구/확인 수 제한 | 정적 충족 | 최대 6회 모델 단계, 단계별 도구 4개, 질문당 proposal 8개. | `utils/ai_assistant/store.py:267,282; __init__.py:447` |
| L05 | 보관/디스크 한도 | 부분 충족 | 200개 대화는 검사하지만 32,000,000자/128MiB 조건은 접수 시점만 검사. 생성/실행 결과 저장에서 넘을 수 있음(D05). | `utils/ai_assistant/store.py:103,128,226; __init__.py:364,430` |
| L06 | 확인/작업 위임 만료 | 정적 충족 | proposal은 min(job 만료,15분), job은 min(30분,앱 세션 수명). | `utils/ai_assistant/store.py:259; __init__.py:294` |
| L07 | 파일/CSV 제한 | 정적 충족 | 파일 10MiB·CSV 1MiB/500행 선언 및 기존 서버 서비스 제한/타입/서명 검사 연결. | `utils/ai_assistant/__init__.py:508,563; utils/roadmap_equipment.py:17` |
| L08 | 모델 네트워크 대기 | 정적 충족 | 연결 5초/읽기 기본 1,800초를 분리. 총 작업 완료 시간이나 응답 SLO로 보고하지 않음. | `utils/ai_assistant/worker.py:141,230` |

## 판정 집계와 한계

| 구분 | 전체 | 정적 충족 | 부분 충족 | 미충족 |
| --- | --- | --- | --- | --- |
| 기능 | 12 | 6 | 6 | 0 |
| 품질 | 15 | 11 | 3 | 1 |
| 자원 제한 | 8 | 7 | 1 | 0 |

합계 35개: 정적 충족 24개, 부분 충족 10개, 미충족 1개. 부분/미충족을 수정 완료로 처리하지 않는다. 검토 자체는 완료하되 **현재 후보의 운영 병합 판단은 보류**다. 특히 D01/D02는 운영 전 필수 수정이다. D03~D06 기능·한도 결함도 수정하고 관련 회귀 근거를 보완해야 한다.

정적 자동 검사: Python AST 9개/JS 구문 2개 통과. 기존 49개 Linux 합성 시험·29개 브라우저 검사는 과거 결과이며 이번 턴에서 재실행하지 않았다. 통과 숫자를 전체 검증 완료로 확대하지 않는다. 모델 정답률·도구 선택 정확성·실제 스트림/취소·운영 DB 계약·지연/부하·일관된 백업 복구는 미확인이다. 답변 정답률·지연 SLO는 아직 수치 목표가 정해지지 않았다.

기존 검증 JSON은 보존했다. 새 소스 검사는 새로운 결함을 추가로 식별한 결과이며 기존 시험 성공 사실을 덮어쓰거나 실패를 성공으로 바꾸지 않는다. 코드 수정·테스트 추가·운영 DB 접근·서버 실행·Git 변경·배포는 수행하지 않는다.

