# 카테고리/제조사 마스터 관리 고도화 기획서 (Plan)

- **작성일자:** 2026-08-11
- **관련 제안:** [제안-031] 카테고리/제조사 마스터 관리 고도화 (신규 추가 및 선택 일괄 삭제)
- **상태:** 개발 및 적용 완료

---

## 1. 개요 및 배경
기존 마스터 데이터 관리 화면(`master_management.html`)에서는 이미 등록된 카테고리와 제조사의 수정 및 단일 삭제만 제공되었습니다. 데이터 관리를 보다 효율적으로 수행하고 일괄 처리 편의성을 제공하기 위해, **카테고리 및 제조사의 신규 항목 추가 기능**과 **체크박스 기반의 선택 항목 일괄 삭제 기능**을 도입합니다.

---

## 2. 주요 요구사항 및 구현 계획

### 2.1 신규 항목 추가 기능
- **프론트엔드**:
  - 추가 화면을 기본 기준 뼈대로 모달 UI(`itemModal`) 설계.
  - 카테고리/제조사 탭 전환 시 "➕ 카테고리 추가", "➕ 제조사 추가" 명칭 동적 적용.
  - 추가 모드일 때는 '통폐합(Merge)' 버튼을 비활성화/숨김 처리.
- **백엔드**:
  - `POST /api/master/manage/<target_type>` 엔드포인트 구현.
  - 기본 식별 명칭(Name) 필수 검증 및 중복 명칭 방지 로직 포함.
  - 감사 로그(`CREATE_MASTER`) 기록.

### 2.2 체크박스 기반 선택 일괄 삭제 기능
- **프론트엔드**:
  - 데이터 테이블 헤더에 전체 선택/해제 체크박스(`selectAllCheckbox`) 배치.
  - 테이블 행별 체크박스(`master-checkbox`) 추가.
  - "🗑️ 선택 삭제" 버튼 추가.
- **백엔드**:
  - `POST /api/master/manage/<target_type>/delete_selected` 엔드포인트 구현.
  - 선택된 마스터 ID 목록 수신 및 일괄 삭제 수행.
  - 연결되어 있던 장비(`equipment`) 테이블의 외래키 참조(`CategoryId`, `ManufacturerId`) 및 레거시 텍스트 컬럼(`Category`, `Manufacturer`)을 `NULL`로 안전하게 일괄 초기화.
  - 감사 로그(`DELETE_MASTER_SELECTED`) 기록.

### 2.3 UX 및 안정성 (전역 로딩 오버레이 연동)
- 모든 비동기 Mutation(추가, 수정, 삭제, 일괄 삭제, 통폐합) 시 `showGlobalLoading()`, `hideGlobalLoading()`을 연동하여 중복 클릭 방지 및 시각 피드백 제공.

---

## 3. 변경 파일 목록 및 의존성

1. `app.py`:
   - `get_or_create_master_management_item(target_type)`: `GET` 및 `POST` 처리.
   - `delete_selected_master_items(target_type)`: `POST` 처리.
2. `templates/master_management.html`:
   - 마크업 및 자바스크립트 핸들러 신설.
3. `FEATURES.md`:
   - 기능 명세 추가.
4. `PROPOSALS.md`:
   - [제안-031] 항목 이관 및 상태 업데이트.

---

## 4. 검증 결과 및 데이터 무결성 확인
- 카테고리/제조사 신규 등록 시 중복 검증 정상 동작 확인.
- 일괄 삭제 시 관련된 장비 데이터의 분류 컬럼이 `NULL`로 무결하게 초기화됨을 확인.
- 감사 로그에 생성 및 일괄 삭제 내역이 정상적이고 세부적으로 기록됨을 확인.
