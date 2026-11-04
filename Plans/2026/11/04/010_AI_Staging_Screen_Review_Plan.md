---
artifact_id: PLAN-20261104-010
work_id: REVIEW-20261104-AI-STAGING-SCREENS
owner: Codex
created_at: 2026-11-04
status: completed
---

# AI Staging 샘플 화면 검토 계획

대상은 009 다중 프로바이더 후보의 `equipment_ai.html/js/css`, `equipment_ai_providers.html/js/css`와 실제 현재 공통 frame/static이다. 화면의 모양을 새로 그리지 않고 이 원문을 렌더링한다. API 응답만 명확한 합성 샘플로 고정해 개인 데이터·키·실모델을 사용하지 않는다.

사용자 기본 화면, 추론 진행, 최종 답변/등록 확인 카드, 모델 변경 후 출처 유지, 종료 확인 필요 안내와 관리자 신규 연결·기존 연결·모델 설정을 캡처한다. 데스크톱 1440×1000, 모바일 390×844를 기본으로 light/dark를 나누어 총 16개 장면을 구성한다. 모바일은 실제 child viewport 또는 동등한 device metrics를 사용하고 캡처 방식/크기를 기록한다. 필요하면 문제 확인을 위한 추가 장면만 생성한다.

기존 Linux fixture 경로처럼 후보 소스를 SSH stdin으로 전송하고 임시 loopback Flask/Chromium에서 렌더링한다. Windows에서 Staging 앱을 실행하지 않는다. 로컬 Tailwind fallback을 사용해 CDN 부재가 앱 결함으로 오인되지 않게 하고, 원본 UI에 디자인 보정 CSS를 덧붙이지 않는다. 샘플 설명은 별도 갤러리/보고서에 두며 화면 자체를 고쳐 찍지 않는다.

`Reports/2026/11/04/010_AI_Staging_Screens/`에 PNG와 manifest/갤러리를 보존하고 010 Report에서 발견 사항을 화면·재현 조건·증거·영향·개선 방향으로 연결한다. 생성 파일은 신규 경로에 한정하고 출처와 SHA를 기록한다. 화면 문제가 발견되면 관찰을 먼저 보고하며 구현 수정은 이번 검토에 포함하지 않는다.

완료: 기본 16장과 확인 카드 상세 2장을 남겼다. desktop/mobile 모두 명시적 child viewport로 고정했으며 모바일 PNG의 바깥 회색 여백을 기록했다. 18장 시각 검토와 원문/PNG hash 대조를 수행하고 결함 2건·개선 권고 1건을 010 Report에 연결했다. 후보/운영 소스와 이전 009 원장은 보존하며 UI 수정은 수행하지 않았다.
