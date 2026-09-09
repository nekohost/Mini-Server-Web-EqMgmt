# [제안-039] 에러 유발 고유 IP 심층 분석(Error IP Analysis) 대시보드 추가 작업 기획서

- **문서 번호:** Plan-Proposal-039
- **작성 일자:** 2026-08-18
- **작성자:** Gemini (Pair-Programming Agent)
- **상태:** 기획 승인 완료 (Staging 개발 진행 중)

---

## 1. 개요 및 목적
현재 웹 접근 로그(`access_logs.html`)는 모든 인바운드 HTTP 요청이 시간 순서대로 단건 나열되어 있습니다. 
악성 스캐너, 크롤러, 무차별 대입 공격자 등 4xx 및 5xx 에러를 유발하는 IP 주소를 직관적으로 특정하고 통계를 파악하기 어렵기 때문에, **4xx/5xx 에러를 발생시킨 IP 주소들만 중복을 제거(GROUP BY)하여 집계**하고, 상위 에러 발생 IP를 차트로 시각화하며 기존 로그로의 상세 추적(딥링크)을 지원하는 심층 분석 화면을 신설합니다.

---

## 2. 세부 설계 사양

### 2.1 UI/UX 설계 (`templates/access_logs_error_ips.html` 및 `templates/access_logs.html`)
1. **서브 메뉴 진입점 (Depth +1)**:
   - `access_logs.html` 화면 상단 액션 바에 `[🔍 에러 유발 IP 분석]` 버튼을 배치하여 화면 간 유기적 이동 지원.
2. **신규 템플릿 (`access_logs_error_ips.html`) 레이아웃**:
   - **상단 요약 카드/차트**: 에러 발생 상위 IP TOP 5의 순위 및 발생 건수를 직관적인 CSS 바 차트/통계 카드로 표출.
   - **고유 IP 집계 테이블**:
     - IP 주소 (클릭 시 원본 `access_logs.html`로 검색 파라미터와 함께 딥링크 이동)
     - 총 에러 건수 (Total Errors)
     - 4xx 클라이언트 에러 건수 (400, 403, 404, 405 등)
     - 5xx 서버 에러 건수 (500, 502 등)
     - 최근 에러 발생 시각 (Last Seen)
   - **상단 복귀 버튼**: 원본 `웹 접근 로그`로 즉시 되돌아가는 네비게이션 제공.
3. **원본 로그 딥링크 연동 (`access_logs.html`)**:
   - URL의 쿼리스트링 `?search_ip=xxx.xxx.xxx.xxx` 파라미터를 수신하여 검색창에 자동 입력 후 필터링 조회 실행.

### 2.2 백엔드 라우트 및 순수 쿼리 API (`app.py`)
> **No-Logic 원칙**: 별도의 백그라운드 엔진이나 테이블 추가 없이, 기존 `access_logs` 테이블에 순수 SQL 쿼리(`GROUP BY`)만 실행.

1. **뷰 라우트**:
   ```python
   @app.route('/access_logs/error_ips')
   @login_required
   def access_logs_error_ips_page():
       """
       [역할]: 에러(4xx, 5xx) 유발 IP 심층 분석 전용 화면을 렌더링합니다.
       [의존성 관계]: access_logs_error_ips.html, check_menu_permission('access_logs')
       [변경 시 영향도]: 에러 IP 관제 UI 진입에 영향을 줍니다.
       """
       if not check_menu_permission('access_logs'):
           return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
       return render_template('access_logs_error_ips.html', user=session['user'])
   ```

2. **데이터 API (`/api/access_logs/error_ips`)**:
   ```python
   @app.route('/api/access_logs/error_ips')
   @login_required
   def api_access_logs_error_ips():
       """
       [역할]: access_logs 테이블에서 4xx/5xx 에러를 발생시킨 고유 IP 목록 및 에러 통계를 집계하여 반환합니다.
       [의존성 관계]: sqlite3 (equipment.db), access_logs 테이블, check_menu_permission('access_logs')
       [변경 시 영향도]: 에러 IP 심층 분석 화면의 비동기 데이터 로딩에 영향을 줍니다.
       """
       if not check_menu_permission('access_logs'):
           return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
       
       # 쿼리: 4xx 이상 상태코드를 유발한 IP별 그룹화 집계
       query = """
           SELECT 
               IpAddress,
               COUNT(LogId) AS TotalErrorCount,
               MAX(CreatedAt) AS LastErrorAt,
               SUM(CASE WHEN StatusCode >= 400 AND StatusCode < 500 THEN 1 ELSE 0 END) AS ClientErrorCount,
               SUM(CASE WHEN StatusCode >= 500 THEN 1 ELSE 0 END) AS ServerErrorCount
           FROM access_logs
           WHERE StatusCode >= 400
           GROUP BY IpAddress
           ORDER BY TotalErrorCount DESC, LastErrorAt DESC
       """
       # sqlite3 조회 및 json 반환
   ```

---

## 3. Rule.md 거버넌스 준수 지침
- **제7-3조 (스테이징 우선 적용)**: `Staging/` 디렉토리에 파일들을 생성 및 수정하여 격리 개발 진행.
- **제5-1-1조 (PC 직접 구동 금지)**: Windows 로컬 환경에서 웹 서버 구동 테스트 금지. AST 정적 분석 및 쿼리 무결성 검증 수행.
- **제4-3조 (주석 3대 원칙)**: 모든 신규 함수에 `[역할]`, `[의존성 관계]`, `[변경 시 영향도]` 명시.
- **제6조 (대화 기록 관리)**: 모든 상호작용을 `Chat/` 디렉토리에 실시간 영구 기록.
