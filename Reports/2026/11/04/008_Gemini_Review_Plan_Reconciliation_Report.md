---
artifact_id: REPORT-20261104-008
work_id: REVIEW-20261104-GEMINI-PLAN-RECONCILIATION
created_at: 2026-11-04
owner: Codex
mode: review-and-plan-reconciliation
status: completed
related_artifacts: [PLAN-20261104-006, TASK-20261104-008, REPORT-20261104-005]
---

# Gemini 완료 평가와 확장 계획 대조

## 결론

**Gemini는 기존 006 계획이 구체적으로 명세하지 못한 감사 처리·전역 점검 게이트·작업 준비 예외·최초 오류 사유의 경계를 짚었다.** S01~S04의 유효한 취지를 실제 코드와 대조해 006의 확장 전 선행 보완과 통합 회귀 기준에 반영했다. 이들은 전면 재작성의 근거가 아니며 기존 기능의 수명주기/전역 훅 경계 보완으로 다룬다.

단, 원본 005에는 실제 소스와 다른 경로·함수/상수명·단위·기능 범위와 일부 입증되지 않은 원인 설명이 섞여 있다. 따라서 ‘P0/P1 0건·Conditional Pass’나 권장 코드 예시를 무비판적으로 이어받지 않고, 항목별로 채택·정정·보류를 구분했다. 이번 검토는 새 런타임 재현 시험이나 기능 수정이 아니다.

검토 원본은 완료 상태인 [005 Report](005_User_AI_Assistant_Post_Correction_Static_Inspection_Report.md), [005 Plan](../../../../Plans/2026/11/04/005_User_AI_Assistant_Post_Correction_Static_Inspection_Plan.md), [005 Task](../../../../Tasks/2026/11/04/005_User_AI_Assistant_Post_Correction_Static_Inspection_Task.md)다. Gemini 원본은 수정하지 않았다. 반영 대상은 [006 확장 계획](../../../../Plans/2026/11/04/006_Multi_Provider_AI_Extension_Plan.md)이며 007 Hermes 비교와 최신 사용자 결정은 유지한다.

## 지적의 소스 대조와 계획 영향

| 원본 ID | 실제 대조 결과 | 기존 계획의 누락·참고점 | 반영 내용 |
| --- | --- | --- | --- |
| S01 | **취지 일부 채택·원인 설명 정정.** `app.py:1343-1371`의 raw body 처리에서 AI 파일/CSV가 기존 예외에 포함되지 않고 CSV export 전체 텍스트가 응답 본문 경로를 탄다. body 예외가 바깥의 포괄 except로 빠지면 사건 push도 생략될 수 있다. 다만 UTF-8 `UnicodeDecodeError` 단정과 ‘기존 파일 metadata 분기’ 설명은 그대로 확인되지 않는다. | 감사 내용 보존 원칙만 있었고, 거부 전 multipart/대용량 CSV와 사건/본문 예외 경계를 구체화하지 않았다. | 원시 전송 본문을 logger가 재소비하지 않기, 거부도 metadata 사건 보존, CSV 업무/결과는 구조화된 내용 또는 보호된 원문/참조로 보존, 물리 감사 저장 예산·실패 정책 명세. AI 본문 전체 제외는 채택하지 않는다. |
| S02 | **핵심 지적 채택.** `maintenance_request_gate`는 비정상 점검 상태에서 쿠키 없는 internal worker 요청을 먼저 막는다. `job_actor`는 `connect()` 후 Domain에서 점검을 확인한다. | 기존 계획에 ‘오류 종결·복귀’ 원칙은 있었으나 전역 before_request와 internal 완료 보고의 충돌이 없었는지 시험하는 계약이 빠졌다. | 신규 claim/모델 호출 차단과 인증된 기존 lease 정리를 분리, 업무 DB를 열기 전 점검 확인, callback의 별도 AI 원장 처리·허용 경로/상태 명세. 내부 prefix 전체 무조건 면제는 하지 않는다. |
| S03 | **채택.** `store.claim()`은 running을 커밋한 뒤 반환한다. HTTP claim은 actor의 AssistantError만 처리하고 도구/context 준비와 그 외 예외를 모두 종결하지 않는다. 모델 호출 전 500에도 작업/슬롯이 남을 수 있다. | 계획은 provider별 실패 격리는 다루었지만 슬롯 선점 직후 actor·도구·context·provider/key/profile 준비의 전체 예외 경계를 명시하지 않았다. | 발신 전 확정 실패와 발신 불명확 상태 분리, 준비 단계 전체의 단일 종결 책임, 미확정 카드/예약/슬롯 일관 정리, 준비 단계마다 fault injection 회귀. |
| S04 | **취지 채택·표현 정정.** `store.cancel`은 `COALESCE(?,error)`로 새 사유를 우선한다. worker는 event가 cancel을 반환해도 offset을 증가시키고 계속 flush할 수 있다. 보고서의 `flush(True)` 이름은 실제 `flush()`와 다르다. | 오류를 사용자에게 보존한다는 원칙에 ‘최초 사유를 후속 오류가 덮어쓰지 않음’과 ‘취소/수락 상태 분리’가 없었다. | 최초 원인/코드 불변, 후속 진단 별도 기록, 서버가 수락한 offset만 반영, 중단 후 일반 chunk 전송 중지와 자체 종료 보고 유지. 권한/점검 실행 차단은 사유 표시와 독립적으로 강제한다. |
| S05 | **기존 보류 유지·추가 주장 미채택.** AI-TECHDEBT-001은 이미 사용자 지시로 보류한 항목이다. 현재 `lineup_node_service.py`의 `_required_int`는 EN rev.2와 KO rev.2를 같은 docstring에 둔다. 보고서의 rev=1 분리 블록 설명과 다르다. | 주석 보류는 기존 계획에 이미 있었다. 현재 소스와 다른 루트 형식 오류를 새 구현 필수 작업으로 넣을 근거가 없다. | 백로그 보류와 향후 실제 소스 기준 재점검만 유지한다. 이번 계획이나 사용자 지시를 주석 일괄 개선 승인으로 확대하지 않는다. |

**S01에 대한 주의:** 참고한 [Werkzeug 3.1.3 공식 구현](https://github.com/pallets/werkzeug/blob/3.1.3/src/werkzeug/wrappers/request.py#L386)의 `Request.get_data(as_text=True)`는 decode 시 `errors="replace"`를 사용한다. 따라서 바이너리라는 이유만으로 그 호출의 UnicodeDecodeError를 확정할 수 없다. 반면 stream 읽기의 용량/연결 예외와 무조건적인 본문 재읽기 비용은 별도의 위험이다. 실제 배포 버전/요청 조건의 재현은 후속 합성 검증에서 확인한다. 보고서의 제외 조건에 `not startswith`를 넣으라는 문구도 실제 boolean의 방향을 다시 검토해야 하므로 권장 예시를 그대로 붙이지 않는다.

S01의 감사 보완은 원문 업무 내용을 버리라는 뜻이 아니다. 정상 질문·추론·답변·업무 제안/결과·CSV 검증/확정 내용을 보존하며, 파일 원문이 이미 보호된 저장소에 있으면 그 참조를 사용한다. CSV export처럼 증거 원문을 별도로 보존할 경우 접근권한·기간·물리 예산을 명세한다. 거부된 body를 감사 목적으로 억지로 읽어 성공/실패 사건을 잃지 않게 하는 것이 핵심이다.

## 원본의 상세를 그대로 채택하지 않은 근거

| 005 서술 또는 예시 | 현재 소스에서 확인한 값·계약 | 처리 |
| --- | --- | --- |
| `/equipment/ai`, `/internal/ai/jobs/claim`, `deploy/systemd/...` 및 `scripts/...` | 사용자 화면은 `/assistant`, claim은 `/internal/ai/claim`, 후보 worker unit은 `overlay/systemd/`, fixture는 `overlay/tests/` | 계획/시험은 실제 등록 경로를 기준으로 한다. |
| CPU loopback `127.0.0.1:8081`, Qwen3-4B, context 12,288 및 외부/LAN 호출 차단 | worker 기본 upstream은 LAN `192.168.0.14:8080`, 모델은 `qwen3.8-flash-next-iq3_xxs`. loopback 강제는 장비관리 internal API 경계다. 해당 12,288 제한은 현재 후보에 확인되지 않는다. | 다른 PC의 LAN AI를 연결하는 사용자 의도를 잘못 축소하지 않는다. 실제 profile의 context를 검증한다. |
| 32MB+32MB·`storage_meta` | 계정별 32,000,000자+추가 기본 32,000,000자·`storage_accounts` 원장 | 문자/물리 바이트를 구분한 기존 006 명세를 유지한다. |
| 전역 index가 queued/running, 도구 4라운드 | index 상태는 running/draining/recovery_required. 라운드당 호출 4개와 턴당 모델 호출 최대 6회는 서로 다른 제한이다. | 새 그룹별 큐에서 대기 상태를 잘못 단일 잠금으로 묶지 않는다. |
| `AssistantError(message,503,'MAINTENANCE_ACTIVE')`, `INTERNAL_ERROR` | 현 AssistantError는 message/status 두 인자이며 기존 사유 코드에는 PROCESSING_FAILED 등이 있다. | 오류 타입·허용 코드와 일치하도록 구현 명세/회귀를 작성한다. 임의 예시를 그대로 적용하지 않는다. |
| 장비/파일 삭제, 카탈로그 승인·반려를 포함한 PASS 항목 | 사용자는 일반 사용자 업무에 한정하고 장비 삭제·관리자 승인/반려 등을 허용하지 않았다. 현재 모델 도구도 이를 제공하지 않는다. | 승인 범위 확대 근거로 쓰지 않는다. |
| 루트 주석 rev=1 분리 형식 오류 | 현재 `_required_int`는 한 docstring의 `[EN rev.2]`/`[KO rev.2]`와 구현을 가진다. | 현재 결함으로 확정하지 않는다. 이 보고서는 comment-sync 전수 실행 통과를 주장하지 않는다. |

이 불일치 때문에 005의 모든 PASS를 독립적으로 재확인한 것으로 보고할 수 없다. 이번 목적은 확장 계획의 누락을 찾는 것이므로 유효한 구체적 지적에 집중하고, 범위/상수/경로는 실제 소스와 사용자 결정에 맞췄다. Gemini의 원래 평가 등급·원문은 그대로 보존한다.

## 006 반영 위치와 향후 검증

1. **1절:** 005가 완료되었음을 반영하고 S01~S04의 소스 대조·선행 보완 표, 원본 서술의 채택 한계를 추가했다.
2. **7절:** claim 이후 준비 단계 전체의 종결, 점검 중 신규 업무와 기존 정리 분리, 최초 사유/수락 offset의 계약을 추가했다.
3. **8절:** 파일/CSV의 원시 전송과 감사 업무 증거를 구분하고, 본문 실패가 사건 전체를 지우지 않는 감사 실패 격리를 추가했다.
4. **9절:** 0단계를 선행 결함 보완/실제 전역 훅 회귀로 강화하고, 그룹별 확장 이후에도 같은 계약을 확인하게 했다.

회귀는 기존 after_request 훅뿐 아니라 실제 maintenance_request_gate와 인증 순서를 합성 fixture에 연결해야 한다. 파싱 전 401/403/413/503 파일 거부, CSV export 증거 보존, 점검 도중 완료 callback과 업무 DB 접근 금지, 각 준비 단계 예외, 최초 오류 뒤 후속 offset/취소를 검사한다. 다중 provider에서는 A의 준비 실패/종료 불명확과 B의 독립 실행, 전역 점검의 모든 그룹 신규 발신 차단을 함께 확인한다.

확장이 가능하다는 결론과 세션 복원 포함·자동 모델 조회/선택 기본·관리자 선택형 수동 등록·고급 연결 설정/주석 작업 보류는 유지한다. 코드·Staging·운영 설정/DB를 수정하지 않았고 실제 앱·모델 호출/새 기능 회귀 시험을 실행하지 않았다. 현재 결함이 수정되었다고 보고하지 않는다.

## Validation 1~8 순차 기록

| 단계 | 근거·긍정적 판단 | 위험·실행 조건 |
| --- | --- | --- |
| 1. 거버넌스 | 005 Plan/Task의 completed와 Report 원본을 확인했다. recorder/profile/context·validate를 확인하고 008 Task를 만든 뒤 검토했다. 변경은 006 Plan과 008 Task/Report에 한정한다. | 코드 수정 승인으로 해석하지 않고 Gemini 원본·현재 Staging·기존 기록을 보존한다. |
| 2. 사용자 의도 | 확장 계획의 누락을 찾는 데 집중해 S01~S04와 기존 S05 보류를 구분했다. 세션 복원·자동 기본/관리자 수동 옵션·고급 설정 보류를 유지했다. | 평가 완료를 코드 수정/병합 승인으로 확대하지 않는다. 기존 일반 사용자 범위를 Gemini 기준표의 삭제·승인/반려로 바꾸지 않는다. |
| 3. 논리 | 실제 전역 게이트·claim 커밋/예외 경계·cancel SQL/worker offset을 대조했다. 준비 실패와 발신 불명확, 취소와 수락 여부를 구분하도록 계획을 강화했다. | 신규 scheduler에서도 점검/준비 예외 때문에 그룹 슬롯이나 예약이 고착되지 않아야 한다. 확정되지 않은 종료를 시간만으로 해제하지 않는다. |
| 4. 운영 영향 | 기존 after_request만 포함한 fixture의 범위 한계를 확인하고 실제 before_request/인증 순서까지 합성 통합할 계획을 추가했다. | 운영 DB/앱을 열어 검증하지 않았다. S01~S04 보완·회귀가 실제 확장의 선행 조건이며 현재 해결 완료가 아니다. |
| 5. 보안·예외 | callback은 worker/lease/허용 상태를 검사하고 업무 DB 점검 차단을 유지한다. 감사 원문·업무 증거 보존과 바이너리 전송/인증 원문 보호를 구분했다. | internal prefix 전체 면제·AI 본문 전체 제외·권한 원문 노출은 채택하지 않는다. 라이브러리 원인 주장은 참고 버전과 실서버 재현을 구분한다. |
| 6. 복귀 | 계획만 변경해 실행/데이터 복귀 대상은 없다. 향후 AI/업무 DB 일관 백업 전에 접수 중지·자체 종료 확인, 지연 callback의 epoch/lease 격리를 추가했다. | 이전 완료/오류/영수증을 삭제하거나 미종료 작업을 재발신해 복구하지 않는다. |
| 7. UX | 최초 원인과 후속 진단을 구분하고 재접속 뒤에도 사유를 보존하는 회귀를 추가했다. 감사 저장 실패도 성공으로 숨기지 않는 조건을 명시했다. | 표시 사유를 보존해도 권한 철회/점검 실행 차단은 계속 강제해야 한다. 삭제/관리자 업무를 UI에 새로 노출하지 않는다. |
| 8. 메타 | Gemini 005 Plan/Task/Report, Staging 16개, 운영 app·루트 참고·007 기록을 포함한 22개 파일의 검토 전후 SHA-256이 동일하다. 갱신한 3개 문서의 내부 링크도 모두 유효하다. | 원본 평가를 덮어쓰거나 근거가 다른 PASS/권장 코드를 그대로 승계하지 않았다. 추가 구현·앱/모델 실행·운영 DB 접근·신규 런타임 회귀는 수행하지 않았다. |

## 최종 상태

계획 반영 완료. S01~S04는 실제 구현 착수 시 선행 보완·회귀로 수행할 항목이고 현재 코드에서 해결된 상태가 아니다. S05는 기존 사용자 보류를 유지한다. 005의 평가 범위는 현재 단일 provider Staging이므로, 그것을 다중 provider 기능 자체의 검증 완료로 확대하지 않는다.
