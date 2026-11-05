---
artifact_id: REPORT-20261105-017
work_id: RELEASE-20261105-AI-DISPLAY-STATUS
owner: Codex
status: complete
approval: staging-and-production-explicit
---

# AI 표시 정책·상태 안내 누적 후보 운영 반영 검증

recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0 및32개 context 노드를 확인했다. 기존 공통 노드를 승계하고 이번 deploy/staging-merge/completion/server 경로를 확인했다. 사용자 명시 승인은 검증 결함 수정과 누적 Staging의 운영 서버 반영까지 포함하므로 재승인 질문 없이 수행한다.

## 구현 전 Validation1~8

1. 거버넌스: Task017과 계획을 먼저 기록하고 기존016 후보/원문을 보존한다. 운영 병합은 정적/화면 검증 후 수행하며 현재 사용자 승인으로 그 단계까지 허용된다.
2. 의도: 내부 ID는 일반 답변에서 배제하도록 암시하되 실제 도구 참조는 유지한다. 입력칸 위에 노랑/빨강 원인 안내를 추가하고 기존1~10을 포함해 운영 반영한다.
3. 논리: 도구 payload 중복/예산 초과·무차별 숫자 삭제를 피한다. 상태 banner는 기존 수신/TTL 렌더를 공유해 중복 poll과 상단/하단 불일치를 막는다.
4. 운영 영향: 현재 후보의 새 모듈·frame·worker까지 배포 대상 누락을 확인한다. 실제 DB 사본의 기동과 모든 기존 행/업무 데이터를 검증하고 동일 commit으로 전환한다.
5. 보안: 원문 감사/권한/CSRF·내부 도구 ID는 유지하고 사용자 데이터의 지시문을 신뢰하지 않는다. 상태 reason은 안전한 텍스트이며 endpoint/key/타 사용자 내용은 공개하지 않는다.
6. 복구: private DB/설정/소스/서비스 백업과 이전 commit을 보존한다. 기존 정상 요청·외부 서비스는 중지하지 않으며 실패 시 own web/worker만 원상 복귀한다.
7. UX: 표시용 필드/시리얼·수량 보존, banner의 위치/색/사유/TTL·긴 글자/낮은 높이·오류 notice 공존과 실제 운영 화면을 확인한다.
8. 메타: 기존016의 완료 증거는 불변이다. 정책 지침과 강제 보안 경계, 합성 검증과 실제 운영 확인을 구분하며 runtime 미검증 모델을 검증됐다고 기록하지 않는다.

## 구현·사전 감사

ID 지침은 SYSTEM/읽기 도구 설명과 결과당 한 번의 bounded `display_policy` 메타로 전달한다. 원본 ID/Revision/링크와 감사 내용은 그대로 유지한다. 실제 claim→조회→상세→수정 제안/확인, 모델 전환 인계, 업무 숫자 보존·권한 경계의 신규 Linux 합성7개는 전부 통과했다(2.729초, skip0). 이는 모델에 전달되는 표시 계약의 검증이며 임의 모델 답변의 강제 검열 증명은 아니다.

입력칸 안내는 상단과 하나의 동기 render/TTL을 공유한다. 최초390px dark 화면에서 긴 사유를 넣었을 때 채팅 최소 높이/가로 경계 검사1건이 실패했다. 이 실패는 `017_AI_Display_Status_Release/smoke-banner-01`에 보존하고 원인 수정 후 재검증한다. 정상 진행을 성공으로 바꾸거나 기준을 낮추지 않는다.

서버 읽기 감사: local/server HEAD `82a936175b28a2dd02942ded34d884c4ca17ec0b`, 정확한 own web PID867701/worker867719, queued/running/draining/recovery job 및 guard0, maintenance NORMAL revision12. retention timer active/waiting·service inactive다. 두 환경의 DB 경로·키/epoch·소유권/0600 및 실행 환경 일치를 값 비공개로 확인했다. 기존 helper는 원격과 SHA `cb525efd49e38c87a054a37ca00e36a45cc8b8cb05d0390ebd34828c15256830`가 같았다.

사전 감사에서 jobs 없는 active guard를 놓치는 helper 판정과 retention 전환 경쟁을 확인했다. 계획017에 두 gate의 동일 snapshot 판정 보강과 timer 상태 보존/일시 정지·실행 중 cleanup 정상 종료 대기를 추가했다. 최종 pull 후 실제 DB 사본 검사와 실패 시 접수 차단/최신 데이터 보존 복구는 부모가 단독 수행한다.

## Staging 통합 검증

Python AST23개/JavaScript 구문11개와 Node 출력 presenter18개가 통과했다. Linux 격리 backend는 **211개 통과**, 실패/오류/skip0,49.592초이며 digest `900a44f52170f031d3a0a26b34811b06f7bda5eaee7d1629da3c959c1fa73da1`다. 기존194개에 ID 표시7개와 배포 guard10개를 더한 수이며 운영 앱 import/DB 사용/모델 호출은 없다.

최초 배너 실패는 border-box 테두리2px 누락으로 pane117.953px가 된 실제 제품 결함이었다. `fitViewport`의 fixed 높이를 두 getBoundingClientRect 높이 차이로 계산하여 테두리·소수점을 포함했다. 신규8화면(320/390/820/1440×라이트/다크) **504개 검사 통과**.500자 사유 전문과 확대글자/620px 높이에서도 pane최소120.094px를 확보했다. 기존 기준 완화 없이 전문 보존 검사와 측정 완료 동기화를 강화했다. 별도 기존 UI4화면642개·viewport4화면142개도 통과했다. 원문과 스크린샷은 새017 결과에 보존한다.

## 배포 준비·백업

서버 private release `instance/releases/20261105-ai-ux-polish-20261105T073602Z-f7c02f`에 두 DB·환경2개·unit3개·maintenance·이전 Git 소스 archive·timer 상태를 보존했다. 두 SQLite main 파일은 immutable 읽기의 integrity/FK를 통과했다. 현재PC 사용자 단독 ACL `.codex/private-releases`에도 stable manifest 포함13개 파일의 SHA를 대조했다. 초기 manifest가 프로세스 종료 때 사라지는 SQLite WAL/SHM 임시 sidecar까지 기록한 문제는 원문을 남기고 별도 stable manifest에서 제외해, 독립 main DB 무결성을 확인한 후 재전송했다. ACL 적용은 numeric SID에 필요한 `*` 접두사를 보완한 뒤 성공했다. 인증정보/실제 대화 원문은 공개 결과에 넣지 않았다. 이 준비 단계에서 서비스는 변경하지 않았다.

## 후보 동결·운영 소스 병합

017 최종 후보40개를 별도 ZIP에 보존했고 SHA256은 `8d5223f49aeaca4fe7dae9987107a38d6262d8ed4174386d75b2490ba4144315`다.016 ZIP/32개 entry는 그대로다.017 실제 브라우저는 **40화면·2,120개 검사 전부 통과**했으며 기존1~10의 layout/lifecycle/실시간 출력과 모델 접기·viewport·신규 배너를 함께 검증했다. 기존016의 포털/CSV 결과는 별도 과거 증거로 유지하고 새40개에 합산하지 않았다.

검토용 README를 제외한39개(runtime18개·검사21개)를 Windows 운영 소스에 구조화 병합했다. 새 모듈·frame CSS·worker·policy/context/domain·배포 helper까지 포함한다. SHA와 정적 재검사 후 이 후보40개만 구조화 정리하고 관련 없는 기존 dirty 파일은 보존한다. 원문 목록/해시는 `validation-before-merge.json`, 병합 대조는 `root-merge-verification.json`에 기록한다.

병합39개는 검토 후보와 바이트 일치를 확인했다. 기존 frame의 CRLF는 검토 LF와 같게 구조화 재작성한 뒤 대조했다. merged root의 Linux backend도 **211개 통과**, 실패/오류/skip0,40.430초, digest `2993581ff48ef292d1bb008cd0cf3dc85c31e7ce9fc1c6180a7ba69d66eea9a0`다. Git whitespace 검사에서 새 EOF 공백 줄20개를 발견해 마지막 개행 한 개만 남겼고, ZIP과의 차이가 그 terminal blank뿐임을 각 파일별 assert했다. 구문23/11 및 scoped diff-check를 다시 통과했다.

최종 배포39개 소스의 별도 ZIP SHA는 `3dcc4271e0407852010122c9b8710b6ece905ed59765afa6b623df2945a1a799`이며 `release-source-verification.json`에 정확한 최종 SHA를 기록했다. 임시 Staging40개만 구조화 삭제했고 원문 ZIP/검증 증거와 기존 unrelated dirty4개 SHA는 보존됐다.

## 운영 전환·실제 DB 사본

실행 commit `df305864b63b23b20550a8f07900f70d6a413595`를 GitHub main에 push했다. 기존 사용자 dirty 문서/거버넌스/과거 보고는 섞지 않았다. generated Windows JSON의 CRLF는 `cr-at-eol`로 검사해 원문을 보존하고 코드 EOF 공백 결함과 구분했다.

최종 새 gate를 검토한 helper 문자열로 기존 HEAD에서 먼저 실행했다. active job/guard0을 재확인하고 timer만 일시 정지했으며 cleanup은 inactive였다. 접수를 닫은 후 정확한 기존 own web867701·worker만 정상 종료했다. 공유 Strata·타 서비스는 제어하지 않았다. quiesced DB/환경·프로세스·maintenance 원문을 private에 보존한 뒤 fast-forward pull했다.

서버 source39개 SHA가 최종 배포 manifest와 일치했다. 새 HEAD의 새 Python 프로세스에서 실행한 `copy-c4f4fc66cfaf/result.json`은 **업무18개·AI17개 테이블**, 기존 대화9/메시지52/job26·guard16·lifecycle5개와 기존 모든 원본 행/열·감사/익명 권한을 통과했다. 실제 모델을 호출하거나 운영 DB를 사본으로 덮지 않았다.

2026-11-05 **16:45:58 KST** 새 own web PID896752와 worker를 기동하고 접수 재개 전 원본 행/비밀을 재대조했다. maintenance NORMAL, worker/retention timer active이며 timer enabled/active는 원래 상태와 같게 복원됐다. 환경2개와 unit3개는 원문 그대로이며 키/epoch·Nginx·스키마 변경은 없다. 정지 시점 두 DB도 독립 main 파일 integrity/FK를 통과했고 서버/현재PC private 보존 파일29개의 SHA를 대조했다.

| 운영 경계 | 확인 결과 |
|---|---|
| HTTPS 익명 | login200,assistant/admin302,capabilities/status401 |
| 배포 자산 | runtime18개·전체39개 서버 SHA 일치,HTTP JS/CSS6개 동일 |
| 서비스 | 정확한 own web·worker,maintenance NORMAL,retention 원래 상태 복원 |
| 데이터 | 기동 시 기존 모든 행/열 일치,이후 업무/감사·기존 메시지/job/영수증/guard 보존 |
| 설정 | 두 환경·unit3개 원문 일치,공유 모델/다른 서비스 제어 없음 |

## 실제 모델·운영 화면

test05(user)로 정상 로그인했다. 점검 진입 때 기존 세션이 종료되는 기존 정책이 적용되어 NORMAL 복귀 후 같은 일반 계정으로 다시 로그인했다. 본인 장비가0건인 계정이므로 실제 데이터가 있는 공개 장비에 자연스러운 `공개 장비 리스트를 표 형태로 출력해주세요.`를 요청했고, ID를 빼라고 별도 유도하지 않았다.

실제 Qwen3.8 Flash Next/off는 **11.174초·2단계**, `search_equipment` 도구로 공개 장비2건을 확인하고 `이름/모델/옵션/상태/보증 종료일/교체 예정일`6개 열의 정상 HTML 표를 반환했다. EquipmentId/Revision 열·문구는 없고 모델/옵션 안의7/21/1TB/256GB 등 업무 숫자는 유지됐다. 도구 JSON의 원래 EquipmentId와 표시 메타가 모두 남았으며 등록·수정 proposal0,guard released,예약 문자0,오류 없음이다. 이 시간은 짧은 조회1회의 접수→완료이며 일반 성능이나 장문 성능으로 확대하지 않는다.

이 검증에서 test05에 대화1개·메시지2개·job1개·이름 변경 영수증1개가 추가됐다. 제목을 `운영 검증 · 장비 표와 내부 참조 표시`로 바꾸고 dialog 종료/포커스 복귀·reload 후 제목/표/추론 복원을 확인했다. 기존 대화나 실제 장비를 삭제·확정하지 않았다.

운영 사용이 재개된 뒤의 단순 원본 row 비교에서는 정상 사용에 따른 기존 대화1개의 title/updated/lifecycle_revision과 문자 사용량2개·연결 확인 시각 갱신이 차이로 나타났다. 이를 숨기거나 과거 DB로 덮지 않고, 변경 제목을 새 rename digest·기존/결과 revision 영수증과 대조했다. 기존 업무/감사·AI 메시지/job/원래 영수증/guard가 모두 보존됨을 확인했다. 시점상 합계는 대화10·메시지62·job31이며 그 증가5개 job 중 이번 검증은1개다. 다른 정상 사용까지 이번 테스트 결과로 합산하지 않았다.

| 실제 화면 | 확인 결과 |
|---|---|
| PC1440×1000 기본 | 문서1440×1000,fit,채팅674.656px,상단 세션 제목 숨김·좌측 선택 표시·기본 접힘·정상 별/경고 숨김 |
| PC 펼침 | 문서 높이1000 유지,채팅517.859px,모델·지원 panel과 입력 겹침 없음 |
| 모바일390×844 기본 | 문서390×844,fit,채팅483.656px,세션 제목 표시·표 내부 가로 스크롤·모델/지원 기본 접힘 |
| 모바일 펼침 | 문서 높이844 유지,채팅318.859px,펼친 제어와 입력·표 겹침 없음 |
| 대화 지속성·오류 | 이름 변경·reload 복원,브라우저 console error0,viewport override 해제·검토 탭 유지 |

최초 `fullPage` 캡처1장은 DOM 기하와 달리 페인트가 비정상인 도구 캡처였다. 원문을 `production-fullpage-capture-anomaly.jpg`에 보존하고 viewport `getScreenshot`으로 다시 찍어 실제 화면/DOM 일치를 직접 확인했다. 이를 정상 화면 증거로 계산하지 않았다. 최종 기본 화면은 [PC](017_AI_Display_Status_Release/production-desktop-collapsed-final.jpg),[모바일](017_AI_Display_Status_Release/production-mobile-collapsed.jpg),펼침은 [PC](017_AI_Display_Status_Release/production-desktop-expanded.jpg),[모바일](017_AI_Display_Status_Release/production-mobile-expanded.jpg)다.

노랑/빨강의 동일색·사유/TTL·전환·오류는504개 합성 화면 검사로 확인했다. 운영의 정상 연결을 인위적으로 끊거나 타 사용자의 요청을 지연시키지 않았다. 실제 브라우저는 시스템 다크 테마이며 라이트/다크 전체는 합성 범위다. 실물 모바일 키보드/터치·모든 LAN 모델·모든 자연어 출력의 ID 강제 차단·운영 영구삭제/일괄 삭제는 추가 검증으로 주장하지 않는다.

## 사후 Validation1~8 및 완료 이력

1. 거버넌스: 명시 승인 범위의1~12만 완료하고 검토 ZIP/실패와 수정 증거·private 백업을 보존했다. 해당 후보40개만 정리하고 다른 dirty 변경은 보존했다.
2. 의도: 내부 참조/업무 값 구분과 입력칸 상태 사유를 가산했으며 기존1~10을 함께 운영에 반영했다. 새로운 권한/도구나 web_search는 추가하지 않았다.
3. 논리: Staging211개와 merged-root211개·Node18개·40화면2,120개를 통과했다. border-box 결함을 수정했고 배포 gate의 orphan guard 누락을 정상 요청 보존 방식으로 보강했다.
4. 운영: 정확한 commit·own PID/worker만 전환하고 새 HEAD 실제 DB 사본과 접수 재개 전 전체 행/열,HTTP6개 자산을 대조했다. timer와 환경/unit을 보존했다.
5. 보안: 내부 ID는 권한이 아니며 서버의 소유자/CSRF/확인/감사를 그대로 유지했다. 원문 숫자나 감사/과거 답변을 지우지 않았고 비밀/DB 원문은 private에만 보존했다.
6. 복구: 이전 commit82a9361·소스·정지 DB/환경/프로세스를 서버/현재PC에 보존했다. 코드 복귀가 필요해도 최신 대화·휴지통/삭제 원장·감사를 과거 DB로 덮지 않는다.
7. UX: 상태·viewport·접기·table·rename/reload·tooltip·console을 확인했다. 운영 장애/삭제는 강제로 만들지 않고 해당 분기는 합성과 실제 검증을 구분했다.
8. 메타: 지침과 강제 출력 차단,보간과 생성 성능,합성과 실화면,테스트와 동시 정상 사용을 구분했다. 기존016 원문/역사적 승인 범위는 보존하고 현재 운영 상태는017에 연결한다.

FEATURES20에 현재 명세를 반영하고 PROPOSALS/ROADMAP에 완료 이력을 유지했다. 완료한 AI-HEADER/CONTROLS/PORTAL/TRASH/POLISH는 미구현 목록에서 제거했다. WebMCP037·AI-TECHDEBT-001 및 관련 없는 기존 제안/보류는 유지한다. 마지막 보고·스크린샷/원장 commit은 실행 소스를 바꾸지 않는 별도 commit으로 push 후 서버에 fast-forward하며 재시작을 반복하지 않는다.

기계 근거는 [검증된 배포 소스](017_AI_Display_Status_Release/release-source-verification.json),[서버·데이터 확인](017_AI_Display_Status_Release/production-verification.json),[실제 UI 측정](017_AI_Display_Status_Release/production-ui-verification.json)이다.
