# [운영 소스 반영 완료 보고서] 마스터 데이터 정합성 복구 및 전자결재 연동 파이프라인

작성일: 2026-09-08  
작성자: AI Agent (Antigravity)  
작업 모드: 운영 반영 (Production Promotion)  
관련 계획서: `Plans/2026-09-07_Master_Data_and_Approval_Pipeline_Improvement_Plan.md`  
관련 작업 대장: `Plans/2026-09-07_Master_Data_and_Approval_Pipeline_Improvement_Task.md`  
관련 Staging 검증 보고서: `Report/2026-09-08_Master_Data_and_Approval_Pipeline_Staging_Review_Report.md`  

---

## 1. 개요 및 배경

사용자의 명시적 운영 반영 지시("이해는 했습니다. 그러면 운영에 반영하는 절차를 개시하십시오.")에 따라, Staging 환경에서 사전 검증이 완료된 **마스터 데이터 조회 버그 복구**, **세션 캐시 실시간 무효화**, **신규 분류 전자결재 연동 파이프라인**을 프로젝트 루트의 운영 소스로 안전하게 병합·반영하였습니다.

거버넌스 규칙(`operations.staging`, `operations.server-execution`, `workflow.staging-merge`)의 표준 배포 절차를 철저히 준수하여 다음 순서로 작업을 완료하였습니다:
1. 배포 전 운영 소스 3개 파일의 사전 백업 완료 (`Backups/2026-09-08_pre_master_approval/`)
2. Staging 파일의 운영 루트 복사 및 병합
3. 정규 파서 기반 거버넌스 재검증 및 파일 해시 무결성 검증
4. Staging 임시 작업 파일 정리

---

## 2. 배포 대상 파일 및 무결성 검증

### 2-1. 반영 파일 및 해시(SHA-256) 비교

| 파일명 | 운영 반영 전 백업 SHA-256 | 운영 반영 후 (Production) SHA-256 | Staging 원본 SHA-256 | 일치 여부 |
| :--- | :--- | :--- | :--- | :---: |
| `app.py` | `01BE4BA0A05D99F695C9822868457B8AE8DF9E3BA432A826D6EDF01E49B354FB` | `713EF23A8B44F18BB5FD38574179F07A2CDE23477C01C1A1CFF4624E49D71E91` | `713EF23A8B44F18BB5FD38574179F07A2CDE23477C01C1A1CFF4624E49D71E91` | **100% 일치** |
| `templates/index.html` | `4CBF75E805996A0D097B2D670001D58CF81579A72A46B5FCBCDE09964417D3C5` | `E62196BCD0DE9EDED86758979332F432AB47B996295AC78C5175018EB4A5BD42` | `E62196BCD0DE9EDED86758979332F432AB47B996295AC78C5175018EB4A5BD42` | **100% 일치** |
| `templates/master_management.html` | `09F1E7C350F46B10C4588D5363F4E142445A9D5E46739FFC4C2C4A101924A2DA` | `31ADF7C09B6ECCC5018BE61CF7ECB4E9FF274E0B93E1F890AF3C82DB565C60B7` | `31ADF7C09B6ECCC5018BE61CF7ECB4E9FF274E0B93E1F890AF3C82DB565C60B7` | **100% 일치** |

### 2-2. 백업 보존 위치

- 디렉터리: `Backups/2026-09-08_pre_master_approval/`
  - `Backups/2026-09-08_pre_master_approval/app.py`
  - `Backups/2026-09-08_pre_master_approval/templates/index.html`
  - `Backups/2026-09-08_pre_master_approval/templates/master_management.html`

롤백 필요 시 위 백업 파일로부터 즉시 복원이 가능합니다.

---

## 3. 주요 운영 반영 내용

### 1) 마스터 데이터 관리 API 스키마 정합성 복구 (`app.py`)
- `get_or_create_master_management_item()`의 GET 쿼리에서 존재하지 않는 컬럼 별칭(`c.id`, `m.id`)을 실제 기본키(`c.CategoryId`, `m.ManufacturerId`)로 정정
- 카테고리/제조사 추가 후 목록에서 누락되던 Critical 버그 완전 해소
- `try-except` 예외 쉴드를 추가하여 DB 오류 시 프로세스 중단 방지

### 2) 장비 등록 화면 세션 캐시 실시간 동기화 (`templates/master_management.html`, `templates/index.html`)
- 마스터 데이터 관리 화면에서 카테고리/제조사 추가, 수정, 삭제, 통폐합 성공 시 `invalidateNodeCache()`를 통해 브라우저 `sessionStorage('nodeCache_v2')`를 즉시 무효화
- 장비 등록 모달 진입 시 `window.LineupApp.init(true)` 강제 새로고침을 적용하여 항상 최신 마스터 분류가 드롭다운에 표시되도록 보장

### 3) '기타' 직접 입력 → 전자결재 자동 상신 파이프라인 (`app.py`, `templates/index.html`)
- **UI 레벨**: 카테고리 또는 제조사를 '기타'(`__custom__`)로 선택하고 명칭을 입력하면 [저장하기] 버튼 잠금이 해제되고, **[신규 분류 승인 요청 및 임시등록]** (amber 색상)으로 전환
- **백엔드 레벨**:
  - `add_equipment()`: 미승인 분류(`IsApproved = 0`) 및 PENDING 임시 노드/옵션 생성
  - `approval_requests` 테이블에 `ADD_CATEGORY` / `ADD_MANUFACTURER` 결재 요청 레코드 자동 적재
  - 등록 장비는 `is_draft = 1`로 안전하게 임시 저장되어 관리자 승인 전 외부 비노출 보장
- **결재 처리 레벨**:
  - `process_approval()`: 관리자 결재 승인 시 해당 카테고리/제조사(`IsApproved = 1`), 연계된 노드/옵션(`status = 'APPROVED'`), 장비(`is_draft = 0`)가 일괄 정식 활성화되는 캐스케이드 동기화 적용

---

## 4. 사후 정적 검증 결과

| 검증 항목 | 결과 | 세부 내용 |
| :--- | :---: | :--- |
| 거버넌스 규격 검증 (`governance-tool.mjs validate`) | **PASS** | 40개 노드, 40개 원장 매핑, **0 에러 / 0 경고**, `status: pass` |
| 파일 해시 정합성 | **PASS** | Staging 원본과 운영 반영 파일 간 100% 바이너리 일치 |
| HTML 스크립트 태그 정적 구문 | **PASS** | `index.html`, `master_management.html` 스크립트 무결성 확인 |
| `git diff` 변경점 분석 | **PASS** | 승인된 계획서 범위 외의 불필요한 코드 변경 없음 확인 |

---

## 5. Staging 환경 정리 완료

`workflow.staging-merge` 규칙에 따라, 운영 병합이 완료된 다음 Staging 작업 파일들을 안전하게 정리(삭제)하였습니다:
- `Staging/app.py` (삭제 완료)
- `Staging/templates/index.html` (삭제 완료)
- `Staging/templates/master_management.html` (삭제 완료)

*참고: 별도 진행 중인 정책 문서 후보(`Staging/Rule_5_1_2_Deployment_Test_Order_Candidate.md`)는 보존되었습니다.*

---

## 6. 향후 절차 안내 (Linux 미니서버 적용)

`operations.server-execution` 규칙에 따른 후속 표준 절차는 다음과 같습니다:

1. **Git Commit & Push**:
   - 현재 변경된 운영 소스(`app.py`, `templates/index.html`, `templates/master_management.html`), 계획서, 작업 관리 대장, 검증 보고서를 하나의 단위로 Git Commit 후 원격 저장소(`origin/main`)에 Push합니다.
2. **Linux 미니서버(`192.168.0.166`) 적용**:
   - SSH 접속 후 `git pull origin main` 수행
   - 원격 Commit 해시와 로컬 Pull 해시 일치 확인
   - Flask 서비스 재시작 (`systemctl restart miniserver` 또는 지정된 서비스 관리자)
3. **브라우저 실제 동작 확인**:
   - 마스터 데이터 관리 화면에서 신규 등록/수정/삭제 후 목록 표시 확인
   - 장비 등록 모달에서 '기타' 입력 후 [신규 분류 승인 요청 및 임시등록] 버튼 작동 확인
   - 전자결재 화면에서 상신된 결재 건 승인 처리 및 장비 활성화 확인

