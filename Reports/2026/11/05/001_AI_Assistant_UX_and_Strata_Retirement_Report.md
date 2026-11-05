---
artifact_id: REPORT-20261105-001
work_id: REVIEW-20261105-AI-UX-RETIREMENT
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 UX·응답 거부·Strata 화면 폐기 검토

## Validation 1 — 거버넌스

질문·원인 분석·개선/폐기 계획으로 분류했다. 운영 소스·실제 메뉴/설정·대화 변경을 이번 검토에 포함하지 않는다. recorder 정상, profile legacy/runtime-session-mismatch, governance 1.8.1/44 nodes/오류·경고 0이다. context의 두 pack과 DB 열람/서버 실행의 관련 노드를 읽었다. 기존 tracked dirty 9개는 보존한다. 실제 대화는 새 온라인 백업을 로컬에 받은 뒤 읽는다.

## Validation 2 — 사용자 의도

여섯 항목을 모두 대상으로 한다. 표의 시각적 형식, 지정한 nekohost 대화의 실제 실패 원인, 짧은 모델명, 관리자 센터 동선, 모바일에서 확인 가능한 처리 피드백, 기존 Strata 시험 UI 폐기를 각각 검토한다. 공유 Strata API/다른 서비스와 새 AI 대화/이력을 폐기 대상으로 확대하지 않는다. 과거 배포 시험 통과를 현재 요청 성공의 근거로 재사용하지 않는다.

## Validation 3 — 원본 증거와 논리

### 사본·검토 범위

실제 서버 HEAD는 `3d9dacc65b83b754f7162b5ba520b0f130551208`이며 로컬과 같다. 2026-11-05 07:53 KST의 각 DB 온라인 백업을 로컬 `instance/ai-review-20261105/20261104T225310Z`에 받았다. 디렉터리는 ACL을 현재 사용자로 제한했고 파일별 SHA가 서버 manifest와 일치한다. 이 시점 이후 지정 대화를 읽었다.

| 사본 | bytes | SHA-256 |
| --- | ---: | --- |
| equipment.sqlite3 | 130,433,024 | c9b0fdb7f11fed826684f375e4c9c1308843a065a379ec724c15c52c2e383246 |
| assistant.sqlite3 | 229,376 | bf0282f14797a50a99c575806d33a5cd6dcd51ebc176ef4d2dc64e3b15152243 |

두 DB의 백업은 각각 일관된 사본이며 두 파일의 원자적 동일 시점을 주장하지 않는다. 계정은 정확한 LoginId `nekohost`로 한 명을 확인하고 그 owner의 제목 '관리자 모델 기능 시험'만 열람했다. 실제 장비의 이름/일련번호/메모나 전체 대화 원문을 보고서에 복제하지 않았다. 원본은 private 사본에 보존한다.

### 1번: 표가 문자 그대로 보이는 원인

`static/js/equipment_ai.js:30`의 `markdown()`은 코드 펜스·일부 제목/목록·굵게/허용 링크를 DOM으로 만든다. 표의 헤더·구분 행을 인식하거나 table 요소를 만드는 분기가 없다. 파이프 행도 각각 p가 되므로 CSS만으로 수정할 수 있는 상태가 아니다. 저장 응답에는 이미 정상적인 Markdown 표가 있어 새 렌더러로 과거 응답도 표시할 수 있다. DB 내용 재생성이나 실모델 응답의 HTML 허용은 필요하지 않다.

권장안은 기존 DOM 기반 렌더러의 표 확장이다. 기준은 [GFM 표 명세](https://github.github.io/gfm/#tables-extension-)의 헤더/구분 행·셀·정렬 처리로 제한한다. HTML 실행을 허용하지 않고 모바일 overflow를 표 내부로 한정한다. 스트리밍의 미완성 표와 코드 펜스, 긴 표 비용도 검증해야 한다.

### 2번: 실제 표 요청 실패 원인

| 시각(KST) | 실제 요청/종료 | 증거 |
| --- | --- | --- |
| 2026-11-05 07:40:11~07:40:21 | '내 장비 리스트를 표 형태로 출력해주세요' → failed | job `77d91926a30b4fa797b0066c46769aa5`, INVALID_TOOL_CALL |
| 2026-11-05 07:40:31~07:40:44 | '내 장비 리스트를 출력해주세요' → done, 2단계 | job `b0b282283d374e96b19fac7cf81b0103`, search_equipment 뒤 2건의 Markdown 표 |

실패 이유는 저장된 job에 **'AI의 작업 요청 형식이 올바르지 않아 작업을 중단했습니다. 허용되지 않은 선택 값입니다.'**로 남아 있다. 당시 worker 완료 보고의 감사 본문에서 다음 인자를 확인했다.

```json
{"scope":"my","query":"","page":1,"status":"","due":""}
```

현재 `policy.py`의 `search_equipment.status` enum은 ACTIVE/LOANED/REPAIR/DISPOSED다. 선택 필드를 생략하면 정상이고 빈 값을 제공하면 거부된다. `query:""`와 `due:""`, page 1과 scope my는 허용된다. 뒤이은 성공 요청의 실제 인자는 `{"scope":"my"}`였다. 도메인 검색은 상태가 비어 있으면 원래 필터를 넣지 않으므로, 선택 필터의 wire schema/검사와 조회 의미를 맞추는 개선이 타당하다.

운영 소스의 순수 validator를 Linux에서 네 경우로 호출해 원인을 교차 확인했다. 앱을 설치/import하거나 모델/큐 요청을 만들지 않았다.

| 검사 | 현재 결과 |
| --- | --- |
| 실제 실패 인자 그대로 | 동일한 '허용되지 않은 선택 값' 오류 |
| 같은 인자에서 빈 status만 생략 | 통과 |
| 조회 status='ANY' | 거부 |
| 실제 상태 변경 도구의 status='' | 거부 |

따라서 조회 도구에 한정된 '상태 필터 없음' 계약/정규화를 보완한다. 형식 오류 후 후속 업무를 중단하는 정책은 유지하고, 알 수 없는 값·쓰기 빈값까지 포괄 허용하거나 실패한 과거 job을 성공으로 고치지 않는다. worker finish endpoint의 HTTP 200은 완료 보고를 수락한 상태이며 최종 사용자 작업 성공 판정은 job.state/error_code를 기준으로 했다.

추가 발견: 지정 대화에는 최초 probe 제목/nonce와 이후 실제 chat이 함께 저장됐다. `context.py:build_context()`는 완료 job의 purpose를 구분하지 않아 이 진단 기록도 일반 대화 문맥에 넣는다. 실제 기능 안내 답변에도 이전 '관리자 모델 기능 시험'을 언급한 흔적이 있다. 신규 진단은 관리자 영역으로 분리하고, 기존 mixed 대화의 실제 chat은 보존한 채 문맥에서 probe 행만 제외하는 안을 계획에 포함했다. 이 사항을 빈 status 오류의 원인으로 대체해 설명하지 않는다.

### 3~5번: 표시·메뉴·관리 UX

| 항목 | 현재 확인 | 계획의 핵심 |
| --- | --- | --- |
| 드롭다운 | 현재 연결 이름 260Strata, 모델 표시명 Qwen3.8 Flash Next. `modelControls()`가 기능 문구까지 option에 덧붙임 | 연결/모델명과 확인된 양자화만. 기능·오류는 별도 상태 영역 유지 |
| 메뉴 위치 | 실제 settings 메뉴 ParentMenuCode=NULL, URL=/admin/ai/providers. admin grant 1만 존재. 메인은 NULL 부모, 관리자 센터는 admin_center 자식 조회 | 신규 seed와 기존 행 metadata를 함께 이전. 일반 사용자 AI 메뉴와 관리자 권한 검사는 유지 |
| 저장 피드백 | `provider-notice`가 form보다 위에 있고 모든 결과를 notice 문자열로 표시. 모델 저장·폐기·조회·수동 추가에도 동일한 시각적 처리 흐름 없음 | 공통 loader + 결과 dialog + 조작 잠금/중복 방지. 성공/실패/불명확/재시험 필요 구분 |

기존 `common.js`의 showGlobalLoading/hideGlobalLoading과 root_frame overlay를 확인했다. native dialog를 사용하는 기존 개별 기능도 있지만, AI 관리 화면이 재사용할 전역 성공/실패 modal 함수는 확인하지 못했다. 새 화면용 재사용 컴포넌트를 계획하고 다른 기능의 alert/confirm 교체로 범위를 넓히지 않는다.

저장 ACK 후 목록 갱신이 실패하면 현재 try/catch가 저장 실패처럼 보이게 할 수 있다. 저장 결과와 후속 GET을 분리해야 한다. 오래 걸리는 기능 시험은 접수와 생성 완료를 나누어 표시하고, 접수 후 오랫동안 전역 overlay로 화면을 막지 않는다. cancelled/recovery_required도 done과 다른 결과다.

### 6번: 폐기 의존성

현재 옛 STRATA_ENABLED와 새 USER_AI_ENABLED는 둘 다 true다. 서버의 기존 Nginx snippet도 존재한다. app/worker에는 각각 새 USER_AI_STRATA_KEY가 있고 두 값이 같음을 원문 출력 없이 확인했으며 worker는 active다. root 전용 옛 key 파일은 무입력으로 읽지 않았다.

폐기 범위는 옛 `/ai`·`/ai/console`, `utils/strata_integration.py`, 전용 화면/bridge/vendor 자산, `/strata/` Nginx gateway와 옛 auth/health 경로다. 새 `utils/ai_assistant`의 Strata adapter·직접 API·USER_AI 설정·대화/영수증/감사는 보존한다.

중요한 잔여 의존성은 `tools/deploy_user_ai.py:32`의 옛 root key 파일과 `prepare-key`다. 현재 연결이 새 private 환경의 키로 작동하더라도 bootstrap 도구가 이 파일을 읽는다. 따라서 옛 UI를 끄는 것과 실제 키 폐기를 한 작업으로 묶지 않는다. helper의 키 입력 경로를 먼저 정리·검증하고 Nginx 설정·메뉴 metadata·옛 localStorage 대화/내보내기·라이선스 근거를 보존한 뒤 전용 자산을 회수해야 한다.

## Validation 4 — 운영 영향과 순서

계획은 기존 구조의 확장/수정으로 실현 가능하다. 전체 AI 기능을 폐기해 재작성할 근거는 없다. A(표·조회·probe 문맥)→B(이름·관리자 동선/UX)→C(옛 Strata UI/gateway 회수) 순서로 묶었다. 새 API를 먼저 안정화한 뒤 옛 입구를 닫는다.

표/이름은 표시 변경이며 과거 응답·호출 ID·동결된 출처를 수정하지 않는다. 메뉴는 신규 설치와 기존 운영 행을 모두 다루는 metadata 이전이다. 새 외부 라이브러리나 업무 테이블 DDL은 현재 제안의 필수 조건이 아니다. 서버 멱등 키 등 추가 schema가 필요해지는 세부 구현은 Staging 설계에서 범위를 명시한다. 운영 app·worker·Nginx·모델을 이번 검토에서 재시작하지 않았다.

## Validation 5 — 보안·예외

- 표 셀은 모델이 준 HTML/JS/외부 이미지가 아니라 안전한 DOM text로 표시한다. 파이프/코드/잘못된 헤더/큰 표와 악성 링크를 검증한다.
- 조회 빈 필터만 뜻을 보존해 정규화한다. owner/SessionToken/CreatedAt/메뉴/Origin/CSRF·고정 도구와 write 확인 카드는 유지한다.
- 이름을 줄여도 모델 사용 불가·대화 전용 사유와 disabled 상태를 유지한다. 실제 호출 ID/주소/인증키를 이름 표시용으로 공개하지 않는다.
- 관리자 메뉴 이동은 노출 위치의 변경이다. 직접 URL/API도 계속 관리자 검사로 보호하고 일반 사용자 grant를 만들지 않는다.
- modal은 성공/실패/취소/결과 불명확을 구분한다. 알려지지 않은 저장 결과를 자동 POST 재시도로 중복 생성하지 않는다. 오류 문구에 API 키나 내부 stack을 넣지 않는다.
- UI 폐기 시 새로운 Strata API 연결·암호화 키·allowlist·worker token을 보존하고 옛 프록시가 남지 않게 차단 테스트를 한다. 다른 서비스의 작업이나 공유 모델 전역 제어를 요구하지 않는다.

## Validation 6 — 보존과 복구

원본 대화·실패 job·probe·감사는 변경하지 않았다. 표 렌더러는 기존 문자열을 그대로 읽으므로 이전 코드 복귀 시 같은 기록을 사용할 수 있다. 메뉴 이전은 정확한 행/부모/권한의 사전 사본을 기준으로 되돌린다. mixed 대화를 통째로 숨기거나 지우지 않는다.

옛 UI 폐기는 앱/메뉴/Nginx 설정·공개 static 자산·bootstrap helper를 함께 검토한 뒤 순서대로 수행한다. 옛 환경·메뉴 metadata·소스/라이선스를 보존하고 복구 경로를 둔다. AI DB나 업무 DB를 되감아 이력/감사를 없애지 않는다. 옛 browser localStorage는 새 DB와 구별하고 임의 삭제/자동 병합하지 않는다.

## Validation 7 — UX·교차 시나리오

| 시나리오 | 구현 후 확인할 결과 |
| --- | --- |
| 지정 문장을 그대로 재요청 | 정상 본인 조회 뒤 실제 표, 같은 질문을 '표' 없이 바꾸는 우회가 불필요 |
| 기존 정상 표 응답 재접속 | 과거 원문을 고치지 않고 table로 표시 |
| 순수 probe vs 기존 mixed 대화 | 진단은 관리자에서 조회, 사용자의 실제 대화는 유지·계속 가능 |
| 모바일 하단 저장/폐기 | 진행 중 화면과 완료/오류 dialog가 현재 위치에서 인지됨 |
| 저장 성공 후 목록 GET 실패 | 저장 성공을 유지하고 목록 갱신 실패를 별도 안내 |
| 응답 유실·두 번 클릭·관리자 409 경합 | 자동 중복 생성 없이 확인/재시도 경로와 입력을 보존 |
| 기능 시험 대기·실패·취소·종료 불명확 | 각각의 상태/사유를 표시하고 실제 생성/외부 서비스는 UI 편의로 끊지 않음 |
| 옛 주소·정적 자산·proxy 직접 접근 | 폐기 안내/차단, 새 API/관리자/로그인·다른 장비 기능은 정상 |

390/430px·태블릿·desktop, light/dark, 키보드/focus, 긴 표/이스케이프·스트리밍을 수용 기준에 포함했다. 이번 검토에서는 새 화면 구현·실제 화면 재촬영·실모델 재발신을 수행하지 않았다.

## Validation 8 — 결론과 한계

여섯 항목의 원인과 수정 방향은 [계획서](../../../../Plans/2026/11/05/001_AI_Assistant_UX_and_Strata_Retirement_Plan.md)에 정리했다. 2번의 실제 실패 원인은 감사 원문과 job 상태, 뒤이은 성공 요청 및 순수 validator 네 경우로 교차 확인했다. 전체 모델 불능·권한 확대 필요·표 출력 금지라고 일반화하지 않는다.

이번 산출물은 계획/검토이며 구현 완료 보고가 아니다. 운영 코드·메뉴·설정·업무/대화 데이터는 그대로이고 검토용 private 백업과 세 문서만 추가했다. 기존 tracked dirty 9개와 과거 보고서는 보존한다. 과거 112/93 통과는 기준선으로만 인용하며 새 기능의 회귀 통과를 주장하지 않는다. 구현/배포 완료와 실제 새 질문 성공은 후속 승인 범위의 작업과 별도 검증으로 남긴다.

종료 확인: 세 문서의 work_id·코드 펜스·로컬 링크 검사가 통과했다. governance validate는 오류/경고 0, recorder는 정상이다. Git index는 비어 있고 tracked diff는 기존 9개 파일만 남았다. 서버 HEAD는 같은 3d9dacc이며 tracked 소스 diff가 없고 worker는 active다. 소스 commit/push·서비스 재시작·모델 생성은 수행하지 않았다.

## 추가사항 7 — 계획 보완 검토

1. **거버넌스:** 사용자는 대화 휴지통/복구/자동·직접 영구삭제를 계획에 추가하도록 요청했다. 실제 삭제나 schema 변경은 승인 범위에 넣지 않는다. recorder 정상, legacy/runtime-session-mismatch, validate 오류/경고 0, 새 context의 두 pack과 schema 관련 노드를 읽었다.
2. **의도:** 평소 삭제는 휴지통 이동, 이동 시점부터 30일 뒤 자동 삭제, 휴지통 안에서 직접 영구삭제, 복구 후 재이동은 새 시점부터 30일이라는 조건을 모두 반영한다. 이번 변경은 기존 1~6 항목을 보존하는 계획 보완이다.
3. **정적 논리:** `store.py`/`providers.py`/`audit.py`/`domain.py`와 기존 private 백업의 schema만 읽었다. 백업은 mode=ro&immutable=1로 열었고 v3/삭제 필드 부재·종속 FK·비참조 선택 이력·storage_accounts를 확인했다. 대화 삭제는 예약/문자 원장과 종속 행을 함께 처리해야 하며 현재 부분 unique index에 의존한 실행 job 단순 삭제는 단일 그룹 점유를 해제할 수 있다. Plan에 별도 최소 실행 제어 원장·늦은 callback 차단을 선행 요건으로 넣었다. 만료/복구/재이동 경합은 서버 시각·lifecycle_revision·동일 write transaction으로 재검사하고 정리는 인덱스/작은 배치로 제한한다.
4. **운영 영향:** `/assistant`의 인증된 경계 안에서만 대화 lifecycle을 확장한다. 장비 삭제/관리자 권한 확대/공유 Strata 제어는 추가하지 않는다. 기존 v3 기동 검사와 providers.migrate의 버전 갱신도 함께 바꾸는 v4 이전, worker/점유/API/UI 이후 timer 활성화 순서를 계획했다. 현재는 문서 세 개만 수정했고 서버 접속·배포·모델 호출·실제 데이터 삭제를 하지 않았다.
5. **보안/예외:** owner+account_key를 유지하고 CSRF/Origin·자료형·서버 시각·revision·조작 식별자를 검사한다. 타 계정 조회/복구/삭제와 브라우저 시각 변조를 막고 제목/메시지는 기존 안전한 renderer로 표시한다. 삭제를 AI tool로 노출하지 않는다. 만료 후 늦은 복구·중복/응답 유실·대화/GC/확정 경합·늦은 worker callback을 수용 검사에 포함했다. 독립 감사와 업무 영수증은 사용자 기존 보존 지시에 따라 계속 보존한다.
6. **복구:** 기존 대화는 정상 상태로 추가 migration하고 사전 백업/원장·FK 대조를 계획했다. timer 정지와 v4 호환 코드 복귀를 함께 정의해 옛 코드가 휴지통을 재노출하거나 버전 검사에서 실패하는 부분 rollback을 피한다. 실제 영구삭제는 기능 rollback으로 되살릴 수 있다고 주장하지 않으며 백업 복원 시 삭제 이력을 재적용한다. 현재 DB는 읽기 전용 schema 확인 외 변경하지 않았다.
7. **휴먼 에러/UX:** 정상 목록의 이동과 휴지통의 복구/영구삭제를 분리하고 대상 제목·만료일·복구 불가 확인·처리/오류 modal을 계획했다. 복구 후 재이동만 새로운 30일을 시작하며 이미 휴지통인 항목의 중복 요청은 연장하지 않는다. 복구는 취소된 실행/미확정 업무를 되살리지 않는다. 문자/200개 보관 한도는 휴지통도 포함함을 알리고 두 탭·모바일·키보드와 결과 불명확 상태를 검증 대상으로 넣었다.
8. **메타/결론:** 기존 Plan 1~6을 보존하고 항목 7·전체 기준표·실행 묶음 C를 추가했다. Task 체크와 이 검토를 같은 work_id로 갱신했다. 세 문서의 frontmatter/work_id/코드 펜스/로컬 링크 검사와 governance validate(44 nodes, 오류/경고 0)가 통과했다. 기존 tracked dirty 9개/기타 untracked 파일은 그대로이며 소스 commit/push나 scratch 파일을 만들지 않았다. 이번 결과는 **계획 보완 완료**이며 휴지통 기능 구현/신규 동작 테스트 완료가 아니다.
