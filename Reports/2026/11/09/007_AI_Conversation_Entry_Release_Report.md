---
artifact_id: REPORT-20261109-007
work_id: RELEASE-20261109-AI-CONVERSATION-ENTRY
owner: Codex
status: completed
---

# AI 도우미 첫 화면 및 새 대화의 운영 검증

1. 기록기와 거버넌스 1.8.1 검증 통과. 실행 프로필은 legacy/runtime-session-mismatch였다.
2. [승인된 Staging 보고서](006_AI_Conversation_Entry_Staging_Report.md)의 기능 5개 및 검사 4개를 운영 루트에 반영한다.
3. 검토 ZIP과 파일별 SHA-256, 운영 소스와 서버 HEAD를 대조한다. DB 스키마 버전은 4다.
4. 운영 DB 사본을 후보로 기동해 원래 행과 권한을 검증한 뒤 웹과 워커를 전환한다.
5. 일반 시험 계정으로 PC·모바일에서 각각 장비를 변경하지 않는 짧은 질문 한 개를 전송한다. 브라우저 로그인과 CSRF 보호를 사용하고 인증 값은 검증 자료에서 제외한다.
6. 이전 코드·DB·설정·프로세스의 비공개 백업을 보관한다. 점검 상태와 활성 작업을 두 번 확인하고 기존 요청을 보호한다.
7. 운영 HTTPS에서 PC·모바일의 프레임과 스크린샷을 확인하고, 동일 접수 키의 중복 전송과 새로고침 전후 건수를 운영 DB에서 읽는다.
8. Staging 증거와 운영 검사를 분리해 보관하고 브라우저 재현 범위 및 실제 검증 중 생성한 자료를 기록한다.

## 운영 적용과 실제 요청

2026년 11월 9일 12시 11분 46초(KST)에 소스 커밋 `ba6ec691a12cd0b00b8668a4e99f56b9bb078a00`를 운영에 적용했다. 접수 제한 전 점검을 시작해 정상 운영으로 복귀하기까지 34.71초가 걸렸다. 코드 5개와 검사 파일 4개를 검토 ZIP, Git, Linux 체크아웃에서 대조했다. 공개 HTTPS로 내려받은 채팅 JavaScript와 CSS도 검토본과 SHA-256이 일치했다. [배포 기록](007_AI_Conversation_Entry_Release/entry-deployment.json) · [운영 HTTP 검증](007_AI_Conversation_Entry_Release/public-http.json)

일반 계정 `test04`로 운영 도메인에 로그인했다. 같은 로그인 세션에서 Chromium의 화면 폭과 터치 설정을 바꿔 각 기기에 서로 다른 짧은 시험 질문을 한 번씩 보냈다. 모델은 두 건 모두 ‘확인’이라고 답했으며, AI 도우미에 다시 접속하면 저장된 질문과 답변이 표시됐다. 아래 프레임 수는 자연 진입 1회와 목록·본문 응답을 이 시험 브라우저에서만 차례로 보류한 진입 1회의 합계다.

| 운영 화면 | 자연 진입 | 응답 지연 | 환영 / 새 제목 / 잘못된 빈 목록 노출 | 전송 전 새 대화 | 중복 제출 후 새 대화·질문·큐 작업 |
|---|---:|---:|---|---:|---|
| PC 1440×900 | 12프레임 | 30프레임 | 0 / 0 / 0 | 0건 | 1건씩 |
| 모바일 384×860 | 12프레임 | 23프레임 | 0 / 0 / 0 | 0건 | 1건씩 |

- 계정의 기존 대화가 있는 상태에서 ‘새 대화’를 반복해서 누르고, 입력만 하거나 공백으로 제출하고, 새로고침하고, 추론을 바꿨다. 첫 질문을 실제로 보내기 전에는 두 화면 모두 대화 생성·전송 POST가 0회였고 운영 DB의 대화·사용자 메시지·답변 자리·작업 증가도 모두 0건이었다.
- PC와 모바일에서 각각 보내기 후 즉시 제출을 반복했다. 화면은 최초 POST 한 번만 만들었다. 서버의 중복 방지도 검증하기 위해 그 요청의 인증·CSRF·본문·접수 키를 그대로 사용해 운영 HTTPS에 두 건을 동시에 전달했다. PC의 두 응답 모두 HTTP 202와 동일한 대화·작업 ID였다.
- 모바일은 서버가 접수한 뒤 첫 응답을 시험 브라우저 안에서 누락시켰다. ‘같은 요청 다시 확인’을 터치한 세 번째 요청도 HTTP 202와 같은 ID를 반환했다. 그사이에 적은 다음 질문이 입력창에 남았으며, 답변 자리도 기기당 한 건만 생겼다. [실측 결과](007_AI_Conversation_Entry_Release/verification.json) · [모바일의 접수 복구 직후](007_AI_Conversation_Entry_Release/mobile/05-first-accepted.png)
- 네 번의 진입 관찰에서 브라우저 오류와 페이지 가로 넘침이 없었다. 두 화면 모두 시험 계정의 시스템 테마(어두운 화면)에서 촬영했다. 모바일은 폴드 외부 화면 폭에 맞춘 Chromium 터치 에뮬레이션이다. [PC 연속 화면](007_AI_Conversation_Entry_Release/desktop-entry.png) · [모바일 연속 화면](007_AI_Conversation_Entry_Release/mobile-entry.png)

| 운영 원본 스크린샷 | 목록 대기 | 본문 대기 | 대화 복원 | 미저장 초안 | 첫 접수 |
|---|---|---|---|---|---|
| PC | [보기](007_AI_Conversation_Entry_Release/desktop/01-list-pending.png) | [보기](007_AI_Conversation_Entry_Release/desktop/02-body-pending.png) | [보기](007_AI_Conversation_Entry_Release/desktop/03-restored.png) | [보기](007_AI_Conversation_Entry_Release/desktop/04-unsaved.png) | [보기](007_AI_Conversation_Entry_Release/desktop/05-first-accepted.png) |
| 모바일 | [보기](007_AI_Conversation_Entry_Release/mobile/01-list-pending.png) | [보기](007_AI_Conversation_Entry_Release/mobile/02-body-pending.png) | [보기](007_AI_Conversation_Entry_Release/mobile/03-restored.png) | [보기](007_AI_Conversation_Entry_Release/mobile/04-unsaved.png) | [보기](007_AI_Conversation_Entry_Release/mobile/05-first-accepted.png) |

## 기존 데이터와 복구

실제 데이터 사본 기동과 운영 재기동 직후에 업무 18개·AI 17개 테이블의 기존 행을 대조했다. 브라우저 검증 후에도 기존 대화 13건, 작업 28건, 메시지 56건과 기존 감사·접근 기록은 모두 보존됐다. 시험 중 모델 목록 점검 시각과 작업 처리 순번이 갱신됐다. 시험 계정의 보관량 증가 759자는 두 대화의 입력·출력과 모델 인계 기록 등을 포함한 서비스의 보관량 계산과 일치했다. 로그인에 따른 세션 토큰 변경은 `test04` 한 계정이었다. 답변을 확인한 뒤 이번에 만든 대화 2건만 시험 계정의 휴지통으로 옮겼다. 웹·워커·보존 타이머는 정상이고 미완료 작업은 0건이었다. [사후 대조](007_AI_Conversation_Entry_Release/entry-preservation.json)

이전 커밋은 `dee0300aedcf5c39efc0c3c1ff409af1bc8313ab`이다. 이전 코드, 기동 설정, DB 일관 사본 등 9개 복구 파일의 SHA-256을 서버와 현재 PC의 사용자 전용 백업에서 확인했다. 서버에는 접수를 제한한 직후의 DB 사본도 보관했다. 복구가 필요하면 먼저 큐를 비운 뒤 이전 코드를 기동하고 DB 버전 4의 기존 대화와 새로 접수된 대화를 확인한다. 백업 식별자는 `20261105-ai-ux-entry-20261109T030719Z-2519ed`이다.
