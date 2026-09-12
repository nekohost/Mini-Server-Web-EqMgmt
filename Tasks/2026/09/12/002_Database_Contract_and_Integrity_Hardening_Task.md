---
artifact_id: TASK-20260912-002
work_id: WORK-20260912-DATABASE-CONTRACT-INTEGRITY-HARDENING
created_at: 2026-09-12T14:20:40.995+09:00
related_artifacts:
  - ../../../../Plans/2026/09/12/001_Database_Contract_and_Integrity_Hardening_Plan.md
  - ../../../../Reports/2026/09/12/002_Database_Contract_and_Integrity_Hardening_Review_Report.md
---

# 데이터베이스 계약 및 무결성 강화 Task

- 상태: 구현·검증·commit·push 및 백업 서버 적용 완료 / 주 서버 SSH 인증 불가
- 범위 제외: 관리자가 승인한 `access_logs` 운영 정책

## 기준선과 설계

- [x] 중단된 5개 기능 릴리스와 로드맵 계획 Task를 확인하고 현재 서버 HEAD에 로컬 fast-forward
- [x] 연결·삭제·호환성 변경 전 Validation 1~8 재검토 및 Staging 소스 복사

- [x] 운영 적용 전 백업·해시·무결성·migration 기준선 자동 기록
- [x] 선언 FK와 코드 기반 논리 참조의 고아 검사 정의
- [x] 목표 스키마 버전과 canonical schema 계약 정의
- [x] 신규 DB와 역사 DB의 의미 기반 호환성 규칙 정의

## 구현

- [x] 정상 DB 연결의 `foreign_keys=ON` 적용 및 활성화 검증
- [x] migration·백업·복구용 연결 초기화 계약 분리
- [x] 카테고리·제조사 단건·일괄 삭제의 NOT NULL 위반 로직 제거
- [x] 참조가 있는 마스터 삭제 차단과 참조 건수 응답 구현
- [x] 충돌 검사와 원자적 rollback을 갖춘 마스터 병합 구현 여부 확정 및 구현
- [x] `PRAGMA user_version`과 `sys_migrations` 동기화
- [x] 백업 호환성 검사를 의미 기반 스키마 비교로 전환
- [x] `equipment` 참조 목록화와 1차 사용 중단 처리
- [x] 1차 레거시 DROP 제외와 v1 DB의 역사 재변환 차단, 별도 rollback_contract 구현
- [x] 측정 결과가 유효한 후보 인덱스만 migration에 추가

## 검증과 배포

- [x] 빈 DB·역사 DB·운영 복제 DB migration 및 멱등성 시험
- [x] CRUD·노드·옵션·장비 삭제·감사 보존·승인·사용자 기능 회귀 시험
- [x] 마스터 삭제 차단·병합 성공·충돌·rollback 시험
- [x] 신규 DB와 역사 DB의 백업·복원 교차 시험
- [x] 인덱스 전후 query plan·지연·쓰기 비용 비교
- [x] staging migration 및 rollback 리허설 보고서 작성
- [x] 운영 점검 모드에서 백업 후 migration 적용
- [x] 운영 무결성 검사와 핵심 기능 smoke test
- [x] 구현 결과 commit 및 원격 저장소 push


## 완료 근거

- Linux 회귀 55/55, Node 회귀 23/23, 거버넌스 회귀 54/54 통과.
- 실제 DB 사본의 기동·행 보존·버전 down/up·신규 DB 교차 호환성 통과.
- 백업 서버 실제 DB version=1, integrity=ok, FK 위반 0. 서비스 PID 48811, 점검 NORMAL.
- 주 서버 192.168.0.166 적용은 현재 키의 SSH 인증 거절로 미완료다. 위 운영 적용 체크는 사용자 지정 백업 서버에 해당한다.
- 최종 보고서: ../../../../Reports/2026/09/12/003_Database_Contract_Production_Release_Report.md
