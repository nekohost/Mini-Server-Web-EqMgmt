# [Staging 검증 계획] 복합 검색 프론트엔드 로딩 UI 함수명 시정

## 1. 목적
- 복합 조건 검색(카테고리 + 제조사) 기능 구동 시 발생한 JavaScript 참조 오류(`showLoading is not defined`)를 시정합니다.
- Rule 7-3조 격리 원칙에 따라 운영 소스코드(`templates/dashboard.html`, `app.py`)를 직접 건드리지 않고, `Staging/` 폴더 내에 복제된 환경에서 독립적으로 수정 및 검증을 수행합니다.

## 2. 변경 파일
- `Staging/Staging_dashboard.html`: `showLoading()` ➔ `showGlobalLoading()`, `hideLoading()` ➔ `hideGlobalLoading()` 교체.
- `Staging/Staging_app.py`: Staging 검증용 라우트(`/staging/dashboard`) 및 Jinja Loader 오버라이딩 적용.

## 3. 검증 항목
- 미니서버에서 `python3 Staging/Staging_app.py` 가동 후 `/staging/dashboard` 접속.
- 복합 검색 실행 시 전체 화면 로딩 오버레이 정상 동작 및 검색 결과 정상 렌더링 확인.
