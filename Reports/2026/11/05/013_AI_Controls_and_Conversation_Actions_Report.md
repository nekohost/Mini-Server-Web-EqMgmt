---
artifact_id: REPORT-20261105-013
work_id: PLANNED-20261105-AI-CONTROLS-ACTIONS
owner: Codex
status: completed-plan-registration
implementation_status: not-started
---

# AI 도우미 후속4건 미실현 계획 등록 검토

recorder ensure 성공(watcher11268), profile legacy/runtime-session-mismatch(verified=false), governance1.8.1 validate 오류0/경고0 및 context27개 선택을 확인했다. 직전에 읽은 변경 없는 공통/검증 노드를 승계하고 제안/계획 원장과 관련 소스를 읽기 전용으로 확인했다.

현재 summary는 추론 아래에 있고 휴지통 이동은 텍스트 버튼이며 sidebar footer에 제거 대상 두 문구가 있다. title 컬럼과 첫 메시지 자동 제목은 있지만 별도 이름 변경 API는 관련 route/store에서 확인되지 않았다. 버튼 추가와 함께 본인 권한/CSRF·수동 제목 보존을 향후 구현 범위로 기록했다.

## 계획 Validation1~8

1. 거버넌스: 계획013·등록 Task/검토 및 PROPOSALS/UNIMPLEMENTED_PROPOSALS만 수정한다. Staging·운영 코드/서버/DB와 기존011·다른 dirty 기록은 보존한다.
2. 의도: 우측 summary/조건부2줄, 두 위치의 빨간 휴지통, 왼쪽 이름 변경/tooltip, 하단 두 문구 제거를 모두 기록했다. 향후 위치 요구와 과거010 완료 이력을 구분했다.
3. 논리: summary/펼친 본문의 배치를 분리하고 실제 높이·상태 보존을 검증 조건으로 뒀다. 이름 변경은 UI 장식만으로 완료할 수 없으며 현재 자동 제목 조건과의 충돌도 검토한다.
4. 운영 영향:011 색상과 조율하고 rename API/데이터 상태 필요성은 추후 결정한다. 이번 문서 등록의 코드 실행 영향은 없다.
5. 보안: 본인 대화/현재 권한·Origin/CSRF·입력 제한/안전한 텍스트·감사 정책을 명세했다. 휴지통 아이콘화가 삭제 권한을 확대하지 않는다.
6. 복구: 문서 가산 기록만 수행하며 소스/DB rollback은 해당 없다. 기존 본문·미실현011과 운영 이력을 보존한다.
7. UX: tooltip/접근 가능한 이름·단색 기호의 테마 색상·모바일 조작·겹침·초안 유지·취소/실패·재자동명명 방지를 검증 기준으로 남겼다.
8. 메타: **계획 등록 완료 / 구현 미착수**를 구분한다. 기능 테스트/스크린샷·서버 반영을 실행한 것으로 집계하지 않는다.

대상은 [계획013](../../../../Plans/2026/11/05/013_AI_Controls_and_Conversation_Actions_Plan.md),[등록 Task](../../../../Tasks/2026/11/05/013_AI_Controls_and_Conversation_Actions_Task.md),[제안 원장](../../../../PROPOSALS.md),[미구현 목록](../../../../UNIMPLEMENTED_PROPOSALS.md)이다. 소스/011 해시 보존과 링크/네 요구사항 대조로 문서 범위를 검증한다.

등록 검증 결과: 네 요구사항 모두 존재, 신규 항목은 각 원장에1개씩 존재, 두 원장의 기존 본문 보존 및 새 문서7개 링크 확인을 통과했다. 현행 template/JS/CSS·AI API/store·app와 기존011, 총7개 참고 파일은 변경 전 SHA와 동일하다. 기능 코드/DB·Staging 변경, 테스트 실행·서버 배포는 수행하지 않았다.
