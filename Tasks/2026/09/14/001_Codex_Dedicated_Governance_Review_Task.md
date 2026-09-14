# GPT-6 Astra 전용 거버넌스 및 모델 확장성 검토 Task

- work_id: GOV-CODEX-DEDICATED-20260914
- 작업자: Codex
- 작업 모드: 검토 완료 후 승인된 구현·운영 정책 반영
- 현재 요청 범위: 최초 전용 도입 대상은 Codex/GPT-6 Astra 1개로 한정. Claude Fable 5.1과 가칭 Gemini 4 Pro는 향후 검토 예시로 두고 등록하지 않는다. 기존 설계의 추가 결함을 점검하여 정식 계획서에 반영한다.
- 현행 계획: [모델별 거버넌스 계획](../../../../Plans/2026/09/14/001_Model_Specific_Governance_Plan.md)
- 해석 정정: 공통 강제 체계에 대한 우수 모델 예외가 아니다. 기존 체계 자체가 모델의 한계를 보완하는 강제 도구이며, 전용 경로는 그 절차를 상속하지 않는다.
- 보고서: [검토 보고서](../../../../Reports/2026/09/14/001_Codex_Dedicated_Governance_Review_Report.md)
- 현재 승인: 사용자가 보고서·계획서 확인 후 운영 반영까지 연속 진행을 명시 승인했다. 아래 실행 절이 최신 상태이며 이전의 미구현 표기는 당시 검토 이력이다. 서비스·DB·모델 설정·Git 원격 변경은 이번 정책 반영에 포함하지 않는다.

## 승인 후 구현 및 운영 반영

- [x] recorder ensure, 기존 validate, edit-rule/implement/merge-production context 및 전체 pack 확인
- [x] 현재 작업 JSONL의 진행 중 turn_context에서 cwd와 gpt-6-astra 모델 ID 확인(대화 본문 출력 없음)
- [x] Staging 정책 후보: 독립 노드·정확한 등록부·AGENTS 분기·선택기·회귀 시험
- [x] Rule 의미·추적성·해시 동기화 및 1~8단계 순차 검증
- [x] 기존 모델 회귀·오류·합성 확장·턴 전환·불완전 패키지 시험
- [x] 승인된 정책 패키지 운영 반영 및 실제 현재 턴의 선택 확인
- [x] 이번 작업의 Staging 파일 정리, 최종 문서 갱신과 복구 패치 보존

## 최초 검토 이력

- [x] 대화 기록 preflight, manifest 검증, catalog 및 review-rule/review context 확인
- [x] Rule 전체, 추적성 map, 적용 context pack, Codex capability 확인
- [x] OpenAI Docs 스킬 및 공식 모델 지침 참조
- [x] 사용자의 두 차례 정정에 따라 독립 전용 노드 설계로 범위 확정
- [x] 사용자 추가 지정에 따라 GPT-6 Astra만 전용 경로, 다른 Codex 모델은 기존 경로로 적용 대상 확정
- [x] 현행 검토 절차의 1~8단계를 순서대로 수행하여 보고서에 기록
- [x] AGENTS 분기·노드 독립성·기존 모델 비영향 및 활성화 전 검증 조건 정리
- [x] 산출물과 활성 정책 미변경 확인 후 검토 결과 제출 준비 완료

최종 검사: governance validate 통과(43개 노드, 오류·경고 0), 활성 정책 diff 없음, 문서 간 상대 링크 확인. 모델별 분기와 전용 노드는 아직 구현하지 않았다.

현재 규칙으로 이번 검토를 수행한다는 사실과 향후 전용 노드에서 그 강제 절차를 적용하지 않는 설계를 구분한다. 전용 노드는 이번 작업에서 활성화하지 않는다.

## 이전 검토 이력 — Fable 5.1 포함안, 현재는 도입 보류

- [x] 사용자가 동일한 설계 이유로 Claude Code의 Fable 5.1도 대상에 포함한 사실 확인
- [x] 기록기 preflight, validate, 확장된 reference-path의 context 및 전체 pack 확인
- [x] CLAUDE.md와 claude capability를 조회하여 기존 진입점 및 기록기 지원 상태 확인
- [x] 후속 요구 확인: 가칭 Gemini 4 Pro를 등록하는 것이 아니라, 향후 적합성이 판단된 모델을 추가할 수 있는 확장성을 설계
- [x] 적용표·분기·전용 노드 초안·합격 기준 갱신, 현행 1~8단계 순차 재검토 기록
- [x] 문서 일관성 및 활성 정책 미변경 확인 후 결과 제출 준비 완료

모델 표시명 Fable 5.1은 사용자 지정 그대로 사용한다. 실제 런타임 식별자와 Claude 실행 도구의 지원 상태는 별개로 다루며, 미확인 값을 만들어 쓰지 않는다.

가칭 Gemini 4 Pro는 사용자 설명의 미래 확장 예시이며 현재 대상·예약 대상·자동 활성화 대상으로 등록하지 않는다. 모델의 출시나 버전 번호만으로 대상에 자동 편입하지 않는다.

후속 최종 검사: 동일 Rule 해시로 validate 통과(43개 노드, 오류·경고 0). Rule·AGENTS·CLAUDE·거버넌스 diff 없음. 두 문서의 대상 명칭·확장성 문구·상대 링크·문자 인코딩 확인.

## 현재 개정 작업 — 단일 도입 대상 및 계획 보완

- [x] 사용자 설명의 구독 접근 제약을 도입 조건으로 반영하고 문서 표시명을 Claude Fable 5.1로 통일
- [x] 기록기 ensure, validate, plan/review/review-rule context 및 적용 pack 확인
- [x] 기존 검토 보고서 전체와 실제 로더 main/load/validate 흐름 점검
- [x] 정식 Plan 부재, 2개 모델 도입 문구 잔존, 전역 로딩 선행, 모델 변경·정합성 조건 미구체화 확인
- [x] GPT-6 Astra 단독 계획서 작성 및 후속 모델 비등록·확장성 기준 반영
- [x] 1~8단계 재검토와 최신 계획/검토 이력 분리 기록
- [x] 문서 링크·현재 대상·활성 정책 미변경 검증 후 제출 준비 완료

이번 개정 역시 문서 작업이며 활성 정책, 실행 코드, 모델 구독·설정, 서버 및 Git 원격은 변경하지 않는다. 위 과거 완료 기록은 그 당시의 검토 범위를 뜻하며 현재 도입 대상을 추가하지 않는다.

개정 최종 검사: governance validate 통과(43개 노드, 오류·경고 0). Rule·AGENTS·CLAUDE·GEMINI·거버넌스 diff 없음. Plan/Report/Task 상대 링크·인코딩·문서 구조 검사 통과. Plan의 단일 도입 대상과 Claude Fable 5.1 표기, 후속 모델 전용 경로 미포함 확인.
