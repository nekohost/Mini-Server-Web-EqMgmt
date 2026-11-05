---
artifact_id: TASK-20261105-001
work_id: REVIEW-20261105-AI-UX-RETIREMENT
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 UX·대화 오류·Strata 시험 화면 폐기 검토

이번 요청은 원인 확인과 개선·폐기 계획이다. 운영 코드·메뉴·설정·대화는 변경하지 않는다.

- [x] recorder/profile/context/validate와 적용 노드를 확인한다.
- [x] 실제 업무/AI DB의 새 일관 백업을 로컬에 받고 해시를 확인한다.
- [x] nekohost의 '관리자 모델 기능 시험' 대화에서 지정 요청·실패 응답·job 원인을 확인한다.
- [x] 표 렌더러·모델명·메뉴 부모·관리자 비동기 UX·기존 Strata 의존성을 정적으로 대조한다.
- [x] 여섯 항목의 원인·수정 방향·이전/폐기 순서·검증/복구 계획을 작성한다.
- [x] Validation 1~8과 코드/운영 무변경 범위를 확인하고 보고한다.

검토 완료: 표 renderer 부재, 조회 status 빈값의 enum 불일치, 혼합 probe 문맥을 확인했다. Linux 순수 validator 네 경우로 교차 확인했다. 구현/폐기/배포는 실행하지 않았고 Plan의 상태는 proposed다.

추가사항 7 검토:

- [x] 현재 AI DB의 대화/종속 기록·보관 예산·실행 잠금 관계를 확인한다.
- [x] 휴지통·복구·30일 기산일 갱신·직접 영구삭제·주기 정리·동시성 계획을 기존 Plan에 추가한다.
- [x] 감사/실행 영수증/백업의 보존 범위를 구분하고 추가 Validation 1~8을 기록한다.

추가사항 7 검토 완료: 기존 private AI 백업은 immutable 읽기 전용으로 schema만 확인했다. Plan에 v4 추가 migration, 정상/휴지통 분리, 재이동 시 30일 갱신, 사용자 직접 영구삭제, 서버 timer, 최소 실행 점유 분리와 종속/원장 삭제, 감사/업무/백업 보존 경계를 반영했다. 세 문서의 구조/링크와 governance 검사를 확인했다. 실제 DB·앱·Staging·운영·timer는 변경하지 않았고 새 동작 테스트나 모델 호출도 수행하지 않았다.
