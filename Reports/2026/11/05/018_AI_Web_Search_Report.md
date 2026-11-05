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
