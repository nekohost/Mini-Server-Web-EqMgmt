# [기획서] [제안-045] 웹 접근 로그 페이로드 지연 로딩(Lazy Loading) 최적화

## 1. 개요 및 배경

### 1-1. 배경
[제안-040]을 통해 관리자 웹 접근 로그 화면에서 각 HTTP 요청 및 응답의 세부 내용(Request/Response Payload)을 추적할 수 있도록 컬럼이 확장되었습니다.
그러나 현재 `/api/access_logs` 목록 조회 API는 한 페이지(기본 50건)를 불러올 때마다 모든 행의 `RequestPayload` 및 `ResponsePayload` 텍스트 데이터 전체를 `SELECT`하여 JSON으로 반환하고 있습니다.
페이로드는 크기가 수십 KB에서 수 MB에 이를 수 있어, 다음과 같은 문제가 발생합니다:
1. **네트워크 대역폭 낭비**: 목록만 확인하고 페이로드를 열어보지 않는 경우에도 모든 페이로드 데이터가 전송되어 불필요한 트래픽 발생.
2. **DB I/O 및 쿼리 부하 증가**: SQLite에서 거대한 TEXT 컬럼을 다량으로 읽어들이며 디스크 I/O 및 응답 지연 발생.
3. **브라우저 메모리 부담**: 수십~수백 건의 페이로드가 클라이언트 메모리(`currentLogsData` 배열)에 항상 유지되어 메모리 낭비 유발.

### 1-2. 목적 및 연관 제안
- **연관 제안**: [제안-036] (웹 접근 로그 모니터링), [제안-040] (Payload 수집 및 모달 뷰어), [제안-043] (Payload 재귀 루프 방어), [제안-044] (청크 단위 분할 삭제 및 진행률 UI)
- **목적**:
  - 목록 조회 시 페이로드 본문 전송을 제거하고 유무 플래그(`HasRequestPayload`, `HasResponsePayload`)만 전송하여 목록 로딩 속도를 극대화.
  - 사용자가 모달 팝업으로 상세보기를 요청한 특정 1건의 로그에 대해서만 온디맨드(On-Demand)로 DB에서 페이로드를 불러오는 지연 로딩(Lazy Loading) 구현.

---

## 2. 세부 구현 방안

### 2-1. 백엔드 API 수정 (`app.py`)
1. **목록 조회 API (`GET /api/access_logs`) 경량화**:
   - `SELECT` 절에서 `RequestPayload`, `ResponsePayload` 본문 조회를 제외.
   - `CASE WHEN RequestPayload IS NOT NULL AND RequestPayload != '' THEN 1 ELSE 0 END AS HasRequestPayload`
   - `CASE WHEN ResponsePayload IS NOT NULL AND ResponsePayload != '' THEN 1 ELSE 0 END AS HasResponsePayload`
   - 위와 같이 페이로드 존재 여부만을 나타내는 0/1 플래그 컬럼으로 대체.
2. **단건 페이로드 조회 API 신설 (`GET /api/access_logs/<int:log_id>/payload`)**:
   - `LogId`를 파라미터로 받아 해당 로그 1건의 `RequestPayload`와 `ResponsePayload`만 조회하여 반환.
   - 3대 필수 주석(`[역할]`, `[의존성 관계]`, `[변경 시 영향도]`) 및 권한 체크(`check_menu_permission('access_logs')`) 적용.

### 2-2. 프론트엔드 연동 (`templates/access_logs.html`)
1. **목록 렌더링 수정**:
   - 클립 아이콘 표출 조건을 `log.HasRequestPayload || log.HasResponsePayload` 플래그로 변경.
2. **모달 열기 함수(`openPayloadModal`) 비동기화**:
   - 행 클릭 시 모달을 즉시 열고 "데이터를 불러오는 중입니다..." 로딩 안내 문구 표출.
   - `fetch('/api/access_logs/' + log.LogId + '/payload')` 비동기 호출을 통해 필요한 페이로드 1건만 수신.
   - 수신된 JSON 또는 텍스트를 파싱하여 `modalReqPayload`, `modalResPayload` 영역에 렌더링.
   - 오류 발생 시 에러 메시지 표출 및 방어 처리.

---

## 3. 기대 효과
- **초기 로딩 속도 비약적 향상**: 접근 로그 테이블 첫 화면 로딩 시간이 수초에서 수십 밀리초 단위로 단축.
- **네트워크 및 메모리 리소스 최소화**: 실제 모달을 열람하는 로그에 대해서만 페이로드 통신이 일어나므로 미니서버의 CPU/I/O 및 대역폭 사용량 대폭 절감.
