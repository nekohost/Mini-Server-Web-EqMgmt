---
artifact_id: REPORT-20261109-006
work_id: STAGING-20261109-AI-CONVERSATION-ENTRY
owner: Codex
status: completed
---

# AI 도우미 첫 화면·첫 접수 Staging 검증

## 구현 전 점검

1. 기록기·정책 검증 통과. 전용 Staging과 보고 자료로 범위를 한정한다.
2. 기존 이력 자동 복원과 명시적 새 대화의 미저장 상태를 분리한다.
3. 서버는 같은 쓰기 트랜잭션에서 대화와 첫 요청을 생성하고 재전송 키를 먼저 대조한다.
4. 후속 전송·관리자 시험과 호환되는 별도 첫 접수 경로를 사용한다.
5. 인증·소유자와 계정·권한·CSRF·보관 및 큐 제한을 재사용한다.
6. DB 구조 변경 없이 기존 레코드를 읽고 후보 파일만 되돌릴 수 있게 한다.
7. 조회 지연·오류·화면 전환·접수 후 응답 유실·한글 입력을 교차 검사한다.
8. 최초 렌더의 관찰과 실제 서버 행 수를 각각 증거로 남기고 기기 재현 범위를 명시한다.

## Staging 적용 결과

AI 도우미의 최초 HTML은 제목·환영 카드·빈 목록 안내를 숨기고 본문에 ‘대화를 불러오는 중입니다.’를 표시한다. 권한을 확인한 뒤 모델 목록과 대화 이력을 독립적으로 읽는다. 내 활성 대화 중 사용자 질문이 있는 가장 최근 대화의 본문이 도착하면 한 번에 표시한다. 미저장 초안이나 다른 대화를 직접 선택하면 이전 조회의 늦은 응답은 그 선택을 덮어쓰지 않는다.

‘새 대화’는 브라우저에서 작성 화면을 열고 미전송 입력을 보존한다. 첫 질문을 보내면 서버의 `POST /api/ai/conversations/first-turn`이 대화, 모델·추론 선택, 첫 사용자 메시지, 답변 자리와 큐 작업을 SQLite 쓰기 트랜잭션 하나에 저장한다. 같은 계정에서 같은 키와 내용으로 재시도하면 이미 발급한 대화와 작업 ID를 돌려준다. 접수 응답이 유실되면 사용자는 원래 요청의 접수 여부를 다시 확인할 수 있다. 접수가 확인된 뒤 본문 읽기만 실패하면 다음 시도는 해당 대화를 다시 읽는다. [계획](../../../../Plans/2026/11/09/005_AI_Conversation_Entry_Plan.md) · [후보 원문](006_AI_Conversation_Entry/reviewed-source.zip)

## PC·모바일 첫 화면

인증된 합성 계정에서 목록 응답을 보류해 첫 화면을 촬영했다. 목록을 돌려준 뒤 본문 응답도 따로 보류해 두 번째 화면을 촬영하고, 본문을 돌려준 다음 세 번째 화면을 촬영했다. Chromium이 문서를 만들 때 설치한 `requestAnimationFrame` 관찰기로 각 구간의 표시 상태를 함께 기록했다.

| 화면 | 테마 | 관찰 프레임 | 환영 / 새 제목 / 잘못된 빈 목록 | 목록 대기 · 본문 대기 · 복원 |
|---|---|---:|---|---|
| PC 1440×900 | 밝음 | 58 | 0 / 0 / 0 | [목록](006_AI_Conversation_Entry/1440-light/01-list-pending.png) · [본문](006_AI_Conversation_Entry/1440-light/02-body-pending.png) · [복원](006_AI_Conversation_Entry/1440-light/03-existing.png) |
| PC 1440×900 | 어두움 | 70 | 0 / 0 / 0 | [목록](006_AI_Conversation_Entry/1440-dark/01-list-pending.png) · [본문](006_AI_Conversation_Entry/1440-dark/02-body-pending.png) · [복원](006_AI_Conversation_Entry/1440-dark/03-existing.png) |
| 모바일 384×860 | 밝음 | 53 | 0 / 0 / 0 | [목록](006_AI_Conversation_Entry/384-light/01-list-pending.png) · [본문](006_AI_Conversation_Entry/384-light/02-body-pending.png) · [복원](006_AI_Conversation_Entry/384-light/03-existing.png) |
| 모바일 384×860 | 어두움 | 54 | 0 / 0 / 0 | [목록](006_AI_Conversation_Entry/384-dark/01-list-pending.png) · [본문](006_AI_Conversation_Entry/384-dark/02-body-pending.png) · [복원](006_AI_Conversation_Entry/384-dark/03-existing.png) |

총 235프레임에서 세 가지 오표시가 각각 0회였다. 네 조건 모두 가로 넘침은 0px였다. 각 조건에서 새 대화 클릭 직후와 첫 접수 확인 직후도 촬영해 원본 20장을 보관했다. 모바일은 폴드 외부 화면 크기를 기준으로 한 Chromium 터치 에뮬레이션이다. [PC 연속 화면](006_AI_Conversation_Entry/desktop-entry.png) · [모바일 연속 화면](006_AI_Conversation_Entry/mobile-entry.png) · [미저장 초안](006_AI_Conversation_Entry/384-dark/04-unsaved.png) · [접수 후 다음 초안 보존](006_AI_Conversation_Entry/384-light/05-first-accepted.png)

## 저장과 재시도

아래 건수는 격리 DB에서 해당 동작으로 늘어난 행 수다. 동시 전송은 독립된 Flask 클라이언트 6개로 실행했고, 응답 유실은 실제 커밋 직후 브라우저로 돌아가는 응답을 502로 바꿔 재현했다.

| 조건 | 새 대화 | 첫 사용자 메시지 | 답변 자리 | 큐 작업 |
|---|---:|---:|---:|---:|
| 새 대화 연타, 제안 문구 입력, 전송 전 새로고침, 공백 제출 | 0 | 0 | 0 | 0 |
| 같은 첫 요청을 6개 클라이언트에서 동시에 제출 | 1 | 1 | 1 | 1 |
| 브라우저에서 연속 제출, 첫 응답 유실 후 같은 키로 재시도 | 1 | 1 | 1 | 1 |
| 접수 한도·모델·입력 검증에서 거절되거나 저장 도중 오류 발생 | 0 | 0 | 0 | 0 |

- 응답 유실 후 같은 키로 확인한 두 번의 HTTP 요청은 하나의 접수를 가리켰다. 그사이에 새로 입력한 문구가 보존됐고, 접수된 대화의 본문을 읽다가 오류가 났을 때에는 조회만 재시도했다. 이미 저장한 모델이 비공개로 바뀐 뒤에도 원래 접수는 확인됐다. 같은 키로 내용을 바꾸면 409를 반환했다.
- 첫 페이지 밖에 있는 실제 대화, 빈 계정, 과거 빈 대화, 다른 계정, 휴지통, 관리자 시험 대화를 확인했다. 과거 빈 대화를 직접 열어 첫 질문을 보내면 같은 ID에 저장됐다. 복원 도중 다른 창에서 해당 대화를 휴지통으로 옮기면 남은 활성 대화를 다시 골랐다.
- 모델 목록 조회에 실패해도 저장된 대화는 읽을 수 있었다. 접수 뒤 모델 응답에 실패하면 질문과 실패 사유를 읽고 후속 질문을 같은 대화에 보낼 수 있었다. 새 대화로 이동해도 이미 접수한 큐 작업은 유지됐다.
- 기존 키보드 검사에서 비활성 입력창에 직접 제출 이벤트를 보낼 수 있는 경로를 발견해 전송 함수에서도 상태를 검사하도록 수정했다. 한글 조합, 개인별 Enter·Shift+Enter 설정, 초안에서 모델·추론 변경 시 쓰기 요청 0회, 로딩 중 새 대화 및 휴지통 선택을 다시 검증했다.

## 최종 검사 기록

| 검사 | 결과 |
|---|---|
| 정적 검사 | JavaScript 3개 구문 검사, Python 4개 AST 파싱, 초기 HTML의 고유 ID 77개·접근성 참조·표시 및 비활성 기본값 검사 통과 |
| 서버·저장소 | 새 접수·복원 시험 6개를 포함한 74개 통과. 모델 전환·관리자 시험·휴지통·페이지 이동·계정 격리 관련 회귀 10개 추가 통과. [서버 검사 로그](006_AI_Conversation_Entry/backend-tests.log) · [관련 회귀 로그](006_AI_Conversation_Entry/related-regression.log) |
| 브라우저 회귀 | 대화 화면 4조건에서 판정 654개, 키보드·초기화 경합 12조건에서 판정 356개 통과. [화면 검사](006_AI_Conversation_Entry/regression-ui.json) · [입력 검사](006_AI_Conversation_Entry/regression-keyboard.json) |
| 보존 | 기준 커밋 `dee0300aedcf5c39efc0c3c1ff409af1bc8313ab`. Staging 원문 9개(기능 5개, 검사 4개)를 실제 검사 환경 및 ZIP과 SHA-256으로 대조했다. [통합 결과](006_AI_Conversation_Entry/verification.json) · [원문·스크린샷 해시](006_AI_Conversation_Entry/source-manifest.json) |

검사에는 Chromium 152, 격리된 Flask 애플리케이션, 임시 SQLite와 합성 모델 응답을 사용했다. 확인 범위는 첫 화면, 요청 접수, 저장, 조회·복구 및 기존 기능과의 호환성이다. 운영 배포는 이번 작업 범위 밖이다.

후속 배포와 운영 HTTPS에서의 실제 화면·DB 확인은 [운영 검증 보고서](007_AI_Conversation_Entry_Release_Report.md)에 기록했다.
