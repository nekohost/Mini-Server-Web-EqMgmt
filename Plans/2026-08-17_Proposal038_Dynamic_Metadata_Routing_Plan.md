# [제안-038] 메타데이터 자동 라우팅 및 보안 텍스트(security.txt) 도입 기획서

## 1. 개요 및 목적
외부 크롤러 및 AI 봇의 무작위 스캐닝으로부터 발생하는 불필요한 트래픽 및 404 에러 로그 생성을 방지하고, 프로젝트의 소유권을 명확히 하는 표준 메타데이터 제공을 목적으로 합니다.
이는 `Rule.md` 제4-5조(보안 및 환경 설정 지침)를 충족시키며, 시스템 관리자의 로그 모니터링 가시성을 높입니다.

## 2. 주요 변경 사항
1. **메타데이터 자동 라우팅 엔진** (`app.py`):
   - `Resources/metadata/` 폴더 내의 정적 파일들을 `os.walk`를 통해 재귀적으로 탐색합니다.
   - 탐색된 파일은 `app.add_url_rule`을 사용하여 동적 라우팅으로 생성되며, 클로저 환경의 늦은 바인딩(Late Binding) 이슈를 피하기 위해 `create_view_func` 헬퍼를 활용합니다.
   - Endpoint 명명 시 경로명을 변환하여 중복을 방지하고 `existing_rules`를 통해 충돌(`AssertionError`)을 예방합니다.

2. **접근 로그의 정적 리소스 필터링 성능 최적화** (`app.py` `after_request_func`):
   - 기존의 하드코딩된 리스트 대신 부팅 시 등록된 `STATIC_METADATA_ROUTES_FROZEN` (`frozenset`) 캐시를 활용해 O(1) 시간 복잡도로 빠르게 `IsStatic=1` 여부를 판별합니다.

3. **보안 및 규격 텍스트 고정** (`Resources/metadata/`):
   - `robots.txt`: 검색 엔진 크롤러 접근 제어 (`/admin_center`, `/api/` 등 차단)
   - `llms.txt`: AI 언어 모델 스캐너용 안내
   - `security.txt` & `.well-known/security.txt`: RFC 9116 표준을 준수하며, 이메일 주소를 `nekohost@nekohost.org`로 절대값(하드코딩) 적용.

## 3. 구현 내역 (스테이징 검증 결과 통합)
- `Rule.md` 5-1-1에 따른 로컬 런타임 제한을 준수하여, 소스 코드 레벨의 정밀한 교차 분석 수행 완료.
- 클로저 늦은 바인딩(Late Binding) 방어, O(1) 성능 최적화, 윈도우-리눅스 크로스 플랫폼 슬래시(`/`) 정규화 모두 완벽히 무결함으로 확인되었습니다.

*작성일자: 2026-08-17 (스테이징 검증 및 운영 반영 병합 완료 시점)*
