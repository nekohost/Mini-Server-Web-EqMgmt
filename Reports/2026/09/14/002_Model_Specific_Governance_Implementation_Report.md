# 모델별 독립 거버넌스 구현·운영 반영 보고서

- work_id: GOV-CODEX-DEDICATED-20260914
- 작업자/일자: Codex / 2026-09-14 KST
- 상태: 운영 거버넌스 1.7.0 활성화 및 전체 회귀 통과
- 계획: [현재 계획](../../../../Plans/2026/09/14/001_Model_Specific_Governance_Plan.md)
- Task: [검토·실행 이력](../../../../Tasks/2026/09/14/001_Codex_Dedicated_Governance_Review_Task.md)
- 승인 근거: 사용자가 보고서·계획서 확인 후 운영 반영까지 멈춤 없이 진행하도록 명시 승인했다.

## 결과와 범위

운영 버전은 1.7.0이다. Codex/GPT-6 Astra만 독립 프로필에 등록하고 AGENTS에서 legacy 전수 로딩 전에 선택한다. legacy는 모델의 한계를 보완하는 강제 도구이며 독립 경로가 그 체계를 상속하거나 예외로 우회하는 구조가 아니다. 다른 Codex 모델·Claude·Antigravity의 기존 경로를 유지한다. Claude Fable 5.1과 가칭 Gemini 4 Pro의 등록·예약·전용 파일·어댑터는 없다.

프로젝트 루트의 정책·도구 20개 파일만 반영 대상이다. CLAUDE.md·GEMINI.md·CHATGPT.md, 기존 router, 앱·DB·모델 설정·구독은 변경하지 않는다. Linux 서비스 변경이 아니므로 SSH 배포나 재시작은 필요 없다. 이번 승인에 Git 원격 변경을 추가 해석하지 않으며 commit/push는 수행하지 않는다.

## 1~8단계 순차 검증

이 최초 전환은 아직 활성화 전의 기존 절차로 검증했다. 아래는 승인된 계획의 구현·병합 판단이며 활성화 후 Astra 일상 작업에 고정 절차를 다시 부과하는 뜻이 아니다.

| 단계 | 확인 근거와 긍정적 결과 | 위험·조치·판정 |
|---|---|---|
| 1. 거버넌스 | recorder ensure/기존 validate/context pack 확인. Staging/Model_Specific_Governance에 격리 후보. 기존 yaml 2.9.0만 잠금 설치, 새 라이브러리 없음 | 기존 Staging 자료는 이번 대상이 아님. Rule 변경 9개 섹션 전체를 sync-plan으로 연결. 적합 |
| 2. 사용자 의도 | 최초 대상 Astra 1개, parent:null. 기존 kernel/always_load/Task/검증 체인 상속 없음. 등록부 기반 확장 fixture 통과 | Fable/Gemini를 현재 등록하지 않음. 모델의 능력에 관한 자동 승격 없음. 적합 |
| 3. 논리 | profile 분기는 loadGovernance 이전에 반환. 기존 context는 전체 validate와 기존 API 유지. 진행 중 턴/cwd/정확한 모델 확인 | 자체 인수/기본 설정/완료 턴 사용 금지. 세션 JSONL 형식 변경·미확인은 legacy로 안전 복귀. 새 모델 선택 상태 캐시 없음. 적합 |
| 4. 운영 영향 | AGENTS 분기, Rule·노드·등록부·추적성·baseline·manifest 묶음 검증. 대표 legacy 호출 4종의 노드/route/budget 전후 일치 | 첫 후보에서 기존 작은 모델 pack 예산 초과 발견. 규칙·예산·부모를 제거하지 않고 설명 중복 압축 후 회귀 통과. 앱/DB 영향 없음. 적합 |
| 5. 보안·예외 | 중복 ID/모델, disabled 중복, 경로 탈출·junction, 누락/손상, 부모 상속, YAML 중복, 패키지 변조 시험 통과 | 현재 작업 파일 하나의 필요한 메타데이터만 출력. 본문·비밀 미출력. 선택기는 절차 도구이지 인증/플랫폼 권한 획득 장치가 아님. 적합 |
| 6. 복구 | Rule·AGENTS·추적성·선택기·등록부·capability의 부분 교체를 탐지하고 fixture 원본 복귀 후 정상 검증 | 다중 파일 편집은 원자적이지 않음. 관련 변경만 묶어서 복구하며 전체 reset/DB 복원 금지. 복구 패치 별도 보존. 적합 |
| 7. 휴먼 에러 | dedicated/legacy/reason/현재 모델/정책 버전/노드 경로 출력. --model 자가 지정 거부. disabled와 손상 분리 | 성공을 가장한 무음 fallback 없음. 참고 문서로 legacy 강제 재유입 방지. 잘못된 입력으로 운영 데이터 변경 없음. 적합 |
| 8. AI 메타 | 등록부·노드·계획의 대상 일치, 기존 변경 보존, 스킬 근거와 자체 설계 판단 구분 | 실제 앱 UI에서 다른 모델로 전환하는 통합 시험은 이 작업에서 수행하지 않음. 프로젝트 도구가 앱 지침 캐시를 강제 삭제한다고 주장하지 않음. 현재 턴 실측과 격리 전환 시험은 수행. 운영 반영 후 실제 CLI 확인 예정 |

OpenAI Docs 스킬의 공식 안내에서 모호한 지침의 정리와 변경에 비례한 검증을 참고했다. 이를 legacy 절차의 적용 범위 명시와 독립 경로의 불필요한 반복 방지에 반영했다. 실제 로더·등록부 설계는 이 저장소의 구조를 분석한 구현 판단이다. [공식 모델 지침](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)

## 검증 증거

- Rule SHA-256: `F2E6E0E7ED8AFDFE2A95BC5E935FA20D1A9812A248287427AAF4504298C10E11`.
- sync-status: 추가 `12`, `12-1`~`12-4`; 변경 `9-1`, `11-3`, `11-6`, `11-8`; 삭제 없음. 최초 미매핑 새 섹션은 독립 노드의 소유로 정식 등록 후 sync-plan 성공.
- 전체 validate: 44개 manifest 노드, 44개 human map 노드, YAML 12개, 오류/경고 0.
- governance-tool 회귀 14건, context-input 회귀 21건, execution-profile 회귀 33건 통과(총 68건).
- 기존 질문·Staging 구현·DB/UI 복합·작은 모델 Rule 검토 호출의 matchedRoutes/nodes/budget 동일.
- Rule 12-1 자체의 작은 모델 유지보수 context도 기존 5,000 예산 이내로 모든 노드를 보존한다.
- 현재 작업 `01a085d1-89fd-7d02-84b5-090d99671fa4`의 진행 중 `turn_context.model=gpt-6-astra`와 프로젝트 cwd 확인. 후보 선택 함수를 실제 프로젝트 cwd로 호출하여 dedicated, nodes 1개, legacyLoaded:false 확인.
- Staging CLI 자체의 자동 선택은 Staging cwd가 현재 작업 cwd와 다르므로 runtime-session-mismatch/legacy를 반환했다. 후보를 운영으로 가장하지 않는 정상 경계 동작이다. 운영 반영 후 루트 CLI를 따로 확인한다.
- 시험은 Node 거버넌스/격리 fixture이며 Flask 서버 실행 시험이 아니다.

## 복구 절차

복구 패치는 이번 정책 변경만 대상으로 한다. 현재 수정과 충돌하는지 Diff를 확인한 후 구조화 편집으로 관련 파일 전체를 복귀하고 기존 validate 및 recorder ensure를 확인한다. 새 프로필을 단지 비활성화하려면 enabled=false와 등록부→manifest 해시를 일치시킨 후 전체 validate/profile을 확인한다. 다른 작업의 변경·DB·서비스·Git 이력은 되돌리지 않는다.

## 운영 반영 및 최종 결과

- 20개 정책 파일을 구조화 패치로 운영 루트에 반영했다. 반영 전 기존 파일과 초기 원문을 비교해 동시 변경이 없음을 확인했다.
- 운영 루트의 실제 `governance-tool.mjs profile` 결과: `governanceVersion:1.7.0`, `kind:dedicated`, `reason:verified-runtime-exact-match`, `observed.model:gpt-6-astra`, `nodes:[profiles.gpt-6-astra]`, `legacyLoaded:false`. 현재 세션은 이 독립 경로로 전환했다.
- 운영 전체 validate는 동일 Rule SHA로 오류/경고 0. 전체 `npm test` 정상 종료(거버넌스·context·신규 프로필·대화 기록·routed ingest·scope handoff·artifact manager·Git 보호 회귀 포함).
- Git 읽기 보호 도구를 통한 `diff --check` 통과. 무관한 기존 기능/로드맵/사용자 가이드 변경은 보존했다. 해당 기존 문서의 Git 줄바꿈 경고는 이번 거버넌스 결함이 아니다.
- 이번에 만든 `Staging/Model_Specific_Governance`의 후보 복사본과 고정 의존성 파일 313개만 구조화 삭제했다. 기존 다른 Staging 자료는 보존했다. 반영본은 운영 루트, 이전 정책은 [복구 패치](002_Model_Specific_Governance_Rollback.patch)로 보존하며 의존성은 잠금 설치로 복구할 수 있다.
- Plan/Task/검토 Report의 최신 상태를 완료로 연결했다. 보고서의 최초 8단계와 당시 미구현 기록은 검토 이력으로 남긴다.
- 앱 UI의 실제 모델 전환 통합 시험은 미실시지만 현재 턴의 운영 선택과 격리된 전환/완료/중단/부모 비상속 시험은 통과했다. 자동 캐시 삭제나 모든 미래 런타임 형식 지원을 주장하지 않는다.
