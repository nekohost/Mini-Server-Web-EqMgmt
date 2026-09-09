# [제안-040] 웹 접근 로그 상세 기록 확장 기획서 (Request & Response Payload 로깅)

본 기획서는 웹 접근 로그 시스템(`access_logs`)에 HTTP Request 및 Response의 Payload(Body)를 기록하여 트러블슈팅 및 감사 기능을 고도화하기 위한 아키텍처 및 구현 방안을 정의합니다. `Rule.md`의 격리 검증 원칙(Staging-First)을 준수합니다.

## User Review Required

> [!CAUTION]
> **민감 정보(Sensitive Data) 무제한 기록 및 무제한 용량 수용 (사용자 지시 적용됨)**
> 사용자의 명시적인 지시("민감정보도 그대로 기록", "전체를 기록하고자 하는 의도가 있으므로 제한을 두지 않음")에 따라:
> 1. `password` 등을 포함한 모든 인증 정보 및 민감 정보가 **마스킹 없이 평문으로 기록**됩니다.
> 2. 대용량 응답에 대한 **용량 제한 로직(Cut-out)을 일절 두지 않고 전체 데이터를 기록**합니다.
> 
> *이 조치는 보안상 취약할 수 있으며 DB 용량의 급격한 증가를 초래할 수 있으나, 사용자의 강력한 감사 기록 확보 의도에 의해 반영되었습니다.*

## Proposed Changes

### Staging/app.py (백엔드 핵심 로직 변경)

#### [MODIFY] `Staging/app.py`
1. **DB 스키마 확장 (`init_db` 함수)**
   - `access_logs` 테이블 생성 구문에 `request_payload TEXT`, `response_payload TEXT` 컬럼 추가.
   - 기존 데이터를 파괴하지 않기 위해 `ALTER TABLE access_logs ADD COLUMN ...` 마이그레이션 구문 동반.
2. **비동기 큐 워커 확장 (`access_log_worker` 함수)**
   - `sqlite3.connect` 및 `INSERT` 쿼리 밸류 목록에 `request_payload`, `response_payload` 바인딩 추가.
3. **Payload 추출 로직 (`after_request` 함수)**
   - `request.get_data(as_text=True)`를 통해 Request Body를 원본 그대로 추출. (마스킹 없음)
   - `response.get_data(as_text=True)`를 통해 Response Body를 원본 그대로 추출. (용량 제한 없이 전체 기록)
   - 추출된 데이터를 `push_access_log()` 인자로 추가.

### Staging/templates/access_logs.html (프론트엔드 UI 변경)

#### [MODIFY] `Staging/templates/access_logs.html`
1. **로그 테이블 UI 변경**
   - 기존의 단건 나열 행에 `Payload 보기` 뱃지 또는 행(Row) 클릭 이벤트 속성 부여.
2. **모달(Modal) 컴포넌트 추가**
   - 클릭 시 숨겨진 `request_payload`, `response_payload` 텍스트를 JSON Pretty Print 포맷으로 렌더링하는 `Tailwind CSS` 기반 모달 팝업 요소 추가.
   - 바이트가 없는(Payload=NULL) 경우 "Payload가 없는 요청입니다." 안내 문구 표출.

## Verification Plan

### Manual Verification
1. `Staging/app.py`를 정적 리뷰한 후 정상 가동합니다.
2. 로그인(`POST /login`)을 시도할 때, 패스워드가 접근 로그 테이블(`access_logs`)에 **평문 그대로 저장**되는지 DB 단 검증을 실시합니다. (사용자 지시사항 확인)
3. 새로운 장비를 등록하거나 수정(`POST /api/equipments_v2`)하여 JSON Request/Response 데이터가 모두 로그로 남는지 확인합니다.
4. 관리자 페이지(`access_logs.html`)로 접속하여 딥링크(모달 클릭) 액션 시 Payload가 직관적으로 펼쳐지는지 UI 동작을 확인합니다.
