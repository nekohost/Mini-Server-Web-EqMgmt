---
artifact_id: PLAN-20261104-011
work_id: FIX-20261104-AI-UI-REASONING-SETTINGS
owner: Codex
created_at: 2026-11-04
status: completed-staging
---

# AI 화면 보완 구현 계획

현재 후보 `Staging/20261104-user-ai-assistant/overlay`를 보완한다. 기존 010 캡처·검토 원장은 변경하지 않고 수정 후 결과는 011 경로에 추가한다.

관리자 화면의 배경·카드·입력란·버튼 배경을 그대로 유지하고 dark에서 제목/항목명/설명 글자색만 대비가 충분한 값으로 지정한다. 흰 입력란/버튼의 글자색은 별도로 어두운 값을 유지한다. 모바일 하단 안내문은 12px로 올리고 줄바꿈과 입력 영역을 다시 확인한다.

사용자 드롭다운의 공통 표시값은 off, low, medium, high, xhigh, max다. 지원되지 않거나 관리자가 허용하지 않은 단계는 삭제하지 않고 disabled로 표시한다. 추론 API를 제공하지 않는 모델은 별도의 모델 기본값 상태를 사용하며 off라고 오인시키지 않는다. 같은 단계 명칭을 답변 출처에도 사용한다.

모델별 추론 설정은 기존 AI 모델 profile JSON에 보관하고 관리자 모델 카드에 허용 단계와 기본값을 제공한다. 알려진 모델의 지원 상한과 관리자 허용값을 서버에서도 검증한다. 미확인 모델은 관리자 설정/기능 시험을 통해 확인한 단계만 사용한다. Qwen3.8 Flash Next는 공식 자료와 기존 Strata 계약을 근거로 off/low/medium/xhigh를 사전 설정하고 high/max를 비활성으로 두며 기본값은 medium을 유지한다. off는 Strata 전송에서 기존 none 계약을 유지한다. 일반 OpenAI 호환의 미지원 모델에 추론 파라미터를 강제하지 않는다.

기존 low→none / high→xhigh 별칭은 새 표준 low/high와 뜻이 다르다. profile 버전과 기존 route_snapshot을 구분해 기존 대화의 다음 선택만 off/xhigh로 이전하고 과거 메시지·job.level·접수된 route·probe 의미는 보존한다. 기존 JSON/행을 삭제하거나 실제 운영 DB를 이전하지 않는다. 관리자 변경 뒤 새 요청과 기능 시험의 revision 충돌을 검증한다.

정적 Python/JS 검사와 승인된 Linux의 합성 backend/browser fixture를 수행한다. 의미가 바뀌는 기존 수준 기대값은 새 계약으로 수정하되 기존 권한·감사·멱등·큐·오류·보관 회귀는 유지한다. 수정 화면의 desktop/mobile·light/dark 및 드롭다운 disabled/관리자 제어를 캡처하고 010 배경색과 비교한다. 실제 두 Strata PC나 타 서비스에 생성·설정 변경을 보내지 않는다.

완료: backend 112/browser 93 통과, 새 PNG 18장과 배경/색 대비·글자 크기·표준 항목 상태를 보존했다. 기존 작업 별칭 및 최초 registry 이전과 신형 모델 기본값을 구분했다. 최종 결과와 검증 경계는 같은 work_id의 011 Report와 화면 원장에 기록했다. 운영 배포는 수행하지 않았다.
