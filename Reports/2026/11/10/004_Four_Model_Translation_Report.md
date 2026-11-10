# 업무 번역 네 모델 개선 검증

1. 거버넌스 — 기록기 복구 후 18개 테스트 통과. 영수증 1,863건과 대화 Markdown 51개 일치. 거버넌스 검사 오류·경고 0건. 독립 시험 사본을 사용한다.
2. 의도 — 네 작성자 모두 같은 양방향 과제를 수행한다. 운영 모델과 일반 대화 설정을 유지한다.
3. 정적 흐름 — 사용자 최초 요청→접수→claim→SSE→저장 경로에서 문안 1편과 도구 0개를 확인한다. 기존 요청 버전 보존을 병합 기준에 포함한다.
4. 운영 영향 — 실험 DB는 운영과 격리하며 새 설정은 검증한 Qwen 방향과 범위에서만 허용한다.
5. 보안 — 합성 문안으로 평가한다. 운영 키는 서버 프로세스 내부에서 사용하며 외부 평가에 전달하지 않는다. 실행기는 문안·지시 구조를 검사한다.
6. 복구 — 운영 코드 기준 27af22a, 이전 응답·작업 상태와 새 검증 결과를 별개로 보관한다.
7. 사용자 오류 — 무응답·경고는 C로 처리하고 재실행이 최초 응답을 덮어쓰지 못하도록 한다.
8. 근거 — 실측과 과거 저장 응답 재생을 구분한다. 익명 자료와 별도 매핑, 채점 원문, 이견과 운영 판정을 보존한다.

## 네 모델이 평가한 번역 설정

Gemini 4 Argon High, Gemini 3.8 Flash High, Claude Opus 5.5 High, GPT-6 Astra Max가 각각 같은 양방향 지침을 작성했다. 다른 세션에서 각 후보로 Qwen이 실제 생성한 메일을 익명으로 교차 채점했다. GPT CLI의 실제 응답 등급은 priority였고, 설정 컨텍스트 872,000, 실효 컨텍스트 828,400을 기록에서 확인했다. 운영은 260Strata의 `qwen3.8-flash-next-iq3_xxs`를 사용하며 영→한은 xhigh, 한→영은 low이다. 원문만 한 편씩 전달하고 도구 호출은 0개다. [설정 증빙](004_Four_Model_Translation/author-settings.json) · [평가 기준](004_Four_Model_Translation/protocol.md) · [개발 채점표](004_Four_Model_Translation/dev-scores.json)

개발 8편에서 기존판의 총괄 등급은 A/B/C 2/5/1이었다. 네 모델의 범용 추가 지시는 각각 1/5/2, 1/6/1, 2/5/1, 2/6/0으로, 전체 업무메일에 공통 적용할 근거가 없었다. 범위를 좁혀 네 모델이 모두 다시 작성하고, 반대 방향으로 빌려주는 경우와 서류 세 종류가 함께 나오는 경우도 비교했다. 실물 대여와 납품 서류에는 Argon의 지침을 선정했다. 주제와 종류를 접수 시 고정하고, 기존 접수의 지시나 저장된 결과를 소급 변경하지 않는다. [소유·서류 재심](004_Four_Model_Translation/ruling-scores.json) · [결선](004_Four_Model_Translation/finalist-scores.json) · [선정 기록](004_Four_Model_Translation/selection.json)

| 변경 파일 | 동작과 검증 |
|---|---|
| `utils/ai_assistant/translation.py` | 실물 대여의 방향·비용과 납품 증빙의 쓰임에 맞는 짧은 지침을 추가한다. 원문에서 같은 수신자를 확인할 수 있으면 한국어 수신자 호칭과 다음 줄의 단독 인사를 한 인사말로 검사한다. 원시 응답과 표시문에 두 줄 모두 남긴다. |
| `tests/test_mail_translation.py` | 두 방향의 조건부 지시와 이전 접수 복원, 다른 프로바이더 및 비대상 메일, 인사말 정상·오류 대조군과 실제 저장 내용을 검사한다. |

기존 영→한 답변은 유상 여부가 없는 예비 펌프를 ‘임차 중’이라고 했다. 후보는 ‘공급업체로부터 … 빌려 두고 있습니다’로 옮겼다. 한→영의 `Delivery Specification`은 실제 납품 증빙을 뜻하는 `delivery note`로 바뀌었고 수량 대조·재발급 보류도 유지됐다. ‘상자 안의 납품서는 보관해 주세요’는 두 설정 모두 `keep the delivery note inside the box`라고 써서 보관 장소까지 지정한 것으로 읽힐 수 있다. 이 사례의 총괄 판정은 둘 다 B이다. [실제 원문·출력과 시간](004_Four_Model_Translation/confirmation-measurements.json)

과거 Hermes 20편은 당시 실제 260Strata 답변의 첫 원시 스트림을 기존판과 최종 후보에 재생했다. 전달 지시와 저장된 답변이 20/20건 일치했다. 이전 등급은 영→한 10/0/0, 한→영 8/2/0이다. 이번 신규 생성 건수와 별도로 집계한다. [회귀 재생 기록](004_Four_Model_Translation/historic-final-replays.json)

## 품질과 시간

A는 필수 수정 없이 발송 가능, B는 필수 수정 필요, C는 중요한 오류·미완료이다. 아래는 총괄 원문 대조 등급과 생성 요청의 중앙값이다. ‘적용 대상’에는 선정 과정에 쓰인 문안도 있다. ‘미사용’은 선정 후 검증에만 쓴 문안이며, 일부 문안은 두 집합에 모두 포함된다.

| 문안 묶음 | 방향 | 문안 수 | 기존 A/B/C | 개선 A/B/C | 기존 → 개선 중앙값 |
|---|---|---:|---:|---:|---:|
| 대여·물류 서류 | 영→한 | 4 | 1/2/1 | 4/0/0 | 24.36초 → 51.65초 |
| 대여·물류 서류 | 한→영 | 4 | 1/3/0 | 2/2/0 | 18.11초 → 19.24초 |
| 선정에 쓰지 않은 문안 | 영→한 | 5 | 4/0/1 | 4/1/0 | 13.96초 → 26.80초 |
| 선정에 쓰지 않은 문안 | 한→영 | 5 | 4/1/0 | 3/2/0 | 14.81초 → 18.80초 |

미사용 문안 전체에서 A는 8/10에서 7/10으로 줄었다. 환불 제목의 `credit`을 ‘신용’으로 옮긴 사례와 ‘가능한지만’의 한정을 약화한 사례는 기존·후보가 완전히 같은 지시·모델·추론 설정으로 각각 새 답을 낸 것이었다. 이 두 편을 포함해 지시가 같았던 6편의 기존 원시 답을 후보 저장 경로로 다시 처리하면 6편 모두 기존 표시문과 같다. 새 지침의 효과는 업무 종류에 따라 다르고 일반 업무메일 전체가 무수정 발송 가능하다는 목표에는 미달한다. [범위 대조](004_Four_Model_Translation/confirmation-scopes.json) · [동일 입력 재생](004_Four_Model_Translation/shared-control-replays.json) · [방향별 시간·등급·평가자별 수치](004_Four_Model_Translation/quality-summary.json)

반납 주체를 ‘아직 반납되지 않았습니다’로 표시한 후보는 익명 재심에서 네 모델 중 세 곳이 더 높게 평가했다. 상자 안에 있던 문서와 상자 안에 보관할 의무의 차이는 재심에서도 두 곳이 필수 수정으로 보았다. 원문이 보관 위치를 요구하지 않으므로 총괄은 B를 유지했다. 새 물류 문안에서는 `bill of lading`보다 `waybill`이 운송장에 맞았으나, 수령 증빙과 `cost billing`의 표현은 발송 전에 다듬어야 한다. 마지막 대여 문안은 네 외부 평가자 모두 기존 C, 개선 A였다. 총괄은 그 두 편의 추가 검사에서 기존 요청 한 건의 실패 상태를 먼저 보았다. 네 외부 채점 세션에는 판본 또는 실패 원인이 전달되지 않았다. [10편 교차 채점](004_Four_Model_Translation/confirmation-scores.json) · [6편 독립 재심](004_Four_Model_Translation/arbitration-scores.json) · [추가 2편의 원문·저장 결과](004_Four_Model_Translation/prospective-measurements.json) · [추가 채점](004_Four_Model_Translation/prospective-scores.json)

Staging에서 실제 260Strata 추론은 76회였고 최초 저장 72회, 실패 4회였다. 개발 후보의 서명 확인 실패 2건과 정상적인 두 줄 인사를 다른 메일의 혼입으로 판단한 2건을 원래 상태로 보존했다. 후자 2건은 같은 모델 원문을 수정된 저장 경로에 제출해 성공했다. 대여 문안의 개선에는 이 처리 변경도 기여한다. 독립 계측의 요청 ID 76개가 모두 달랐고 실행 시간대가 겹친 건수는 0이었다. [전체 집계](004_Four_Model_Translation/quality-summary.json) · [두 줄 인사 재생](004_Four_Model_Translation/envelope-counterfactual.json)

| 독립 채점자 | 적용 대상 8편 기존 → 개선 A/B/C | 선정에 안 쓴 10편 기존 → 개선 A/B/C |
|---|---:|---:|
| Gemini 4 Argon High | 4/2/2 → 5/3/0 | 6/3/1 → 5/5/0 |
| Gemini 3.8 Flash High | 4/2/2 → 5/3/0 | 6/2/2 → 5/4/1 |
| Claude Opus 5.5 High | 5/2/1 → 8/0/0 | 8/1/1 → 8/2/0 |
| GPT-6 Astra Max | 2/4/2 → 5/3/0 | 6/3/1 → 6/4/0 |
| 총괄 원문 대조 | 2/5/1 → 6/2/0 | 8/1/1 → 7/3/0 |

이 표는 첫 익명 판정과 선정 문안의 정식 재심을 어떻게 집계했는지 재현하는 고정 표다. 6편의 추가 재심은 원문 근거 확인에 사용했으며 앞선 표를 유리한 재채점으로 덮어쓰지 않았다. 발송자 한글 표기는 원문 발신자 식별 정보를 지키는 정책에 따른다. 평가자에게는 필수 수정과 표현 선호를 구분해 달라고 요청했다. [점수 집계 코드](004_Four_Model_Translation/quality_summary.py)

## 운영 반영과 확인

2026년 11월 10일 13시 03분 57초 KST에 `926dd9f7f38f0991295273e01d1130a31ebd6436`이 활성화됐다. 배포 전후 서비스 전환은 19.91초였다. 기존 감사·업무·AI 행과 서버 설정을 보존했고 워커와 보관 정리 타이머는 정상이다. 메일마다 신규 사용자 메시지 1개와 답변 1개, 모델 단계 1개가 저장됐고 제안·도구 실행은 0건이었다. [배포 영수증](004_Four_Model_Translation/release-result.json) · [DB 사본 검증](004_Four_Model_Translation/release-copy-summary.json) · [운영 상태](004_Four_Model_Translation/final-health.json)

최종 소스의 Linux 회귀는 306/306, Node의 메일 표시·스트리밍·복구 검사는 25/25였다. 처음에는 브라우저 전용 테스트 3개를 Node에서 잘못 실행해 실패했다. 실제 Chromium에서 AI 도우미와 포털을 390px·1440px로 검증했다. 휴지통 테스트는 기존판과 후보 모두 구형 모의 목록에서 `resume_conversation` 누락으로 첫 대화 로드에 실패했다. 모의 응답을 현행 API와 맞추고 기존 검증문을 그대로 재실행해 각 너비에서 35/35를 통과했다. 인사말 수정 중 발견한 ‘호칭·인사·서명만 있어도 통과’ 반례를 최종 코드에서 거부한다. 최종 저장 경로로 12쌍의 채점 결과를 대조하고 과거 20편의 기존 결과도 보존했다. [최종 소스 지문](004_Four_Model_Translation/release-source-manifest.json) · [Linux 결과](004_Four_Model_Translation/release-qa.json) · [브라우저 모의 응답 대조](004_Four_Model_Translation/browser-lifecycle-current.json) · [최종 표시문 일치](004_Four_Model_Translation/release-panel-equality.json) · [과거 결과 일치](004_Four_Model_Translation/release-historic-replays.json)

일반 권한 계정에서 공개 운영 주소의 같은 대화로 합성 메일 두 편을 순차 전송했다. 첫 응답과 새로고침 후 표시가 두 편 모두 DB에 저장한 답과 일치했다.

| 방향 | 운영 실측 | 실제 표시 내용 |
|---|---:|---|
| 영→한, xhigh | 53.01초 | 예비 센서를 유통업체에서 빌려 왔고 시험대는 우리 소유이며 운송비 부담에 합의하지 않았다는 뜻을 보존했다. [원문과 응답](004_Four_Model_Translation/live-mail/en-ko.json) · [화면](004_Four_Model_Translation/live-mail/en-ko.png) |
| 한→영, low | 15.62초 | 포장명세서의 여섯 상자, 실수량 대조 중, 차이 확인 시 사본만 요청한다는 조건과 발신자 한서린을 보존했다. [원문과 응답](004_Four_Model_Translation/live-mail/ko-en.json) · [화면](004_Four_Model_Translation/live-mail/ko-en.png) |

운영 영→한은 총괄과 네 평가자 모두 A였다. 운영 한→영은 총괄·Argon·Opus·Astra가 A, Flash가 B였다. Flash의 지적은 한서린을 영문 서명으로 바꾸라는 것이었다. 원문에는 당사자의 공식 영문명이 없으므로 발신자 식별 정보를 보존하는 정책을 적용했다. 최초 Opus 운영 채점은 할당량 오류 429로 종료됐다. 할당량 복구 후 같은 입력 지문으로 다시 접수해 두 편 모두 A를 받았다. 재채점은 Qwen을 추가로 호출하지 않았다. 15시 07분 KST에도 운영 소스 지문, 로그인 응답, 워커와 보관 정리 타이머를 다시 확인했다. [운영 사용자 화면](004_Four_Model_Translation/live-mail/verified.json) · [최초 호출 기록](004_Four_Model_Translation/production-opus-first-attempt.json) · [최종 점수](004_Four_Model_Translation/production-scores.json) · [마지막 서비스 확인](004_Four_Model_Translation/closeout-health.json)

## CLI 입력과 공개 답변

| 같은 과제를 받은 단계 | 입력 | 모델 답변 원문 |
|---|---|---|
| 양방향 지침 작성 | [작성 지시](004_Four_Model_Translation/author-instruction.txt) | [네 모델](004_Four_Model_Translation/author-responses.json) |
| 범용 후보 40건 평가 | [채점 지시](004_Four_Model_Translation/grading-instruction.txt) · [익명 문안](004_Four_Model_Translation/dev-blind.json) · [Flash 재요청 입력](004_Four_Model_Translation/dev-flash-retry-input.txt) | [네 모델](004_Four_Model_Translation/dev-replies.json) · [Flash 최초 시도](004_Four_Model_Translation/dev-flash-empty-attempt.json) |
| 대여·문서 지침 작성 | [작성 지시](004_Four_Model_Translation/micro-instruction.txt) | [네 모델](004_Four_Model_Translation/micro-replies.json) |
| 개발·대여·문서 재심 | [지시](004_Four_Model_Translation/ruling-instruction.txt) · [익명 문안](004_Four_Model_Translation/ruling-blind.json) | [네 모델](004_Four_Model_Translation/ruling-replies.json) |
| 결선 두 후보와 기존판 | [지시](004_Four_Model_Translation/finalist-instruction.txt) · [익명 문안](004_Four_Model_Translation/finalist-blind.json) | [네 모델](004_Four_Model_Translation/finalist-replies.json) |
| 10편 독립 비교 | [전체 입력](004_Four_Model_Translation/confirmation-instruction.txt) | [네 모델](004_Four_Model_Translation/confirmation-replies.json) |
| 이견 6편 재심 | [전체 입력](004_Four_Model_Translation/arbitration-instruction.txt) | [네 모델](004_Four_Model_Translation/arbitration-replies.json) |
| 추가 미사용 2편 | [전체 입력](004_Four_Model_Translation/prospective-instruction.txt) | [네 모델](004_Four_Model_Translation/prospective-replies.json) |
| 운영 합성 번역 2편 | [전체 입력](004_Four_Model_Translation/production-instruction.txt) | [네 모델 및 Opus 재호출](004_Four_Model_Translation/production-replies.json) · [최초 상태](004_Four_Model_Translation/production-first-panel.json) |
