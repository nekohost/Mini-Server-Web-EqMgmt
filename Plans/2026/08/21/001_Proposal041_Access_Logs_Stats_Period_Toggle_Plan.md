# [제안-041] 웹 접근 로그 요약 통계 기간 필터 확장 기획서 (오늘/전체 토글)

본 기획서는 관리자 웹 접근 로그 모니터링 화면(`access_logs.html`) 상단의 4종 요약 통계 카드에 대해, 기존의 당일(오늘) 기준 집계뿐만 아니라 시스템 전체 누적 기준 집계를 선택하여 조회할 수 있는 기간 토글 기능을 구축하기 위한 아키텍처 및 구현 방안을 정의합니다. `Rule.md`의 격리 검증 원칙(Staging-First) 및 거버넌스 수칙을 엄격히 준수합니다.

---

## 1. 개요 및 배경
- **현황**: 현재 `GET /api/access_logs/stats` API는 `WHERE CreatedAt >= today_start` 조건으로 오늘(당일 00:00:00 이후) 발생한 요청에 대해서만 통계(총 요청, API 요청, 정적 리소스, 에러 응답률)를 집계하여 반환함.
- **요구사항**: 상단 카드에서 오늘자 데이터뿐만 아니라 전체 누적 데이터도 전환하여 조회할 수 있는 기능 제공.
- **목표**: 
  1. 백엔드 통계 API에 기간 파라미터(`period=today|all`) 분기 로직 추가 (기본값 `today`로 하위 호환성 100% 보장).
  2. 프론트엔드 상단 요약 카드 섹션에 직관적인 세그먼트 토글 UI(`[ 📅 오늘 ]` / `[ 🌐 전체 누적 ]`) 추가.
  3. 토글 변경 시 비동기(`fetch`)로 즉각 통계 수치를 갱신하고 카드 레이블을 동적으로 동기화.

---

## 2. 영향도 및 의존성 분석 (Impact & Dependencies)

### 긍정적 측면
1. **모니터링 시야 확장**: 관리자가 일별 트래픽과 전체 누적 트래픽 및 장기적 에러율 추이를 단일 화면에서 원클릭으로 비교 분석 가능.
2. **무중단 및 무손실 (No Schema Change)**: 기존 `access_logs` 테이블 스키마 변경이 전혀 없으므로 데이터 무결성 보존 및 롤백 위험 0%.
3. **하위 호환성 100%**: API 기본값이 `period=today`이므로 기존 호출부나 외부 연동에 파괴적 변경(Breaking Change) 없음.

### 부정적 측면 및 기술적 고려사항
1. **대용량 집계 부하 가능성**: `period=all` 조회 시 `access_logs` 테이블 전체에 대한 집계 쿼리(`COUNT(*)`, `SUM(CASE ...)`)가 수행됨. 현재 미니서버의 수만 건 수준에서는 수 밀리초(ms) 단위로 즉시 처리되나, 수십만 건 이상 누적 시 Full Table Scan 비용이 발생할 수 있음.
2. **대응책**: `access_logs`의 `IsStatic`, `StatusCode` 등의 인덱스를 활용하거나, 필요 시 로그 정리 기능(`api_cleanup_access_logs`)과의 시너지를 통해 쾌적한 데이터 볼륨을 유지함.

---

## 3. 세부 설계 및 변경 명세

### 3-1. 백엔드 API 설계 (`Staging/app.py` ➡️ `app.py`)
- **엔드포인트**: `GET /api/access_logs/stats`
- **쿼리 파라미터**:
  - `period`: `today` (기본값) | `all`
- **로직 흐름**:
  ```python
  @app.route('/api/access_logs/stats', methods=['GET'])
  @login_required
  def api_get_access_log_stats():
      """
      [역할]: 지정된 기간(오늘 또는 전체 누적)의 웹 접근 로그 통계(총 요청, 일반 웹/API, 정적 리소스, 에러율)를 집계하여 반환합니다.
      [의존성 관계]: access_logs 테이블, check_menu_permission('access_logs')
      [변경 시 영향도]: 관리자 접근 로그 화면의 상단 4종 요약 카드 수치 렌더링에 영향을 줍니다.
      """
      if not check_menu_permission('access_logs'):
          return jsonify({"error": "권한이 없습니다."}), 403

      period = request.args.get('period', 'today').lower()
      
      conn = get_db_connection()
      cursor = conn.cursor()

      if period == 'all':
          cursor.execute("""
              SELECT 
                  COUNT(*) as total,
                  SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                  SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                  SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
              FROM access_logs
          """)
      else:
          period = 'today'
          today_str = datetime.now().strftime('%Y-%m-%d')
          today_start = f"{today_str} 00:00:00"
          cursor.execute("""
              SELECT 
                  COUNT(*) as total,
                  SUM(CASE WHEN IsStatic = 0 THEN 1 ELSE 0 END) as api_count,
                  SUM(CASE WHEN IsStatic = 1 THEN 1 ELSE 0 END) as static_count,
                  SUM(CASE WHEN StatusCode >= 400 THEN 1 ELSE 0 END) as error_count
              FROM access_logs
              WHERE CreatedAt >= ?
          """, (today_start,))

      row = cursor.fetchone()
      conn.close()

      total = row['total'] or 0
      api_count = row['api_count'] or 0
      static_count = row['static_count'] or 0
      error_count = row['error_count'] or 0
      error_rate = round((error_count / total * 100.0), 1) if total > 0 else 0.0

      return jsonify({
          "status": "success",
          "period": period,
          "total": total,
          "api_count": api_count,
          "static_count": static_count,
          "error_count": error_count,
          "error_rate": error_rate
      })
  ```

### 3-2. 프론트엔드 UI/UX 설계 (`Staging/templates/access_logs.html` ➡️ `templates/access_logs.html`)
1. **요약 카드 섹션 헤더 구성**:
   - 요약 카드 상단에 제목과 기간 선택 세그먼트 컨트롤 배치:
     ```html
     <div class="flex items-center justify-between mb-3">
         <div class="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
             <i class="fa-solid fa-chart-simple text-brand-500"></i>
             <span id="statSectionTitle">오늘 트래픽 요약</span>
         </div>
         <!-- 기간 전환 세그먼트 버튼 -->
         <div class="inline-flex p-0.5 rounded-lg bg-slate-100 dark:bg-slate-700/60 border border-slate-200 dark:border-slate-700 text-xs">
             <button type="button" onclick="setStatsPeriod('today')" id="btnStatPeriod_today" class="px-2.5 py-1 rounded-md font-semibold transition-all bg-white dark:bg-slate-800 text-brand-600 dark:text-brand-400 shadow-sm">
                 <i class="fa-regular fa-calendar-days mr-1"></i> 오늘
             </button>
             <button type="button" onclick="setStatsPeriod('all')" id="btnStatPeriod_all" class="px-2.5 py-1 rounded-md font-medium transition-all text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                 <i class="fa-solid fa-globe mr-1"></i> 전체 누적
             </button>
         </div>
     </div>
     ```
2. **동적 레이블 갱신**:
   - 총 요청 카드의 레이블 ID `#statTotalTitle`을 마련하여 `오늘 총 요청` ↔ `전체 총 요청` 텍스트 전환.
3. **자바스크립트 제어 함수**:
   ```javascript
   let currentStatsPeriod = 'today';

   function setStatsPeriod(period) {
       if (currentStatsPeriod === period) return;
       currentStatsPeriod = period;
       
       // 버튼 스타일 전환
       const btnToday = document.getElementById('btnStatPeriod_today');
       const btnAll = document.getElementById('btnStatPeriod_all');
       const title = document.getElementById('statSectionTitle');
       const totalTitle = document.getElementById('statTotalTitle');
       
       if (period === 'today') {
           btnToday.className = 'px-2.5 py-1 rounded-md font-semibold transition-all bg-white dark:bg-slate-800 text-brand-600 dark:text-brand-400 shadow-sm';
           btnAll.className = 'px-2.5 py-1 rounded-md font-medium transition-all text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200';
           if (title) title.innerText = '오늘 트래픽 요약';
           if (totalTitle) totalTitle.innerText = '오늘 총 요청';
       } else {
           btnAll.className = 'px-2.5 py-1 rounded-md font-semibold transition-all bg-white dark:bg-slate-800 text-brand-600 dark:text-brand-400 shadow-sm';
           btnToday.className = 'px-2.5 py-1 rounded-md font-medium transition-all text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200';
           if (title) title.innerText = '전체 누적 트래픽 요약';
           if (totalTitle) totalTitle.innerText = '전체 총 요청';
       }
       
       fetchStats();
   }

   async function fetchStats() {
       try {
           const res = await fetch(`/api/access_logs/stats?period=${encodeURIComponent(currentStatsPeriod)}`);
           if (res.ok) {
               const data = await res.json();
               document.getElementById('statTotalRequests').innerText = Number(data.total || 0).toLocaleString() + ' 건';
               document.getElementById('statApiRequests').innerText = Number(data.api_count || 0).toLocaleString() + ' 건';
               document.getElementById('statStaticRequests').innerText = Number(data.static_count || 0).toLocaleString() + ' 건';
               document.getElementById('statErrorRate').innerText = (data.error_rate || 0).toFixed(1) + '%';
           }
       } catch (err) {
           console.error('통계 조회 오류:', err);
       }
   }
   ```

---

## 4. 개발 및 검증 파이프라인 (Task 계획)

- **Phase 1 (문서화 및 등록)**:
  - `PROPOSALS.md` 및 `UNIMPLEMENTED_PROPOSALS.md`에 `[제안-041]` 등재
  - `ROADMAP.md` 및 `UNIMPLEMENTED_ROADMAP.md`에 작업 등록
- **Phase 2 (스테이징 격리 개발)**:
  - `Staging/` 디렉토리에 `Staging_PLAN.md` 생성 및 `Staging/app.py`, `Staging/templates/access_logs.html` 모의 구현
- **Phase 3 (검증 방법론 점검)**:
  - `VALIDATION_METHODOLOGY.md` 기반 정적 검증 및 검증 보고서 작성
- **Phase 4 (프로덕션 병합 및 배포)**:
  - 실제 `app.py` 및 `templates/access_logs.html`에 병합 반영
  - `Staging/` 임시 작업 파일 정리(Clean-up)
  - Git 커밋 및 Push
