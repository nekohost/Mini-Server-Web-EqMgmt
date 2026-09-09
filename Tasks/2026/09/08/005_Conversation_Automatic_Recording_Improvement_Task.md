# [Task] 대화 자동 기록 파이프라인 개선 계획

## 목적

AI의 작업 기억에 의존하는 현행 Chat 저장 절차를 모델 턴 밖의 단일 기록기, 플랫폼 어댑터, 내구성 있는 cursor와 검증 gate를 갖춘 자동 기록 파이프라인으로 바꾸기 위한 구현 계획을 확정한다.

## 이번 요청 범위

- [x] 현행 Rule 제6장과 자동 기록 누락 분석 결과 대조
- [x] context 로더의 실제 기본 노드 선택 방식 확인
- [x] Codex·Antigravity·Claude capability와 세 진입점 확인
- [x] 모델 턴 종료 이후 final 기록이 가능한 실행 구조 설계
- [x] 중복 방지, 동시성, 시각, UTF-8, 비밀 치환과 복구 절차 설계
- [x] Rule·노드·router·manifest·traceability 동기화 범위 식별
- [x] 구현 순서, 시험표, 수용 기준과 롤백 계획 작성
- [x] Validation 1~8 순차 검토 및 보고서 작성
- [x] 하위 에이전트 이력의 제외 사유 재검토와 작업 receipt·companion 공개 범위 설계
- [x] Windows `fs.watch`와 1.5초 stat 폴링 병행 권고 반영
- [x] Antigravity `brain\<conversation-id>` 탐색·workspace 연동 설계 반영
- [x] Codex·Antigravity 우선, Claude 후속 활성화 순서 반영
- [x] 수정 계획 Validation 1~8 재검증

## 후속 구현 Task

- [ ] 현재 Rule hash 재확인과 전용 Staging 후보 생성
- [ ] Codex·Antigravity 비식별 fixture와 capability probe 작성
- [ ] 어댑터·정규화·필터·비밀 치환 구현
- [ ] provenance·단일 writer·원자적 저장·cursor·receipt 구현
- [ ] watcher와 `ensure`·`reconcile`·`verify`·`status`, Windows stat 폴링 구현
- [ ] 하위 에이전트 작업 receipt와 companion 기록 구현
- [ ] `Staging/Rule.md`와 실행 노드·router·진입점·capability 동기화
- [ ] fixture, 강제 종료, 동시성, 날짜 전환과 보안 시험 수행
- [ ] shadow 기록으로 원본 대비 누락·중복 0건 확인
- [ ] Staging 구현·검증 보고서 제출
- [ ] 별도 승인 후 운영 루트 병합 및 초기 3턴 감시
- [ ] 1차 버전 안정화 후 Claude 어댑터를 별도 Staging Task로 확장

## 변경 제한

이번 Task에서는 계획·검증 문서만 작성한다. `Rule.md`, 활성 거버넌스 노드, 라우터, 진입점, Chat 자동 writer와 애플리케이션 코드는 변경하지 않는다.
