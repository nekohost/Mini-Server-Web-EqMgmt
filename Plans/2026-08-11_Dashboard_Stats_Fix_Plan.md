# 카테고리 외래키(FK) 연동에 따른 통계 대시보드 쿼리 복구 기획서 (Plan)

- **작성일자:** 2026-08-11
- **관련 작업:** 카테고리/제조사 외래키(FK) 구조 개편에 따른 대시보드 통계 집계 쿼리 복구
- **상태:** 개발 및 적용 완료

---

## 1. 개요 및 배경
장비 데이터 구조가 `Category` (단순 문자열) 형태에서 `CategoryId` (마스터 데이터 테이블 참조 외래키) 구조로 개편됨에 따라, `api_dashboard_stats` 함수 내부의 단순 `GROUP BY Category` 쿼리가 외래키 참조 명칭을 정상적으로 가져오지 못하는 문제가 발생했습니다.
또한 장비 임시저장(`IsDraft = 1`) 상태 데이터가 대시보드 수치 집계에 포함되는 오류를 수정하기 위해 쿼리 보정을 수행합니다.

---

## 2. 주요 요구사항 및 구현 계획

### 2.1 대시보드 쿼리 고도화
- **임시저장(IsDraft) 데이터 제외**:
  - 내 장비 수, 총 장비 수, 카테고리별 통계 집계 시 `(e.IsDraft = 0 OR e.IsDraft IS NULL)` 조건을 필수 적용.
- **카테고리 외래키 LEFT JOIN 및 COALESCE 처리**:
  - `equipment` 테이블과 `categories` 테이블을 `LEFT JOIN categories c ON e.CategoryId = c.CategoryId`로 연결.
  - 카테고리 명칭 반환 시 `COALESCE(c.NameKo, c.Name, e.Category, '미분류')` 순서로 안전하게 명칭을 자동 바인딩.

---

## 3. 변경 파일 목록 및 의존성

1. `app.py`:
   - `api_dashboard_stats()`: `LEFT JOIN` 및 `COALESCE` 적용, `IsDraft` 조건 추가.
   - `Rule 4-3` 주석(`[역할]`, `[의존성 관계]`, `[변경 시 영향도]`) 유지.
2. `Plans/2026-08-11_Dashboard_Stats_Fix_Plan.md`:
   - 기획서 아카이빙 (Rule 7-2 준수).

---

## 4. 검증 결과
- `api_dashboard_stats` 결과에 카테고리 한국어/영문 명칭이 올바르게 매핑되어 반환됨.
- 임시저장 상태의 장비가 집계 수치에서 제외되는 것 확인.
