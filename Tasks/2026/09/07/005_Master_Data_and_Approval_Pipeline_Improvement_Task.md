# [작업 관리 대장] 마스터 데이터 조회 정합성 복구 및 전자결재 연동 파이프라인 구축

작성일: 2026-09-08  
상태: 운영 소스 반영 및 정적 재검증 완료  
관련 계획서: `Plans/2026/09/07/004_Master_Data_and_Approval_Pipeline_Improvement_Plan.md`  
관련 검증 보고서: `Reports/2026/09/07/011_Master_Data_and_Approval_Pipeline_Improvement_Plan_Validation_Report.md`  
Staging 검증 보고서: `Reports/2026/09/08/005_Master_Data_and_Approval_Pipeline_Improvement_Staging_Validation_Report.md`  
운영 반영 보고서: `Reports/2026/09/08/006_Master_Data_and_Approval_Pipeline_Production_Promotion_Report.md`  

---

## 작업 개요 및 원칙
- **작업 환경**: `Staging/` 디렉토리 내부에서만 수정 작업 수행. 운영 코드는 일절 직접 수정하지 않음.
- **작업 순서**: 단계별 순차 구현 및 정적 검증 수행 완료.

---

## 작업 목록

- [x] **Task 1: Staging 환경 파일 복사 및 준비**
  - 운영 소스(`app.py`, `templates/master_management.html`, `templates/index.html`)를 `Staging/` 경로로 복사 완료
  - 기준점 동기화 확인 완료

- [x] **Task 2: 마스터 데이터 관리 API 스키마 정합성 복구 (`Staging/app.py`)**
  - `get_or_create_master_management_item()`의 GET 쿼리에서 `c.id` -> `c.CategoryId`, `m.id` -> `m.ManufacturerId` 정정 완료
  - `LEFT JOIN lineup_nodes` 조인 조건 수정 완료
  - `try-except` 예외 쉴드 보강 완료

- [x] **Task 3: 마스터 관리 및 장비 등록 화면 캐시 실시간 동기화**
  - `Staging/templates/master_management.html`: 추가/수정/통폐합/삭제 성공 시 `sessionStorage.removeItem('nodeCache_v2')` 호출 함수(`invalidateNodeCache`) 추가 완료
  - `Staging/templates/index.html`: 장비 등록 모달 진입 시 최신 카탈로그 트리를 강제 갱신(`await window.LineupApp.init(true)`) 적용 완료

- [x] **Task 4: 장비 등록 화면 '기타' 입력 UI 잠금 해제 및 전환 (`Staging/templates/index.html`)**
  - `CategorySelect` 또는 `ManufacturerSelect`에서 `__custom__` 선택 시 [저장하기] 잠금 해제 완료
  - 버튼 텍스트를 [신규 분류 승인 요청 및 임시등록]으로 전환 완료
  - 안내 문구 및 입력 유효성 실시간 검증(`oninput`) 연결 완료

- [x] **Task 5: '기타' 입력 시 전자결재 상신 및 임시 장비 저장 파이프라인 (`Staging/app.py`)**
  - `add_equipment()`: `RootData`의 커스텀 분류 감지 시:
    1) `categories` / `manufacturers`에 `IsApproved = 0` (미승인) 삽입/조회
    2) 해당 분류 하위에 임시 노드/옵션 (`status = 'PENDING'`) 연계 생성
    3) `approval_requests`에 결재 상신 레코드 적재 (`ADD_CATEGORY`, `ADD_MANUFACTURER`)
    4) 장비는 `is_draft = 1`로 임시 등록
  - `process_approval()`: 관리자 승인 시 `lineup_nodes`, `equipment_options`, `equipments.is_draft` 일괄 활성화 동기화 완료
  - 관리자 반려 시 대체 명칭 업데이트 또는 미승인 데이터 정리 완료

- [x] **Task 6: 정적 논리 검증 및 시뮬레이션 테스트**
  - Node.js 기반 JS 구문 검사 (2개 템플릿 인라인 스크립트 전원 통과)
  - `git diff --check` 공백 오류 점검 및 trailing whitespace 정리 완료
  - `governance-tool.mjs validate` 통과 확인 완료

- [x] **Task 7: Staging 구현 검증 보고서 작성 및 사용자 보고**
  - `Reports/2026/09/08/005_Master_Data_and_Approval_Pipeline_Improvement_Staging_Validation_Report.md` 작성
  - `Reports/2026/09/08/007_Master_Data_and_Approval_Pipeline_Staging_Review_Report.md` 작성 (사용자 검토 요청 대응)

- [x] **Task 8: 운영 원본 파일 백업**
  - 배포 전 `app.py`, `templates/index.html`, `templates/master_management.html`을 `Backups/2026-09-08_pre_master_approval/`에 안전하게 백업 완료
  - SHA256 해시 검증 및 디렉터리 격리 보존 확인

- [x] **Task 9: Staging 소스를 Production 운영 위치로 병합**
  - `Staging/app.py` -> `app.py` 복사 및 병합 완료
  - `Staging/templates/index.html` -> `templates/index.html` 복사 및 병합 완료
  - `Staging/templates/master_management.html` -> `templates/master_management.html` 복사 및 병합 완료

- [x] **Task 10: 운영 소스 정적 재검증**
  - 정규 파서 기반 `node .agent-governance/tooling/governance-tool.mjs validate` 통과 완료 (40노드 0에러 0경고, status: pass)
  - Staging과 Production 파일 간 SHA256 해시 100% 일치 확인
  - HTML 인라인 스크립트 정적 구문 무결성 확인
  - `git diff`를 통한 변경 내용 및 안정성 최종 점검

- [x] **Task 11: Staging 작업 파일 정리**
  - 병합 완료된 `Staging/app.py`, `Staging/templates/index.html`, `Staging/templates/master_management.html` 정리 완료 (`workflow.staging-merge` 준수)

- [x] **Task 12: 운영 반영 완료 보고서 작성 및 사용자 보고**
  - `Reports/2026/09/08/006_Master_Data_and_Approval_Pipeline_Production_Promotion_Report.md` 작성 완료

