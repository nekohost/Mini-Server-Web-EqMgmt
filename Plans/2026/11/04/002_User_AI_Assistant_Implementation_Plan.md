---
artifact_id: PLAN-20261104-002
work_id: IMPL-20261104-USER-AI-ASSISTANT
created_at: 2026-11-04
owner: Codex
mode: implementation-plan
status: implemented-staging-awaiting-review-approval
related_artifacts: [TASK-20261104-002, REPORT-20261104-002]
---

# 장비관리 AI 도우미 구현 계획

사용자의 실제 개발 지시와 [이전 설계](001_User_AI_API_Conversation_and_Queue_Plan.md)를 승계한다. 장비관리 내부 요청만 순차 처리하고 Strata 시험 UI와 별도로 `/assistant`를 작성한다. 일반 질문은 모델이 답하고 업무 실행은 일반 사용자에게 허용된 장비관리 기능만 제공한다. 삭제·관리자 도구·임의 코드/파일/네트워크 실행은 제공하지 않는다.

## 화면과 모델 계약

- 대화 목록·새 대화·이어보기, 질문 입력, 추론 선택, 상태·취소, 확인 카드·업무 결과를 신규 템플릿/Vanilla JS/CSS로 작성한다. 기존 Strata HTML/vendor/iframe/bridge는 사용하지 않는다.
- `reasoning_content` 조각은 접기 가능한 별도 영역에 실시간 표시한다. 답변이 시작될 때 한 번만 자동으로 닫고 사용자의 재열기/접기 선택을 후속 polling에서 덮어쓰지 않는다. 최종 답변과 추론은 별도로 저장하고 추론을 다음 프롬프트에 재주입하거나 도구 인자로 해석하지 않는다.
- 현재 health에서 `qwen3.8-flash-next-iq3_xxs`, 196608 context, loaded=true를 읽기 전용으로 확인했다. 현재 Strata 공개 UI는 none/low/medium/high 선택과 `reasoning_content`를 사용한다. 공식 frontend는 none/low/medium/xhigh를 지원하며 high는 xhigh 별칭이다.
- 요청한 간단한 3단계 UI는 `낮은 추론(추론 없음)`→`none`, `중간 추론`→`medium`, `높은 추론`→`xhigh`로 제한한다. 기본값은 medium. 모델/URL/도구/임의 파라미터는 사용자 입력으로 받지 않는다. 모델이 보내지 않은 추론을 만들어 표시하지 않는다.

## 서버 경계

- Flask의 서명된 로그인 cookie와 현재 users.SessionToken/활성 상태/역할/메뉴를 다시 검증한다. 암호화 자체가 인가를 대체하지 않는다. 브라우저에는 서명 비밀·Strata key·worker key를 전달하지 않는다.
- 대화·작업의 소유권은 UserId와 서버 CreatedAt으로 만든 계정 식별정보를 함께 확인한다. 복원 후 번호 재사용으로 이전 계정의 기록이 노출되는 것을 차단하며, 로그인 이름 변경은 기록을 유지한다. 생성 정보가 없는 계정은 명시적으로 접근을 거절하고 운영 DB를 자동 보정하지 않는다.
- 작업에는 로그인 토큰의 서버 HMAC과 절대 만료를 결합한다. 변경 전/도구 실행마다 현재 계정과 비교한다. 자동 상태 조회는 공통 타이머와 cookie 재발급에서 제외한다. 기존 화면의 세션 연장 동작은 보존한다.
- 독립 worker는 장비관리 내부 인증 API로 claim/이벤트/step 완료를 보고한다. 브라우저 세션이나 app.py를 worker로 가져가지 않는다. 긴 Strata SSE는 worker가 소비하고 웹 요청은 짧게 처리한다.
- 시스템 프롬프트는 도구 범위·확인·비신뢰 자료 취급을 설명한다. 실제 방어는 서버 도구 allowlist/엄격한 인자 schema/소유권/메뉴/현재 revision/CSRF/Origin/확인으로 수행한다. 관리자 계정도 이 UI에서는 일반 사용자 범위의 본인 업무만 수행한다.
- worker 도구는 조회/변경 제안만 가능하다. 실제 commit은 본인 브라우저의 CSRF 보호 확인 endpoint만 허용하며 worker key로 확인할 수 없다.

## 저장·큐·확정

- 별도 SQLite AI DB에 대화·메시지·job·도구 문맥·불변 proposal을 저장한다. owner 조건과 cursor/크기/횟수 제한을 적용하고 생성 중 transaction을 열지 않는다.
- 장비관리 발신 active 요청 최대 1개, 사용자 열린 턴 제한, step 완료 후 큐 뒤로 재진입, 확인/입력 대기 중 내부 점유 해제. 다른 서비스의 Strata 요청은 관리하지 않는다.
- worker lease가 오래됐다고 자동 재전송하지 않는다. 자체 요청이 불명확하면 recovery_required로 남겨 중복 전송을 차단한다. 운영자가 자체 요청 종료를 확인한 뒤 내부 작업만 해제하는 복구 경로를 둔다. 공유 Strata stop/unload/restart·전체 idle 대기는 구현하지 않는다.
- 업무 DB schema를 이번 후보에서 변경하지 않는다. 기존 audit_logs의 전용 AI 실행 영수증을 BEGIN IMMEDIATE 안에서 먼저 조회하고 업무 변경/감사/영수증을 같은 transaction에 저장하여 재전송을 방지한다. proposal의 전체 ID·내용 hash·actor를 함께 비교하고 AI DB 상태 반영이 실패해도 영수증으로 결과를 복구한다. 이는 초기 v4 별도 receipt 테이블 제안의 대안이며 실제 계약 확인 없이 운영 DB migration을 하지 않기 위한 선택이다.
- 장비 등록/수정은 승인 옵션 또는 본인에게 허용된 임시저장 옵션, 입력 validator·날짜·시리얼·revision·감사를 적용한다. 상태/카탈로그 신청/옵션 신청/CSV/개인 설정은 기존 서비스를 재사용한다. 파일 작업은 본인 UI에서 고른 파일과 기존 업로드/다운로드 경계를 사용하며 임의 경로/OCR/외부 URL 취득 도구를 제공하지 않는다.

## 산출물과 검증

후보는 `Staging/20261104-user-ai-assistant/overlay/`에 package·템플릿·JS/CSS·테스트를 작성한다. root app/session_timer integration은 검토 가능한 patch로 제공하고 기존 사용자 변경은 보존한다. 기술 주석은 EN revision으로 추적하며 별도 Gemini KO 감사가 끝났다고 주장하지 않는다.

검증은 1~8단계 설계 검토 후 Python AST/JS 구문·모듈 계약/도구 인자·route 충돌·보안·변경 범위의 정적 점검을 수행한다. Linux용 합성 DB/가짜 모델/브라우저 테스트를 작성한다. 프로젝트의 표준 절차는 정적 Staging 결과에 대한 사용자 승인 후 운영 소스 병합→Git→Linux 격리 검증→서비스 반영이다. 이번 지시를 아직 작성하지 않은 검증 결과에 대한 사전 승인으로 확대하지 않는다. 운영 DB 조회·schema 변경·서비스 재시작은 실행하지 않는다.

실제 모델 검증 시에도 장비관리의 짧은 합성 요청만 사용하고 다른 클라이언트의 요청을 끊거나 설정을 바꾸지 않는다. API key/요청 원문을 로그에 노출하지 않는다. 설치본 API/취소 동작과 모델의 도구 정확성은 실제 검증 전 미확인으로 보고한다.

공식 기술 근거: [Strata frontend](https://github.com/Niko1221/Strata/blob/main/serve/frontend.py). 읽기 전용 현장 확인: 백업 Linux 서버를 통한 `/health`, `/`, `/web/app.js`; `/props`는 401로 응답해 인증을 우회하지 않았다.

## 구현 결과의 현재 상태

후보 구현과 구현 전 1~8 검토 및 구현 후 1~8 검토를 완료했다. Linux 합성 테스트 49개와 Chromium 데스크톱/430px 모바일 화면 검사 29개를 통과했다. 처리 결과·CSV 미리보기의 사용자용 표현을 보강한 마지막 수정은 화면 검사만 재실행했으며 기존 Python 업무 코드는 바뀌지 않았다. 상세 결과·제약·승인 후 순서는 관련 Report에 기록한다. 운영 루트·Git·서버 설정·운영 DB는 변경하지 않았고, 실제 모델 생성·운영 통합·서비스 활성화는 검증 결과 승인 이후의 잔여 작업이다. 기존 사용자 수정 9개와 기존 앱/Strata 파일 4개의 기준 hash를 보존한다.
