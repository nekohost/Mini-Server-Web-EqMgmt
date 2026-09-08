# [Task] 대화 자동 기록 파이프라인 전체 구현

- 승인 근거: 2026-09-08 사용자 지시 “계획서 … 이대로 진행하십시오.”
- 기준 계획: `Plans/2026-09-08_Conversation_Automatic_Recording_Improvement_Plan.md`
- 기준 Rule SHA-256: `CF8428BFDC14058B2D2BFE934751514DCA0D3E2655A9274D9AF40F043535F79E`
- 작업 모드: Staging 구현·정적 검증·승인된 운영 병합

## 순차 작업

1. [x] 활성 거버넌스 validate·sync-status와 변경 전 Rule hash 확인
2. [x] Rule·human map 및 플랫폼별 실제 원본 구조 읽기
3. [x] Staging 기록기 core, Codex·Antigravity 어댑터, Claude 미지원 probe 구현
4. [x] Windows `fs.watch`와 1.5초 stat 폴링, 단일 writer·cursor·receipt 구현
5. [x] 하위 에이전트 작업 receipt와 companion 기록 구현
6. [x] 비식별 fixture와 정상·중복·강제 종료·날짜·인코딩·비밀 치환 시험 구현
7. [x] `Staging/Rule.md`와 거버넌스 후보 노드·라우터·진입점·capability 작성
8. [x] Staging 정적 검증 및 Validation 1~8 수행
9. [x] Rule·노드·map·baseline·manifest·진입점·도구를 운영 루트에 같은 버전으로 병합
10. [x] 운영 거버넌스 validate·sync-status와 기록기 시험 재실행
11. [x] 실제 원본 dry-run·초기 reconcile·status 확인
12. [x] 전용 Staging 후보 정리 및 구현 보고서 제출

## 보존·제한

- 기존 Chat 원문과 헤더를 삭제하거나 수정하지 않는다.
- `app.py`, DB, Flask·Gunicorn·Linux 서비스는 변경하지 않는다.
- Codex와 Antigravity를 1차 활성 범위로 한다.
- Claude는 원본 capability가 검증될 때까지 `unsupported`로 유지한다.
- Git commit·push는 이번 지시에 포함되지 않는다.
