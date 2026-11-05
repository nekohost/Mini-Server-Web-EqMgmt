---
artifact_id: REPORT-20261105-018
work_id: RELEASE-20261105-AI-WEB-SEARCH
owner: Codex
status: in-progress
approval: explicit-staging-and-production
---

# AI 웹 검색 검증·운영 기록

recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0과 context31개를 확인했다. 분할 출력에서 누락된 operations.staging/records2개는 별도로 전부 읽었다. 현재 local/server HEAD는 `cee4e5e060e4d323d889e9d3e9b0749ed6d463af`다. 기존9개 tracked dirty와 다른 untracked 자료는 보존한다. 사용자 명시 승인은 구현·검증·필요 수정·운영 반영까지다.

## 구현 전 Validation1~8

1. 거버넌스: Plan/Task018을 먼저 작성하고 Staging부터 진행한다. Windows에서 앱을 import/실행하지 않으며 source 편집은 구조화 도구로 수행한다. 기존 기록/다른 dirty는 보존한다.
2. 의도: 일반 공개 웹 검색을 장비 AI의 도구로 추가하고 출처가 있는 답변을 제공한다. 기존 일반 사용자 업무 범위와 실제 변경 확인을 유지하며 서버 반영까지 수행한다.
3. 논리: 현재 worker finish HTTP read timeout15초와 검색 외부 I/O의 상호작용, DB transaction 점유,재전송·취소·컨텍스트 예산을 점검했다. 검색만 bounded 별도 실행하고 전체 응답을 검증한 뒤 저장한다.
4. 운영 영향: 기본 검색 서비스/키가 없어 실제 사용할 검색 경로 선정을 먼저 검증한다. 외부 의존성은 분리된 환경에 고정하고 base Flask 환경·모델/큐·기존 DB 스키마를 보존하는 방식을 우선한다.
5. 보안: 외부 검색의 query 유출·결과 프롬프트 주입·위험 링크/SSRF·off job 위조·유효하지 않은 worker 결과·크기/호출 남용을 다룬다. 임의 fetch/명령/인증정보 전달은 제공하지 않는다.
6. 복구: 코드·설정·DB·소유 프로세스·검색 runtime 변경 전 백업과 복귀 대상을 보존한다. 정상 모델 요청/타 서비스는 중지하지 않는다. 최신 메시지·삭제/감사 원장은 되감지 않는다.
7. UX: 기존 공간 절약을 유지하는 opt-in 제어·명확한 검색 실패와 빈 결과·안전한 출처 표시를 검증한다. 모델 미지원/서버 비활성·접수 후 옵션 변경·모델 전환·reload/휴지통을 확인한다.
8. 메타: 단순200·잘못된 결과·캡차를 검색 성공으로 기록하지 않는다. 검색 summary와 원문 열람을 구분하고 검색 지침을 모든 모델의 강제 안전 보장으로 주장하지 않는다. 신규 유료 계약이나 다른 서비스의 키 복사는 승인 범위에 포함하지 않는다.

## 사전 검색 진단

프로젝트 검색 관련 환경 이름0개,검색 unit0개,Docker 미설치다. DDG HTML의 공개 Flask 문서 검색은202 challenge/결과0, Bing RSS는200이지만 무관한 동일 도메인2건을 반환했다. 별도 검색 서비스 유무를 optional text 질문으로 요청하고, 답변과 독립적인 경로·보안/기존 계약 검토를 계속한다.

공식 참고: [SearXNG Search API](https://docs.searxng.org/dev/search_api.html),[설치](https://docs.searxng.org/admin/installation-searxng.html),[DDGS 공식 저장소](https://github.com/deedy5/ddgs). Microsoft의 옛 Bing Search API는 [공식 폐지 기록](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)에 따라 신규 경로로 채택하지 않는다.

## 검색 경로 선정

Linux private 임시 package target에서 DDGS9.6.1을 시험했다. unconstrained primp2.0.1은 `chrome_131` 인수 호환 오류가 있어 primp0.15.0으로 고정한 뒤 재검증했다. DDGS 공식 v9.6.1 소스는 정해진 engine만 남기는 경로와 Yahoo의 고정 HTTPS 검색 및 결과 URL 추출을 확인했다. Brave/Mojeek는 결과 없음으로 남기고 사용하지 않는다. Yahoo는 S25 한국어 질의5건(Samsung 공식 포함),Flask 영어5건(Pallets 공식 포함),서울시청 한국어5건(서울시 공식 포함)이 반환됐다. 외부 HTML 검색 결과에는 비공식/불필요 사이트도 섞이므로 결과만으로 정답 보장을 하지 않는다.

현재 선택은 Yahoo만 허용하는 DDGS9.6.1/primp0.15.0이며16개 binary wheel의 버전·SHA를 별도 lock에 보존한다. 라이브러리의 auto/다른 엔진·proxy 환경·URL 추출/방문 도구를 사용하지 않는다. 검색 전용 격리 runtime과8초 프로세스 deadline으로 기존 Flask 환경·15초 finish 응답·정상 LLM 생성 시간 계약을 분리한다.

## Staging 구현·결함 수정

검색 도구는 요청별 명시적 opt-in·현재 actor/lease/menu·route snapshot으로 제한한다. 비공개 장비 상세가 이 요청에 이미 들어온 경우 추가 외부 검색을 막고, 계정/연락처/인증·알려진 본인 시리얼/메모·private IPv4를 검색어에서 거부한다. 이 방어는 모든 비밀 문장의 완전한 분류기로 주장하지 않는다. 검색 전에 업무 connection을 닫으며 child에는 app 환경·쿠키·프록시·인증을 넘기지 않는다. 도구 모음 전체 검증 및 검색 우선 처리로 검색 실패 후 업무 확인 카드가 준비되지 않도록 했다.

출처는 실제 tool-call ID/name과 결과 envelope를 대조해 서버에서 투영한다. HTTPS 도메인만 허용하고 IP/인증/비표준 port/로컬/위험 scheme/중첩 인코딩 제어문자를 거부한다. 결과를 서버에서 방문하지 않으며 브라우저는 textContent·새 탭/noopener/noreferrer/no-referrer로 표시한다. 검색 요약과 원문 전체 열람을 구분한다. source version ACK로250ms마다 동일 자료를 재전송하지 않으며 모델 전환 인계에는 bounded 제목/URL만 비신뢰 자료로 유지한다.

최초 신규 검사에서 **취소 중 외부 검색이 끝나면 context에 늦은 출처가 남는 결함**을 찾았다. Store.finish의 같은 writer transaction에서 cancel/deleted를 확인해 새 context를 받지 않도록 수정했다. 기본32M와 확장32M는 유지하고 검색 허용 때32K를 추가 예약한다. 실제 검색 JSON만 증분 차감하며 재시작 시 없는 원장만 재구성하고 영구삭제/GC 때 정확히 환급한다. 기존 account 원장을 리셋하지 않는다.

초기 fixture의 보관량 기대값은 기존 claim의 인계 문자·임시 답변 `Answer`도 합산해야 하므로 실제 계약대로 보정했다. 첫 browser 실행은 기존 harness의 portal→viewport 모듈 import 순서 문제여서 의존 모듈을 먼저 적재하도록 수정했다. 합성 driver의 조기 완료/선택 저장 중 재변경 race도 fixture에서 수정했다. 이 초기 실패 화면/결과는 별도 폴더에 보존하고 최종 성공 검사에 합산하지 않았다.

## Staging 검증 결과

| 검사 | 결과 |
|---|---|
| 기존+신규 Linux backend |230개,실패0/오류0/skip0,45.185초. Windows/운영 app·DB 미사용|
| 검색 통합 세부 |19개 통과: opt-in/위조/CSRF/타 계정·실패·횟수·연결 해제·취소·모델 인계·예약·재시작 원장·삭제 환급|
| 정적/Node |Python AST11,JS 구문4,실제 client URL 경계14개 통과|
| 검색 UI |320/390/820/1440px×라이트/다크8화면·160개 검사 통과|
| 기존 UI 회귀 |390/1440px×라이트/다크4화면·642개 검사 통과|
| 실제 격리 검색 client |Flask5건/1.349초,S25한국어5건/1.688초,서울시청한국어4건/1.415초. 모두 공식 도메인 포함|

검색 화면의 기본 off/외부 전송 설명·확정 요청의 true·출처 접힘·poll ACK/포커스 유지·실행 불가 링크 제거·악성 문자열 비실행·모델 변경/이력 재열기·320px부터의 컨트롤/채팅 높이·문서 overflow를 확인했다. 직접 확인한 모바일/PC 다크 이미지에서 검색/보내기 버튼 높이와 기존 접기 배치를 유지했다. 모의 `<img>/<script>`는 의도적으로 문자로 남아 있으며 실제 공격 실행은 없다. [검색 UI](018_AI_Web_Search/staging-web-search-final/results.json),[기존 UI](018_AI_Web_Search/staging-ui-regression/results.json),[실제 검색](018_AI_Web_Search/actual-search-client.json),[정적 검사](018_AI_Web_Search/static-checks.json).

서버의 검색 runtime은 `instance/web-search/runtime-ddgs-9.6.1-primp-0.15.0`에 격리 설치하고 ready marker/lock SHA를 대조했다. 기존 Flask venv·환경·공개 listener·모델 서비스는 변경하지 않았다. 이 단계에서는 실행 중인 앱은 여전히 기존017 코드다. 운영 전환·일반 계정 실제 대화 검증은 다음 단계로 기록한다.

## 원문 보존·병합 및 배포 준비

수정 전 보호한 실행 파일114개는 병합 직전까지 전부 원본 SHA와 일치했다. 검토 후보18개를 ZIP과 manifest에 원래 경로·바이트 SHA로 보존한 뒤 root에 병합했고18개 모두 바이트 동일함을 확인했다. merged-root의 Linux backend도230개,실패0/오류0/skip0,44.185초로 통과했다. 이 후보18개만 구조화 편집으로 정리했다. 첫 일괄 patch 전송은 출력 길이 제한으로 적용 전에 중단됐으므로 파일별로 분할 적용했으며 결과의 바이트 동일성을 다시 대조했다.

운영 사전 점검은 이전 HEAD `cee4e5e`·tracked clean·own web PID896752와 worker/timer를 확인했다. 기존 owner1 요청1건이8:33UTC `ValueError/STREAM_INCOMPLETE/recovery_required`로 남아 있었다. 응답/오류를 성공으로 바꾸지 않았다. 실제 고정 Strata `/slots`에서 모든 슬롯 `is_processing=false`를 두 번 확인한 뒤, 기존 trusted loopback `acknowledge-finished`로 이 자체 요청만 `failed/STREAM_INCOMPLETE`와 released 점유로 정리했다. 전역 cancel/다른 서비스 제어는 사용하지 않았다. DB·환경·unit·기존 소스는 정리 전에 private 백업했다. 최초 비인증 `/slots` 조회401은 인증된 동일 읽기 경로로 바로잡았다.

private 서버 백업 경로는 `/home/nekohost/services/Mini-Server-Web-EqMgmt/instance/releases/20261105-ai-ux-web-search-20261105T084615Z-e2866a`다. 본문에는 key/DB 원문을 넣지 않는다. 정상 종료 확인 후 active/orphan 점유는0이고 retention은 enabled/active,cleanup은 inactive다. [준비 기록](018_AI_Web_Search/release-preparation.json),[병합 SHA](018_AI_Web_Search/root-merge-verification.json),[소스 원문](018_AI_Web_Search/source-archive-manifest.json).

## 운영 전환·출처 번호 보완

실행 commit `97fe899bba8fbd8f09cf209779a93341647abb87`를 push한 뒤 retention timer를 잠시 정지하고 cleanup의 자연 종료/active0을 재확인했다. 이전 own web/worker만 정상 종료하고 같은 commit을 pull했다. 새 프로세스의 실제 DB 사본 검사에서 업무18개·AI17개 테이블과 기존 감사/삭제 원장을 보존했다. v4 유지·비밀 유지·기존 행 대조 후8:48:57UTC NORMAL로 재개했고 own web PID907570,worker/timer active를 확인했다.

일반 계정 test05에서 기본 off인 버튼을 켜 공개 Flask 문서 질문을 보냈다. 실제 Qwen 모델은 `web_search`를 호출했고 Yahoo5건·공식 Pallets 출처와 `[1]` 인용 답변을 완료했다. 운영 화면의 실제 목록 스타일에서 **출처 번호가 공통 list reset에 가려지는 문제**가 보였다. 첫 실제 화면을 보존하고 CSS의 decimal/outside를 명시했다. 같은 Staging에 CSS/driver/harness3개만 재구성해8화면168개 검사(번호 스타일 포함)를 통과했다. 후속 ZIP/SHA와 root 동일성을 확인하고 이3개 후보를 다시 정리했다. 실행 Python/worker 변경이 없으므로 이 후속은 검증한 정적 자산만 fast-forward하고 실제 화면 reload로 검사하며 정상 작업자를 반복 재시작하지 않는다.

후속 commit `602972a4198cb1d93b9bdbd777e1d892995a0e2c`를 같은 서버에 fast-forward했다. source18개·공개 CSS HTTP SHA가 맞고 web PID907570/worker PID907580은 그대로다. 실제 AX에 출처1~5의 list marker와 브라우저 computed decimal을 확인했다. 추가 실행 변경은 없으며 마지막 완료 문서 commit도 동일 방식으로 동기화한다.

## 실제 검색·화면·보존 결과

실제 요청 `Flask의 공식 문서를 웹 검색으로 찾아 주요 용도를 두 문장으로 설명하고 출처를 알려주세요.`는 test05/user·Qwen3.8 Flash Next/off로 **13.232초·2단계·완료**됐다. 실제 도구는 `web_search`1회,질의 `Flask official documentation`,검색 결과5건과 첫 공식 출처 `https://flask.palletsprojects.com/`를 반환했다. 생성 답변에는 `[1]`과 공식 문서/출처 목록 안내가 있고 검색 요약에 근거한 주요 용도2문장을 제공했다. 별도 장비 변경 proposal0,오류 없음,guard released,예약 문자0이다. 출처 JSON2,117자가 정확히 사용량에 포함됐으며 본인 전체 보관 원장과 실제 메시지/인계/초안/검색량 합계가 일치한다. 이13.232초는 짧은 질문1회의 접수→완료이며 일반 모델 성능이나 검색 전용 지연으로 확대하지 않는다.

실제 추가 데이터는 검증 대화1개·메시지2개·job1개·이름 변경 영수증1개다. 제목은 `운영 검증 · 웹 검색과 출처`로 정리했다. reload 후 답변·출처5건·제목이 복원되고 웹 검색은 off로 재시작했다. 모델 변경/취소/검색 오류/휴지통/위험 링크는 합성19개와 UI에서 검증했으며 운영 오류/삭제를 인위적으로 만들지 않았다.

| 실제 운영 화면 | 결과 |
|---|---|
| PC1440×1000 기본/출처 펼침 | 문서1440×1000,fit,채팅674.656px. 검색/보내기36px,실제 번호·HTTPS 출처 확인 |
| 모바일390×844 기본/출처 펼침 | 문서390×844,fit,채팅458.266px. 검색/보내기44px,제목·native 출처·테마 스크롤 유지 |
| 지속성/안전 표시 | 검색 기본 off·5건 복원·decimal 번호·no-referrer/새 탭 링크·콘솔 error0 |

최종 [PC 답변](018_AI_Web_Search/production-desktop-collapsed-final.jpg),[PC 출처](018_AI_Web_Search/production-desktop-expanded-final.jpg),[모바일 답변](018_AI_Web_Search/production-mobile-collapsed.jpg),[모바일 검색어/출처](018_AI_Web_Search/production-mobile-sources-final.jpg)를 직접 검토했다. 번호 수정 전 원본 이미지는 별도 이름으로 보존했다. viewport override를 해제하고 일반 계정의 검토 탭을 남겼다. 실제 화면은 시스템 다크,라이트/다크/320~1440px 전수는 합성 범위이며 실물 모바일 터치/키보드/모든 모델의 도구 사용은 검증 완료로 주장하지 않는다.

서버와 현재 PC의 private 경로에 정지 시점의 업무/AI DB·환경·unit·process·기존 원본 source/사본 결과19개를 보존하고 SHA를 일치시켰다. 첫 전체 전송은 중복 DB/소스 압축 때문에45초 전송 제한에 걸렸고, 이후 정지 DB/설정·결과만 전송했다. Windows에서 재생성한 Git tar는 CRLF 영향으로 원본 tar와 달라 byte-identical 백업으로 사용하지 않았으며 Linux 원본 tar를 별도로 전송해 SHA를 맞췄다. 원문을 덮거나 지우지 않았다. [private 사본 확인](018_AI_Web_Search/private-backup-verification.json).

운영은 NORMAL,worker/timer active,active/orphan 요청0,anon login200/assistant302/capabilities401/admin302다. `.env`/worker.env 바이트 SHA는 이전과 같다. 실제 사본의 업무18개·AI17개/감사/삭제 보존과 접수 재개 전 기존 행 대조는 release helper에서 통과했다. 기존 실패 요청은 `failed/STREAM_INCOMPLETE`로 보존하며 정상 성공으로 바꾸지 않았다. [실제 요청·서비스/사본](018_AI_Web_Search/production-verification.json),[소스/HTTP](018_AI_Web_Search/production-source-verification.json),[실제 UI 기하](018_AI_Web_Search/production-ui-verification.json).

## 사후 Validation1~8

1. 거버넌스: 사용자 명시 승인 안에서 계획→Staging→검증→원문/SHA→root→운영을 수행했다. 018의 후보18개와 후속3개만 정리했고 기존9개 dirty는 보존했다.
2. 의도: 장비관리 AI에 공개 웹 검색과 출처를 가산하고 운영 일반 사용자 요청까지 확인했다. 기존 장비 업무/확인·관리자/사용자 범위는 유지했다.
3. 논리: backend230개를 Staging/merged root에서 각각 통과했고,최종 검색 UI8화면168개와 기존 UI4화면642개를 확인했다. 취소 후 늦은 출처·보관 원장·번호 reset 문제를 수정했다.
4. 운영: isolated hash-locked runtime·정확한 commit·own idle 전환·실제 DB 사본을 확인했고 static 후속에는 재시작을 반복하지 않았다. 정상 LLM 생성의 전역 시간 제한은 추가하지 않았다.
5. 보안: opt-in snapshot·actor/CSRF/lease·공개 키워드/알려진 비공개 값·위험 URL·신뢰 구분/확인을 검증했다. 임의 fetch/셸·키 전달이 없으며 자연어 지침을 완전한 방어로 주장하지 않는다.
6. 복구: private 원본 DB/설정/소스를 양쪽에 보존했다. 최신 대화/삭제·감사 원장을 과거 DB로 덮지 않으며 실패 기록/배포 중 오류도 보존했다.
7. UX: 기본 off·간단한 버튼·이유 있는 비활성/실패·source 접기/번호/새 탭·reload·PC/모바일을 확인하고 실제 발견한 번호 표시를 보완했다.
8. 메타: 실제 검색/합성·검색 요약/원문 열람·짧은 요청 시간/일반 성능을 구분했다. 외부 Yahoo HTML 검색은 차단/변경/품질 편차가 있고 다른 API/유료 SLA/웹페이지 탐색을 제공한 것으로 확대하지 않는다.

현재 명세는 FEATURES21·운영 안내·원장018에 기록한다. FEATURES19/ROADMAP017의 당시 web_search 보류 기록은 역사로 보존하고 이번018에서 완료로 갱신한다. 기존 WebMCP037·AI-TECHDEBT-001 등 별도 보류는 이번 작업으로 완료 처리하지 않는다.

## 최종 JSON 보관 경계 보강

최종 정적 검토에서 제목/요약/URL의 JSON escape가 문자 저장량을 늘릴 수 있음을 확인했다. 실제 SearchService의 최대5건을2회 모의한 경계 검사를 추가했고,32K 예약에서 **48,764자 >32,000자 실패**를 재현했다. 결과를 줄이거나 정답 기준을 완화하지 않고 검색 예약만64K로 늘렸다. 기본32M/확장32M와 실제2,117자 사용량 계산은 그대로이며 사용하지 않은 예약은 완료 시 해제된다. 이 추가 검사를 포함해 Staging231개·오류0/실패0/skip0,43.974초를 확인했다. 후보4개의 ZIP/SHA·root 동일성을 보존하고 해당 후보만 정리했다. 이 뒤 merged-root 재검증·같은 idle 백업/배포·실제 확인을 수행한다. 앞선32K 설명과230개 결과는 당시 이력이고 최종 계약은64K/231개다.

merged-root도231개/44.167초로 통과했다. 실행 commit73f516e를 private 후속 백업·실제 업무18/AI17 테이블 보존·idle own 전환으로 적용했다. 후속 private 백업17개는 현재PC 사본과 SHA를 일치시켰다. 새 web PID911927과worker/timer 정상으로 재개했다. 이어진 한국어 S25 질의에서는 **모델이 검색을 호출하지 않고 검색 결과1번이라고 답하는 오류**를 발견했다. 이4.012초·1단계·도구0·출처0 사례는 정상 검색 성공으로 계산하지 않는다. 실제 저장된 답변/오류 사례를 그대로 보존하고,켜진 요청은 첫 단계에서 named web_search를 요구하며,이를 무시한 응답은 WEB_SEARCH_REQUIRED로 실패하도록 보강했다. 기존 다른업무 도구의 권한/확인은 유지한다.

또한 최대 검색 JSON을 worker finish로 검증하면서 기존 일반 업무 도구의16K 결과 상한이 검색 결과까지 대체할 수 있음을 확인했다. 검색 envelope에는32K의 별도 검증 상한을 적용하고 초과는 명시적 실패로 남긴다. 정상 최대 자료를 줄여 맞추지 않는다. 실제 worker payload의 named tool 선택·off/후속 단계의 기존 동작·검색 없는 가짜 인용 실패·큰 출처 보존을 추가해 신규 검색 검사23개가 통과했다. 최종 전체 검증/운영 결과는 아래 후속 기록을 따른다.
