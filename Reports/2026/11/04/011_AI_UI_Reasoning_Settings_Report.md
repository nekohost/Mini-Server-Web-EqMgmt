---
artifact_id: REPORT-20261104-011
work_id: FIX-20261104-AI-UI-REASONING-SETTINGS
owner: Codex
created_at: 2026-11-04
status: completed-staging
---

# AI 글자색·추론 모델 설정·모바일 가독성 보완

## 사전 Validation (순차)

1. **거버넌스:** recorder 정상, profile legacy/runtime-session-mismatch, governance 1.8.1/44 nodes/0 errors·warnings. 필수 context pack을 읽고 현재 후보만 변경한다. 운영 app·기존 009/010 산출물과 다른 작업자의 변경은 보존한다.
2. **의도:** 배경 고정/글자색 수정, 표준 단계의 전체 노출과 지원 밖 disabled, 관리자 조절/Qwen 사전 설정, 모바일 적정 글자 크기를 각각 구현한다. 기존 한글 3단계 별칭은 이번 사용자 지시로 표준 값 표기로 변경한다. 운영 배포 권한으로 확대하지 않는다.
3. **논리/예외:** low/high의 기존 의미가 새 이름과 충돌하므로 profile 버전·선택 이전·frozen route/probe를 분리한다. 알려진 지원 상한과 관리자 허용/검증 단계의 교집합을 서버에서 확인하며 선택 불가 이유와 모델 기본값 상태를 구분한다. 기존 접수 작업을 새 의미로 재해석하면 차단 조건이다.
4. **운영 영향:** schema 열 추가 대신 기존 profile JSON을 사용한다. backend/frontend를 함께 적용해야 하며 오래 열린 클라이언트가 새 명칭으로 오인되지 않게 복원/재선택을 처리한다. 운영 DB·서비스·실모델에는 접근하지 않는다. 실제 배포 시 AI DB 백업과 작업 drain/호환 버전 동시 적용이 필요하다.
5. **보안:** 관리자 외 설정 쓰기 금지와 기존 CSRF를 유지한다. DOM disabled만 신뢰하지 않고 잘못된 타입·중복/미지원 단계·비허용 기본값·revision 변경을 서버에서 거부한다. 표시는 textContent/native control로 구성하며 주소/키 노출과 외부 제어를 추가하지 않는다.
6. **복구:** 현재는 Staging source 변경이며 운영 데이터 이전이 없다. 기존 기록을 보존하고 변경 파일·해시·diff를 식별한다. 새 profile 형식이 저장된 환경은 이전 UI/서버만 단독 복귀하지 않고 일관된 AI DB 백업/코드 쌍으로 복원해야 한다. frozen accepted jobs/history를 덮어쓰면 실패다.
7. **UX:** dark의 흰 입력/버튼 글자는 dark 본문과 구분하고 배경색은 그대로 둔다. 드롭다운의 모든 표준 단계·disabled 사유·관리자 기본값 및 모델 변경 후 이전 선택이 비허용일 때 명확한 재선택을 확인한다. 12px 안내문이 입력창을 가리거나 가로 넘침을 만들지 않아야 한다.
8. **메타/근거:** [Qwen 공식 모델 카드](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)는 low/medium/xhigh와 별도 추론 끄기를 설명한다. 이를 사전 지원 설정의 근거로 사용하되 두 PC의 실모델을 이번에 검증했다고 주장하지 않는다. 합성 기능 시험·새 스크린샷과 과거 106/83 결과를 구분한다. 실제 측정 후 결과를 추가한다.

## 구현·검증 결과

사용자가 요청한 세 항목을 현재 Staging 후보에 반영했다. 운영 앱·DB·서비스와 실제 Strata 설정은 변경하지 않았다. 최종 Linux 합성 검사에서 **backend 112개 / browser 93개 통과**, 수정 후 화면 **18장**을 캡처·시각 검토했다.

- [수정 전·후 및 18장 화면 갤러리](011_AI_UI_Reasoning_Screens/index.html)
- [최종 검사·소스 SHA·캡처 및 배경색 비교 원장](011_AI_UI_Reasoning_Screens/manifest.json)
- [파일 무결성 검증](011_AI_UI_Reasoning_Screens/verification.json)
- [중간 검사와 보완 이력](011_AI_UI_Reasoning_Screens/validation-attempts.json)

### 요청별 반영

| 요청 | 적용 결과 | 확인 근거 |
| --- | --- | --- |
| 테마 배경 고정, 글자색 변경 | 관리자 dark 본문·제목·label을 `#e2e8f0`, 보조 설명을 `#b8c5d6`으로 보완했다. 흰 입력란·버튼의 글자는 `#253044`로 유지했다. 기존 배경 선언을 바꾸지 않았다. | 이전 010과 같은 16개 상태/크기의 body 및 대응하는 기존 요소 배경색이 일치한다. dark 제목/label 대비 **1.347→14.482:1**, 설명 **3.028→10.198:1**. [desktop](011_AI_UI_Reasoning_Screens/samples/08-admin-models-dark-desktop.png), [mobile](011_AI_UI_Reasoning_Screens/samples/08-admin-models-dark-mobile.png) |
| 표준 추론 명칭과 모델별 제한·관리자 설정 | off/low/medium/high/xhigh/max 모두 표시하고 미지원·미허용·미검증 항목을 비활성화한다. 관리자 모델 카드에서 허용 단계와 기본값을 조절한다. 알려진 지원 상한은 서버에서도 강제한다. | native option의 실제 disabled 상태와 서버 거부를 검증했다. [관리자 desktop](011_AI_UI_Reasoning_Screens/samples/09-admin-reasoning-dark-desktop.png), [mobile](011_AI_UI_Reasoning_Screens/samples/09-admin-reasoning-dark-mobile.png) |
| 작은 안내문 | 하단 등록·수정 확인/업무 범위 안내를 desktop/mobile 모두 **12px**, line-height 1.6으로 조정했다. 모바일의 8px override를 제거했다. | 실제 계산 크기 12px 및 줄바꿈 확인, 가로 넘침 0. [모바일 기본 화면](011_AI_UI_Reasoning_Screens/samples/01-user-welcome-mobile.png) |

010의 UI-01과 UI-I01을 보완했다. UI-02의 추론 표기는 이번 사용자 지시에 따라 한글 3단계 대신 표준 명칭으로 통일했다. 출처의 `none`은 `off`로 표시하고 medium/xhigh 등은 선택 메뉴와 같은 표준 값으로 표시한다. 과거 답변의 실제 provider/model/effort 스냅샷은 바꾸지 않았다. 010 당시의 미수정 기록과 PNG는 원본 그대로 보존한다.

### Qwen3.8 Flash Next 사전 설정

현재 승인된 Strata 모델 계열의 upstream ID를 기준으로 다음 설정을 준비했다. 표시 이름만 같다는 이유로 다른 모델에 이를 부여하지 않는다. 기본값은 기존 대화 경험을 유지하도록 **medium**이다.

| 표시 단계 | 기본 허용 | 이 모델에서의 의미 |
| --- | --- | --- |
| off | 허용 | 추론 끄기, 기존 Strata wire 값 `none` |
| low | 허용 | 실제 `low` |
| medium | 허용·기본 | 실제 `medium` |
| high | 비활성·목록 유지 | 알려진 지원 범위 밖, 관리자 저장도 거부 |
| xhigh | 허용 | 실제 `xhigh` |
| max | 비활성·목록 유지 | 알려진 지원 범위 밖, 관리자 저장도 거부 |

근거는 [Qwen 공식 Flash Next 모델 카드](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)의 low/medium/xhigh 및 별도 추론 끄기 지원과 기존 Strata의 none 전송 계약이다. **이번에는 실제 두 Strata PC에 새 생성 요청을 보내지 않았다.** 위 내용은 Staging 코드의 사전 설정이며 실서버 설정 변경 완료라는 뜻이 아니다. 자동으로 아는 지원 사전 설정은 현재 Strata의 이 계열에 한정한다. 다른 모델/엔진 조합은 명시적 관리자 설정과 기능 시험을 사용한다.

추론 파라미터를 제공하지 않거나 관리자가 수준 지정을 해제한 모델은 `모델 기본값`으로 구분한다. 여섯 표준 항목은 목록에 남지만 비활성이고 reasoning_effort를 보내지 않는다. 이 상태를 off라고 표시하거나 실제 추론이 꺼졌다고 주장하지 않는다.

### 관리자 설정과 서버 검증

`/admin/ai/providers` → 연결 선택 → 모델 카드의 **사용자에게 허용할 추론 수준**과 **새 선택의 기본 추론 수준**에서 조절한다. 저장 후 **저장된 설정으로 기능 시험**을 실행한다. 이 버튼의 모델 호출은 이전과 같이 장비관리 내부 자원 그룹 큐를 사용하며 타 서비스 큐·모델 load/unload는 조작하지 않는다.

설정은 기존 AI 모델 `profile` JSON에 `reasoning_version=2`, `enabled_levels`, `default_level`, `verified_levels`로 보관한다. 스키마 열을 추가하거나 기록을 삭제하지 않았다. 사용자에게 공개하는 실제 levels는 알려진 지원 범위 또는 시험에서 확인한 단계와 관리자 허용값의 교집합이다. 미확인 모델은 설정만으로 임의의 high/max가 승인되지 않는다. 알려진 Qwen 사전 설정과 실제 probe 검증 결과는 원장에 구분한다.

새 허용 범위/기본값 또는 context 계약이 바뀌면 profile revision이 증가하고 모델 시험 상태가 무효화된다. stale 관리자 저장과 시험 도중 설정 변경은 충돌로 거부한다. 일반 사용자의 설정 쓰기, 잘못된 타입/중복 단계/미지원 값/허용 범위 밖 기본값을 거부하며 부분 저장하지 않는다. 브라우저의 disabled 속성을 제거해도 서버의 선택·접수 검증이 남는다.

기능 시험은 서버가 구성한 대화+선택한 도구+최대 6개 추론 단계의 **최대 8개** 항목만 처리한다. 일반 사용자 작업의 기존 **6단계** 제한은 유지한다. nonce와 실제 SSE/도구/추론 출력의 호환을 확인하지만, 짧은 출력만으로 공급자가 각 강도를 실제로 구별하는지나 품질·장문 성능을 입증하지는 않는다.

### 기존 대화와 접수 작업 보존

이전 UI는 low→none, medium→medium, high→xhigh였다. 새로운 low/high와 구분하기 위해 기존 profile과 대화의 **다음 선택**을 off/medium/xhigh로 이전한다. 초기 registry를 만들기 전의 미선택 구 대화와 새 미선택 대화도 구분하며 새 행은 `default`로 만든다. 이전 데이터의 이름만 보고 과거 답변 출처를 새로 꾸미지 않는다.

과거 job.level, 선택 이력, 이미 수락된 route_snapshot과 probe 계획은 그대로 둔다. version 없는 옛 probe의 low/high는 계속 none/xhigh로 전송한다. 새 UI/API의 변경 요청은 `reasoning_version=2`를 요구하여 오래 열린 구 화면이 새 low/high 의미로 작업을 발신하지 못하게 하고 새로고침을 안내한다. 모델/설정 변경은 다음 요청에만 적용된다.

현재는 Staging source 수정이며 운영 AI DB를 이전하지 않았다. 실제 반영 시 AI DB 백업과 호환되는 app/worker/UI를 함께 확인해야 한다. 새 profile 형식이 저장된 DB에 구 서버/UI만 단독 복귀하면 의미가 달라질 수 있으므로, 실패 시 신규 접수를 닫고 일관된 코드·AI DB 백업 쌍으로 복귀한다. 확정된 장비 변경·감사·대화 이력을 지우는 방식은 사용하지 않는다.

### 검증 결과

| 검사 | 최종 실제 결과 |
| --- | --- |
| Linux backend | **112개 통과**, 실패/오류/skip 0, **237.248초**. 기존 68개 기본 회귀와 확장 ProviderTests 44개. |
| 실제 Chromium browser | **93개 통과**. 사용자 desktop 32/mobile 33, 관리자 desktop 14/mobile 14. 사용자 모델 복원·출처·disabled·12px 안내문과 관리자 허용 단계/기본값/profile revision 저장을 포함. |
| 정적 검사 | overlay Python **15개 AST**, 신규 capture/내장 remote AST, 제품 JS 2개와 capture JS 2개 syntax 통과. |
| 수정 후 화면 | 실제 원문 Jinja/JS/CSS·공통 frame/static, desktop 1440×1000 / mobile 390×844, **18장 모두 초기화 완료·JS 예외 0·문서 가로 넘침 0**, 전수 시각 확인. 모바일 PNG의 500px 바깥 치수에는 양쪽 55px 회색 캡처 여백이 포함됨. |
| 보존 | 운영 app.py, 공통 frame/static 11개, 기존 보호 기록 6개, 010 PNG 18개와 캡처 도구 3개 해시 동일. 009 검증 원장은 변경하지 않음. |
| 거버넌스 | 1.8.1 / 44 nodes / errors·warnings 0. 일반 파일 편집은 구조화 patch, 테스트는 승인된 Linux 합성 환경. |

추가 회귀 6개는 표준 low와 off의 실제 wire 구분/구 화면 거부, 관리자 범위·기본값·revision·서버 거부, 미확인 모델의 최대 8단계 실제 worker+loopback SSE 시험, 기존 선택/route 보존과 이전 멱등성, 기존 probe 별칭 보존, 최초 registry 이전·새 모델 기본값/미확인 모델 자동 승인 금지를 검사한다. 권한·감사·큐·멱등·오류/보관 테스트는 유지했다.

중간 검사에서는 확장 probe가 기존 6단계 제한에 걸리는 실제 결함과 일부 fixture에 남은 옛 low 기대값을 발견했다. 제한은 probe에만 최대 8개로 조정하고 일반 업무 제한은 유지했으며, 추론 설정 미지원 기대값을 명시적인 default와 여섯 단계 disabled 검사로 갱신했다. 최종 결과는 이 보완과 추가 최초 이전 회귀를 포함한 새 전체 실행 결과다. 과거 009의 106/83 결과를 이번 통과 수치로 재사용하지 않았다.

## 후속 Validation (순차)

1. **거버넌스:** 현재 legacy/runtime-session-mismatch 경로를 지켰고 Task→Plan→사전 1~8→Staging 수정→허용된 Linux 검사 순으로 진행했다. 운영/기존 기록은 보존했다. 새 의존성이나 운영 배포는 없다. 코드 계약 변경의 EN revision/신규 핵심 ID를 기록했고 KO 감사 완료를 주장하지 않는다.
2. **의도:** 배경 고정+글자색, 표준 6개와 지원 밖 disabled, 관리자 조절/Qwen 사전 설정, 적정 안내문 크기를 각각 실제 화면과 API에서 확인했다. 한국어 3단계의 옛 요구를 이번 표준 명칭 지시로 대체했고 관리자 고급 endpoint customization으로 확대하지 않았다.
3. **논리/예외:** 최종 112/93 통과. legacy low/high와 새 low/high를 분리하고 다음 선택만 이전했다. profile/config/probe revision 충돌과 미지원 입력은 거부하며 old frozen jobs/probes는 원래 wire를 유지했다. unknown 모델은 설정과 검증을 구분한다. probe 확장만 8항목으로 한정했다.
4. **운영 영향:** root app.py SHA `6244893711252F6C78BF36C53CC010BBB485E22C773EBFF038D8F7D3EEE8A581` 유지. 공통 frame/static·다른 기능과 실제 서비스/DB는 변경하지 않았다. API에 형식 버전이 생겨 app/UI를 함께 적용해야 하며 옛 클라이언트는 새로고침 전 실패하도록 했다. 실서버 통합은 이번 검사 밖이다.
5. **보안:** 실제 admin/CSRF/owner 경계, known ceiling·관리자 허용 교집합, 타입/중복/기본값/profile revision 거부를 검증했다. textContent/native controls를 사용한다. 실제 API key·계정·대화를 사용하지 않았고 새 외부 도구나 공유 서비스 제어를 추가하지 않았다.
6. **복구:** 운영 DB/schema 변경이 없으며 기존 source 원장·010 PNG와 도구를 보존했다. profile JSON의 전진 이전은 다음 선택만 바꾸고 frozen 자료는 보존한다. 실제 배포 이후의 복귀는 호환 코드/AI DB 백업 쌍을 사용해야 하며 실운영 복구 훈련은 하지 않았다. Linux fixture의 임시 DB/profile/server는 기존 격리 수명 규칙으로 정리했다.
7. **UX:** 18장 전수 시각 확인 및 기존 16장과 배경 비교. dark 밝은 제목/항목명과 흰 입력/버튼의 어두운 글자, 여섯 단계 표시·disabled 이유, 모델 기본값의 별도 설명, 12px 줄바꿈을 확인했다. 관리자 체크박스는 한 줄 label로 정렬했고 모바일에서도 가로 넘침이 없다. native 모바일 키보드·확대·스크린리더까지 검증한 결과는 아니다.
8. **메타:** 공식 모델 카드의 지원 사전 설정, 합성 fixture의 실제 통과, 실모델 미검증을 구분한다. 최종 소스/PNG hash·배경 비교와 중간 보완 이력을 별도 JSON에 남겼다. 010의 당시 결함 보고를 덮어쓰지 않았다. 다른 PC/서비스에 승인 요청·메시지·생성·설정 변경을 보내지 않았으며 Git commit/push도 수행하지 않았다.

최종 무결성 검증은 **2026-11-04 21:35:30 KST, pass / 오류 0**이다. 새 PNG 18장, 후보 source/guide 26개, 캡처 원문 asset 18개와 도구 3개를 SHA로 대조했다. 이전과 같은 body 16장 및 기존 요소 배경 24개의 값이 일치한다. 최종 갤러리는 새 이미지 18장과 이전 dark 화면 비교를 포함한다.
