---
artifact_id: REPORT-20261105-020
work_id: RELEASE-20261105-AI-AUTO-SEARCH
owner: Codex
status: in-progress
approval: requested-extension-of-authorized-ai-release
---

# 문맥 기반 검색·제공자 확장 검증

사전 확인: 현재 Yahoo 단독, DDGS9.6.1/primp0.15.0. Google/GitHub 설정 키는 없고 DDGS9.6.1 Google 구현은 비활성이다. GitHub 익명 공개 저장소 검색은 실제 HTTP200/3건(Flask 공식 저장소 포함)/0.492초로 확인했다. Google 기본 HTML GET은200이지만 JS 안내이고 실제 Flask 출처가 없어 성공으로 계산하지 않았다. Google 뉴스 RSS는 일반 웹 검색과 다르므로 Google 전체 검색의 대체 성공으로 사용하지 않는다.

공식 자료: [Google API 현황](https://developers.google.com/custom-search/v1/overview)은 신규 고객 제한과2027-01-01 전환을 명시한다. [GitHub 검색 API](https://docs.github.com/en/rest/search/search?apiVersion=2022-11-28)는 익명 공개 검색10회/분과 코드 검색 인증 필요를 명시한다. [DDGS 공식 릴리스](https://github.com/deedy5/ddgs/releases)는9.16.0의 Google 재활성과9.15.0의 DHT 제거를 기록한다. PyPI 공식 metadata에서 최신9.16.1을 읽었다. 외부 연결·제공자 한계와 실제 결과를 구분한다.

## 구현 전 Validation1~8

1. 거버넌스: recorder ensure 성공·legacy/runtime-session-mismatch,1.8.1 validate 오류/경고0,context31개/requiredInputs0과 기존에 읽은 동일 노드/pack을 적용한다. Plan/Task020을 먼저 기록하고 source는 구조화 편집한다. Windows에서 앱을 import/실행하지 않는다.
2. 의도: 버튼 제거·모델 문맥 판단과 현재 제공자 공개·Google/GitHub 추가가 범위다. 기존 일반 사용자 업무·019 복구·소유자 대화·확인/감사·운영 반영 승인을 유지한다.
3. 논리: auto와 기존 required/off를 snapshot에서 구분하고 일반 응답에 강제 검색/오답 처리를 적용하지 않는다. 실제 제공자 이름·범위·fallback·빈 결과·실패와 저장/전환을 검사한다.
4. 운영: 기존 Flask/검색 환경을 보존한 새 고정 runtime부터 검증한다. 장비 앱의 own web/worker만 idle 전환하며 다른 Strata/서비스 큐는 제어하지 않는다. 정상 생성의 전역 timeout은 없다.
5. 보안: 공개 검색어·고정 provider/scope와 크기/횟수만 허용한다. 비공개 값/자격증명·임의 origin/SSRF·결과 프롬프트 주입·모델 권한 확대를 차단하며 Git 토큰을 가져오지 않는다.
6. 복구: 새 후보/원문/SHA·기존 dirty와 운영 코드/설정/DB private 사본을 보존한다. 이전 runtime을 삭제/덮지 않으며 최신 대화/감사 DB를 과거로 복원하지 않는다.
7. UX: 검색 버튼의 공간을 없애고 실제 검색 시 출처 목록과 제공자를 표시한다. 숨은 opt-in state와 stale 안내를 제거하며 새 UI와 기존 캐시/접수 기록을 함께 검사한다.
8. 메타: 라이브러리 지원·실제 제공자 응답·실제 모델의 도구 선택을 각각 검증한다. GitHub 공개 저장소/이슈를 비공개·전체 코드 검색으로 확대하지 않고 Google 뉴스나 타 엔진 결과를 Google 전체 검색으로 표기하지 않는다.

## Google와 Hermes 참조 결과

사용자는 Google API가 별도로 없으며 일반 검색 수단과 Hermes 구현을 참고하라고 추가 지시했다. Google WML의 일반 요청은403이었고, 설치된 표준 Chromium을 기본 사용자 에이전트/새 격리 프로필에서 실행한 일반 검색도3.256초 후 보안 확인을 반환했다(h3 결과0/Flask 공식 출처0). 보안 확인을 해결하거나 UA·프록시·다른 IP로 우회하지 않았다. DDGS9.16.1의 실제 wheel metadata는 primp>=1.3.1을 요구하며 wheel 내부 Google 클래스도 disabled=True다. 업데이트만으로 해결된 것으로 간주하지 않았다.

Hermes의 설치 코드 `agent/web_search_registry.py`, `agent/web_search_provider.py`, `plugins/web/ddgs/provider.py`와 `_search_worker.py`를 외부 reference scope로 읽었다. registry의 capability/availability 선택과 별도 subprocess 경계, API 키 없는 DDGS/Brave Free 제공자 구조를 참고했다. 설치된 provider 목록은 brave_free/ddgs/exa/firecrawl/keenable/openai_native/parallel/perplexity/searxng/tavily/xai다. 현재 기본 config의 web 절과 검색 관련 환경변수 이름은 없었다. 개별 profile의 실제 활성 제공자까지 실행해서 확인한 결과는 아니며 Hermes에 Google 직접 검색이 활성이라고 주장하지 않는다. 설정/키/인증/다른 앱 코드는 수정·복사하지 않았다.

후보는 기존 hash-locked runtime을 유지하며 stdlib GitHub 공개 adapter를 추가했다. Google은 고정 API adapter의 합성 검사/연결 상태 표시만 준비하며 실제 활성은 미완료다. 선택 제공자/공개 범위를 whitelist하고 redirect·임의 endpoint·비공개 Git 접근·앱/Git/Hermes 키 재사용을 제공하지 않는다. [실제 제공자 검사](020_AI_Automatic_Search_Providers/provider-probe.json)는 Yahoo 일반 검색1.962초/공식 삼성 링크, GitHub 저장소0.762초/공식 Flask 및 공개 이슈0.720초를 확인했고 Google은 available=false로 명확히 표시했다.

## 후보·Root 검증

기존 버튼/숨은 opt-in state를 제거하고, 구 template가 캐시된 경우에도 새 JS가 옛 제어를 제거한다. 새 POST는 legacy web_search 필드를 생략하고 서버가 auto snapshot을 접수한다. 구 명시적 true/false와 기존 route의 required/off는 유지한다. 모델에 공개 검색 도구와 제공자 상태·문맥/민감정보/명시적 검색 금지 지침을 전달하고 required만 forced tool_choice/실제 검색 없는 완료 차단을 적용한다.

첫 전체244개 검사에서2개 소규모 보관량 시험이 실제 서버의 설치된 검색 runtime 상태를 상속해64K 예약까지 포함하는 것을 발견했다. 운영 코드의 보관 기준을 낮추지 않고 합성 기본 시험의 USER_AI_WEB_SEARCH를 false로 고정했다. 검색 시험은 자체 FakeSearch를 주입하고 auto 접수의64K 추가 예약/완료 해제를 별도로 검증한다. 이3개 관련 검사를 재통과했고 Staging244개/45.260초, root244개/71.819초 모두 오류·실패·skip0이다. [검사 이력](020_AI_Automatic_Search_Providers/backend-verification.json).

실제 Linux Chromium의 검색 UI8화면160개·019 회복12화면216개·기존 대화 UI4화면642개, 합계24화면1,018개 검사를 Staging/root에서 각각 통과했다. 최신 template와 옛 버튼이 남은 캐시 template를 함께 검사했다. 동적 Yahoo/GitHub 출처·공개 이슈/부분 결과·안전 링크/비신뢰 텍스트·모델 전환/재열기·초안/오류 복구·정적 높이와 실제 프레임을 확인했다. 첫 모바일 화면을 직접 검토했고 웹 검색 버튼 공간이 없어지고 실제 제공자 출처를 구분한다. 실제 운영 계정/모델을 쓴 검사는 뒤에서 별도 기록한다.

최종 후보14개는 [원문 ZIP](020_AI_Automatic_Search_Providers/reviewed-staging-source.zip)/[SHA manifest](020_AI_Automatic_Search_Providers/reviewed-staging-source.json)로 보존했고 root14개 SHA가 전부 같았다. Python AST/JS 구문을 통과했다. Google API 없는 일반 검색은 미구현 원장에 남기며 후보의 일반 웹/GitHub 완료와 구분한다. 이어서 기존9개 dirty를 보존한 scoped commit과 private 백업·idle own 전환/실제 DB 사본 검증을 수행한다.
