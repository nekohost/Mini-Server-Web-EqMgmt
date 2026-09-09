# [영구 기획서] 실시간 웹 접근 로그(HTTP Access Log) 자동 수집 및 모니터링 시스템 구축

**문서 분류**: 영구 보존 기획서 (`Rule.md` 제7-2조)  
**작성 일시**: 2026-08-15 01:25:00 (KST)  
**대상 기능**: `[제안-036]` 실시간 웹 접근 로그 자동 수집 및 관리자 모니터링 시스템 구축  
**관련 규정**: `Rule.md` 제1-3조, 제2조, 제3조, 제4조, 제6조, 제7조  

---

## 1. 개요 및 배경

본 기획서는 개인 보유 장비 관리 미니서버(`192.168.0.166`)에 유입되는 모든 HTTP 트래픽(일반 페이지, RESTful API, 정적 리소스, 외부 비인가 스캐너/봇넷 등)을 실시간으로 수집하고, 관리자 전용 웹 모니터링 화면(`access_logs.html`)을 통해 관제할 수 있는 경량 고성능 인프라를 구축하는 것을 목적으로 합니다.

Staging 검증 단계에서 도출된 **1. `Rule.md` 제4-3조 주석 수칙 준수, 2. `ROADMAP.md` [제안-029] 전역 로딩 오버레이 연동, 3. `common.js` 전역 CSRF 함수 재활용**을 전수 수용하여 완전 무결점 상태로 기획되었습니다.

---

## 2. 핵심 요구사항 및 아키텍처 원칙

1. **미니서버 SD카드 보호 (디스크 I/O 95% 절감)**:
   - 요청마다 DB `INSERT`를 치지 않고 In-Memory `queue.Queue(maxsize=10000)`에 적재.
   - 백그라운드 단일 워커 스레드가 0.5초 또는 50건 단위로 `executemany` 벌크 커밋.
2. **웹 서비스 가용성 최우선 (Fail-Open)**:
   - `queue.put_nowait()`로 큐 풀 시 안전하게 드롭하여 웹 요청 딜레이 0ms 보장.
   - `@app.after_request` 인터셉터를 최상위 `try...except`로 감싸 로깅 에러 시 500 에러 전파 100% 차단.
3. **완벽한 동시성 제어 및 Graceful Shutdown**:
   - `threading.Event()` + 워커 `get(0.5s)` + 메인 스레드 `join(3.0s)` 조합으로 서버 재시작/종료 시 잔여 로그 100% 보존.
   - SQLite `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 5000;`.
4. **사용자 지침 준수 (수동 클렌징 유지 & 자동 삭제 코드 구비)**:
   - 백그라운드 자동 삭제는 비활성화된 상태를 유지하되, 30,000건 초과 삭제 쿼리를 워커 내에 주석(`#`)으로 완비.
   - UI에 3종 수동 클렌징(30일 이전 정리, 정적 로그 삭제, 전체 초기화) 모달 및 CSRF 연동 제공.
5. **규정 준수 (Rule.md 제4-3조 및 [제안-029])**:
   - 프론트엔드/백엔드 모든 함수에 `[역할]`, `[의존성 관계]`, `[변경 시 영향도]` 3대 주석 100% 기입.
   - 비동기 데이터 변경(수동 삭제) 시 전역 로딩 오버레이(`window.showGlobalLoading()`) 표출.
   - `common.js`의 `window.getCSRFToken()` 재활용.

---

## 3. 세부 명세

### 3-1. DB 스키마 (`access_logs`)
- `LogId` (INTEGER PK AUTOINCREMENT)
- `IpAddress` (TEXT NOT NULL)
- `HttpMethod` (TEXT NOT NULL)
- `RequestPath` (TEXT NOT NULL)
- `StatusCode` (INTEGER NOT NULL)
- `UserAgent` (TEXT)
- `Referer` (TEXT)
- `DurationMs` (REAL)
- `IsStatic` (INTEGER DEFAULT 0)
- `CreatedAt` (TEXT NOT NULL)
- 인덱스 4종 (`CreatedAt`, `IpAddress`, `StatusCode`, `IsStatic`)

### 3-2. API 엔드포인트
- `GET /access_logs` (관리자 전용 웹 페이지 렌더링)
- `GET /api/access_logs` (필터링 및 페이징 JSON 반환)
- `GET /api/access_logs/stats` (오늘 트래픽 요약 통계 JSON 반환)
- `POST /api/access_logs/cleanup` (수동 로그 클렌징 수행, CSRF 필수)
