---
artifact_id: TASK-20261104-002
work_id: IMPL-20261104-USER-AI-ASSISTANT
created_at: 2026-11-04
owner: Codex
mode: implementation
status: staging-verified-awaiting-approval
related_artifacts: [PLAN-20261104-002, REPORT-20261104-002]
---

# 장비관리 AI 도우미 개발 작업

사용자가 실제 기능 개발을 요청했다. 기존 계획의 장비관리 내부 큐·독립 UI·사용자별 대화 저장·일반 사용자 업무·삭제 차단을 승계하고, 추론 스트림의 접기/펼치기·최종 답변 시 자동 접힘, 모델이 지원하는 낮음/중간/높음 추론 선택, 서버가 강제하는 세션·도구 권한을 추가한다. 외부 서비스 요청이나 Strata 시험 화면을 제어하지 않는다.

- [x] 기록기·profile·governance validate·작업 context 확인. legacy 사유 runtime-session-mismatch.
- [x] 기존 앱·업무·배포·Strata 모델/API 계약 조사. 공개 health/UI와 공식 API 구현 근거 구분.
- [x] 구현 계획 및 구현 전 검증 1~8 순차 검토.
- [x] Staging에서 독립 대화 UI와 추론 표시/선택 구현.
- [x] 대화 저장·장비관리 내부 영구 큐·작업자·모델 스트림 구현.
- [x] 서버 세션/위임 검증·도구 허용 목록·변경 확인/중복 방지·계정 번호 재사용 차단 구현.
- [x] 일반 사용자 장비·카탈로그 신청·파일/CSV·개인 설정 연동. 특수 임시 카탈로그 복합 등록은 기존 수동 화면으로 한정.
- [x] Linux 합성 테스트 49개 및 Chromium 1440px/430px 화면 검사 29개 통과. 마지막 UI 표현 변경은 화면 검사만 재실행.
- [x] 통합·이관 가능한 후보, 배포/복귀 절차와 구현 후 1~8 검토·제약·해시 근거 정리.
- [ ] 사용자의 구체적 Staging 검증 결과 승인. legacy staging-merge 규칙에 따른 운영 병합 전 필수 조건.
- [ ] 승인 후 기존 변경 재대조→운영 소스 병합→Git→서버 pull→실제 앱/Strata 통합 확인→단계별 활성화.

운영 계정·DB 계약/영수증 성능·일관된 백업·실제 모델 도구 정확성 및 자체 요청 취소/복구는 미검증이다. 기존 운영 DB를 열거나 schema를 변경하지 않았다. 이 후보의 검증 완료를 운영 배포 완료로 표시하지 않는다.
