---
artifact_id: PLAN-20261105-020
work_id: RELEASE-20261105-AI-AUTO-SEARCH
owner: Codex
status: implementation
approval: requested-extension-of-authorized-ai-release
---

# 문맥에 따른 웹 검색과 Google·GitHub 제공자

사용자는 웹 검색 버튼 대신 질문 맥락에 따라 AI가 web_search를 사용하는 방식과 현재 제공자 출력, 누락된 Google/GitHub 추가를 지시했다. 현재 운영은 Yahoo 전용 DDGS9.6.1/primp0.15.0이며 Google/GitHub는 없다. 이번 변경은 기존 검색·출처·보관/감사·본인 업무 권한·019 복구를 유지하며 Staging 검증 뒤 운영까지 반영한다.

## 검색 정책

새 화면에서 검색 버튼/상태를 제거하고 신규 요청은 서버의 auto 정책으로 접수한다. 도구 지원 모델에는 web_search와 일반 공개 최신 사실·출처 요청·개발 저장소 질문 등에 검색을 사용하는 지침을 제공한다. 인사·일반 설명·본인 장비 업무에는 검색을 강제하지 않는다. 자동 검색의 판단은 모델이 하며 정규식으로 모든 질문을 분류하거나 매 요청의 검색을 의무화하지 않는다.

접수 route snapshot에 auto/required/off를 고정한다. 배포 전 접수 기록과 구 UI의 명시적 true/false는 기존 required/off 의미를 유지해 기존 작업/꺼짐 화면의 동의를 소급 변경하지 않는다. 새 UI는 해당 구식 필드를 보내지 않는다. auto는 forced tool_choice/검색 없는 응답 실패 검사를 적용하지 않으며 required만 기존 강제 검색·완료 보호를 유지한다. 도구 미지원 모델/검색 비활성 서버는 제한 이유를 지침에 제공하고 외부 검색을 주장하지 않는다.

## 제공자

- Google: 공식 Custom Search JSON API는 신규 고객에 닫혀 있고 기존 고객도2027-01-01 전환 대상이다. 기존 키/cx가 없으므로 새 유료 계약/계정·타 앱 자격증명을 만들거나 가져오지 않는다. 공식 DDGS의 Google 재활성 버전을 별도 hash-locked runtime에서 검증한다. CAPTCHA/접근 차단을 우회하지 않고 실제 결과를 확인하지 못하면 활성 성공으로 표시하지 않는다.
- GitHub: 고정 https://api.github.com REST 공개 저장소/이슈 검색을 제공한다. 익명 공개 접근만 사용하고 비공개 저장소·인증이 필요한 코드 검색·사용자 Git 자격증명 재사용은 제외한다. API의 길이/크기·시간·호출 한도와403/429를 구분한다.
- Yahoo: 기존 공개 검색을 유지한다. auto의 일반 검색은 검증된 Google 우선·Yahoo fallback을 검토하고 실제 제공자 이름/근거를 기록한다. GitHub 질문은 모델이 고정 provider와 공개 범위를 선택할 수 있다. 실패/빈 결과를 다른 엔진의 성공으로 위장하지 않는다.

의존성 후보를 실제 확인한 결과 DDGS9.16.1은 primp>=1.3.1이 필요하고 Google 엔진도 다시 비활성이다. Google 기본 GET은 JS 안내, 공개 WML은403, 표준 Chromium 검색은 보안 확인이며 실제 결과가 없었다. 따라서 이를 우회하거나 라이브러리를 강제 활성화하지 않고 기존 검증된 Yahoo runtime을 유지한다. GitHub는 같은 격리 child에서 stdlib로 추가해 새 패키지/서비스 비용이 없다. Google 고정 API adapter와 명시적 사용 불가 상태를 준비하되 사용자는 기존 API가 없다고 답했으므로 실제 활성 완료로 표시하지 않는다. Google 일반 검색의 안정적인 API 없는 경로는 미해결 조건으로 남기며 뉴스 RSS를 대신 활성화하지 않는다.

사용자의 추가 지시에 따라 설치된 Hermes의 web provider registry·DDGS subprocess·검색 인터페이스와 현재 설정의 검색 관련 이름만 읽기 참조했다. 키 없는 검색 제공자를 분리하고 모델이 도구를 선택하는 구조를 참고하되 Hermes의 설정/자격증명/실행 파일을 수정하거나 복사하지 않는다. Hermes에 검색 도구가 있다는 사실을 Google 직접 검색 성공 근거로 삼지 않는다.

## 보존·검증·운영

모델이 선택하는 것은 공개 query·provider enum·결과 수/공개 GitHub 범위뿐이다. 임의 origin/URL/셸/파일·쿠키를 받지 않는다. 기존 민감 값 검증·검색 결과 비신뢰 처리·사용자 소유자/lease/취소·확인/감사·64K 검색 예약과 실제 출처 증분 보관을 유지한다. 각 검색 결과의 제공자와 범위를 서버에서 검증한 실제 값으로 표시한다. 정상 LLM 생성에는 전역 timeout을 추가하지 않는다.

Plan/Task/Validation→Staging→Linux AST/합성/실제 제공자 검색·화면→원문/SHA→root 병합/재검증→현재 DB/설정/source private 백업·idle own web/worker 전환·실제 DB 사본 보존→운영 검증을 따른다. 실제 일반 계정에서 자동 검색 질문과 검색 불필요 질문을 구분해 확인하고, 기존 대화를 자동 재실행하지 않는다. 다른 dirty/외부 서비스는 보존한다. rollback은 기존 코드/runtime으로 복원하고 최신 대화/감사 DB는 되돌리지 않는다.
