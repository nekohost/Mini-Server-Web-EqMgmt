---
artifact_id: PLAN-20261123-002
work_id: PLAN-20261123-AI-CONTEXT-TOKEN-CALIBRATION
owner: Gemini
status: planned-deferred
approval: plan-only-no-implementation
---

# [항목 4 보류 계획] AI 모델 UTF-8 바이트 대 토큰 추정치 보정 및 `context_tokens` 상향

> [!NOTE]
> 본 문서는 사용자 지시에 따라 **계획으로만 수립하며 현재 구현하지 않습니다.**
> 항목 1·2·3의 Staging 구현 및 검증과 독립적으로 보관되며, 실제 `260Strata` 실측 및 관리자 검증 근거 확보 전에는 코드·설정·DB의 추정식이나 `context_tokens`를 변경하지 않습니다.

## 1. 현황 및 문제 배경

1. **현행 보수적 추정 방식:**
   - [utils/ai_assistant/__init__.py](../../../utils/ai_assistant/__init__.py)와 [utils/ai_assistant/context.py](../../../utils/ai_assistant/context.py)는 `len(canonical(...).encode())`(UTF-8 바이트 수)를 `route['context_tokens']`와 **1:1**로 비교합니다.
   - 한국어 UTF-8은 1글자당 3바이트(JSON escape 시 최대 6바이트)이므로 실제 BPE/SentencePiece 토큰 수(대략 한국어 1글자 ≈ 0.7~1.5토큰, 영문 3~4바이트 ≈ 1토큰) 대비 **약 2~3배 과대 계상**되는 보수적 경계를 가집니다.
2. **운영 모델 설정 현황:**
   - 백업 서버(`nkhst-pentium`) DB 조회 기준 `260Strata`의 공개 모델 3종(`gemma-4-26b-a4b-qat-ud-q4_k_xl`, `gemma-4-26b-a4b-ud-q4_k_m`, `Qwen3.8 Flash Next`)의 `context_tokens`가 모두 `65,536`으로 등록되어 있습니다.
   - `CONTEXT_LIMIT` 안내 문구가 "더 큰 모델을 선택해 주세요"라고 안내하더라도, 현재 공개 모델 간 `context_tokens`가 모두 동일해 모델 전환만으로는 문맥 용량을 키울 수 없습니다.

## 2. 왜 즉시 구현하지 않고 별도 선행 조건을 두는가

- 실제 `260Strata`(`http://192.168.0.14:8080`)가 각 모델별로 서빙 중인 실제 `n_ctx`와 KV 캐시 한도 확인 없이 `context_tokens`를 임의로 높이거나 바이트 추정 배수를 완화하면, 앱 서버 pre-dispatch 검사는 통과했으나 upstream llama.cpp/Strata가 HTTP 400/413(`UPSTREAM_REJECTED`)으로 거절하거나 추론 지연/VRAM 부족을 유발할 위험이 있습니다.
- `test_provider_ca.py:602` 등 기존 보안/프로브 테스트는 `4,096` 토큰 후보가 일반 대화 문맥 예산(보수적 바이트 기준)을 수용하지 못할 때 `PROVIDER_CONTEXT`로 차단하는 계약을 검증합니다.

## 3. 향후 착수 시 선행 조건 및 실행 단계

1. **실서버(`260Strata`) 서빙 스펙 실측 (읽기 전용):**
   - 각 공개 모델의 실제 서빙 `n_ctx` 및 `max_model_len`을 확인하고, 관리자 화면(`/admin/ai/providers`)의 모델별 `context_tokens` 검증값과 일치시킵니다.
   - `260Strata`가 실제 `131,072` 이상을 지원하는 모델이 있다면 관리자 기능 시험을 거쳐 해당 모델의 `context_tokens`만 상향합니다.
2. **토크나이저별 최악 바이트/토큰 비율 벤치마크:**
   - Gemma 4 계열 및 Qwen3.8 계열 모델에 대해 한국어 산문, 영문 메일, JSON 도구 스키마, 코드 블록, 이모지·특수문자 혼합 입력의 실제 `prompt_tokens` 대비 `utf8_bytes` 비율을 측정합니다.
   - 상한 초과가 절대 발생하지 않는 안전 계수(예: UTF-8 한국어/CJK 바이트 가중치 vs ASCII 바이트 가중치 분리 또는 모델 패밀리별 보수 상한)를 도출하고, 기존 `test_provider_ca.py`의 `4,096` 경계 테스트와 호환되는지 검토합니다.
3. **Upstream 문맥 초과(`400/413`)와 일반 `UPSTREAM_REJECTED` 세분화 검토:**
   - 추정 완화 후 발생할 수 있는 upstream 실제 `context length exceeded` 응답을 `CONTEXT_LIMIT`로 안전 매핑하는 방안을 설계합니다(응답 본문 원문 비노출 원칙 유지).
4. **롤백 기준:**
   - 추정식 변경으로 upstream 400/413 거절률이 증가하면 `policy.py`/`context.py`의 추정 계수만 즉시 `1 byte = 1 token` 기준선으로 되돌릴 수 있도록 단일 헬퍼 함수로 격리 구현합니다.
