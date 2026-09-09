# [기획서] 운영 소스코드 전체 코드 흐름 기반 상세 주석 표준화 작업

## 1. 개요 (배경 및 목적)
사용자께서 `Rule.md`의 **4-3. 코드 주석 보존 수칙**을 개정하고 심층적인 실행 흐름 명시를 지시함에 따라, 향후 개발 및 유지보수 시 모든 AI 에이전트와 휴먼 개발자가 코드의 역할뿐 아니라 **변수 입출력, 실행 흐름(Flow), 조건 분기 결과에 따른 파급 효과**를 완벽하게 인지할 수 있도록 운영 환경의 모든 소스코드(Python, HTML, JS, 스크립트 등)에 대해 1파일 1페이즈 원칙으로 상세 주석을 일괄 적용하고자 합니다.

---

## 2. 준수해야 하는 사실들의 적시 (사전 확인 및 절대 준수 규칙)
작업에 착수하기 전, 아래의 규정을 반드시 숙지하고 100% 준수해야 합니다.

> [!IMPORTANT]
> **모든 작업의 대전제: Rule.md 및 GEMINI.md 정독·준수·무위배 원칙**
> 모든 페이즈의 개별 파일 및 후속 작업에 착수하기 전, 아래 3개 항목이 선행되어야 합니다:
> 1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
> 2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
> 3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것

> [!IMPORTANT]
> **Rule.md 제4-3조 (코드 주석 보존 및 코드 실행 흐름 상세화 수칙)**
> 1. **3대 표준 메타 주석**: 모든 함수, API 라우트, 모듈/템플릿 상단에는 `[역할]`, `[의존성 관계]`, `[변경 시 영향도]`를 반드시 작성/유지하며, 기존의 설계 의도를 절대 희석하지 않고 더욱 명확하게 구체화(상세화)해야 합니다.
> 2. **코드 실행 흐름(Flow) 및 변수 컨텍스트 명시**: 각 코드 라인 혹은 논리적 코드 블록마다 단순 동작 설명에 그치지 않고, 아래의 내용을 반드시 포함하여 기재합니다:
>    - **변수의 입출력 맥락**: 어떤 변수에 무엇을 담는지, 그 변수를 통해 외부나 DB에서 무엇을 가져오는지.
>    - **실행 흐름 및 분기 결과**: 조건식(`if/else`) 평가 결과에 따라 시스템 흐름이 어디로 이어지는지, 예외 발생 시 어떻게 흘러가는지.
>    - **비즈니스 파급 효과**: 이 연산이나 호출의 결과로 프론트엔드/백엔드 상태가 최종적으로 어떻게 전이되는지.

> [!CAUTION]
> **코드 무결성 및 비즈니스 로직 보존 원칙**
> 1. 주석을 추가/개선하는 과정에서 **절대 기존의 작동 코드가 훼손되거나 비즈니스 로직/변수명/함수 시그니처가 변경되어서는 안 됩니다.** 오직 주석(`/* */`, `<!-- -->`, `#`, docstring)만이 추가·보강되어야 합니다.
> 2. `Rule.md` 제8-2조에 따라 모든 파일 수정은 IDE 내장 API(`replace_file_content` 등)만을 사용합니다.
> 3. `Rule.md` 제5-1-1조에 따라 Windows 로컬 런타임 구동 테스트를 시도하지 않고 정적 정합성 검증을 준수합니다.

---

## 3. 영향을 미칠 파일의 완전한 리스트 (총 30개 파일)

### 3-1. 백엔드 파이썬 핵심 및 DB 마이그레이션 (5개)
1. `app.py`
2. `utils/mailer.py`
3. `utils/__init__.py`
4. `db_migration.py`
5. `down_migration.py`

### 3-2. 프론트엔드 스태틱 자바스크립트 및 서드파티 (3개)
6. `static/js/common.js`
7. `static/js/session_timer.js`
8. `static/js/tailwindcss.js` *(서드파티 CDN 번들: 최상단 메타 주석으로 한정)*

### 3-3. 환경 설정 및 정적 메타데이터 자산 (4개)
9. `requirements.txt`
10. `Resources/metadata/llms.txt`
11. `Resources/metadata/robots.txt`
12. `Resources/metadata/security.txt` & `.well-known/security.txt`

### 3-4. 프론트엔드 UI 템플릿 (18개)
13. `templates/root_frame.html`
14. `templates/portal.html`
15. `templates/index.html`
16. `templates/dashboard.html`
17. `templates/admin_center.html`
18. `templates/access_logs.html`
19. `templates/access_logs_error_ips.html`
20. `templates/audit_logs.html`
21. `templates/master_management.html`
22. `templates/users_management.html`
23. `templates/permissions.html`
24. `templates/approvals.html`
25. `templates/login.html`
26. `templates/register.html`
27. `templates/reset_password.html`
28. `templates/mypage.html`
29. `templates/deactivated_notice.html`
30. `templates/miniserver_frame.html`

---

## 4. 작업의 상세 (코드 흐름 중심 상세 주석 작성 기준 및 예시)

모든 주석은 "코드 동작 흐름"과 "데이터의 이동 경로"를 완벽히 추적할 수 있도록 작성됩니다.

### 4-1. 파이썬 백엔드 주석 표준 모델 예시
```python
def api_get_equipment_detail(equipment_id):
    """
    [역할]: 단일 장비의 상세 정보 및 하위 옵션 목록을 JSON 형태로 반환합니다.
    [의존성 관계]: DB 테이블(equipments, equipment_options), 프론트엔드 모달 렌더러(index.html::openDetailModal)
    [변경 시 영향도]: 반환 JSON 키값 변경 시 프론트엔드 렌더링 스크립트 수정 필수
    """
    # [1] 요청 검증 및 변수 초기화: 클라이언트로부터 전달받은 equipment_id 파라미터가 유효한 정수형인지 확인
    if not equipment_id:
        # 유효하지 않은 ID가 들어오면 400 Bad Request 에러 JSON을 생성하여 클라이언트에 즉시 반환하고 함수 종료
        return jsonify({'error': '유효하지 않은 장비 ID입니다.'}), 400

    # [2] DB 커넥션 획득 및 쿼리 실행: equipment_id를 바인딩하여 단일 장비 레코드를 조회
    conn = get_db_connection()
    # sqlite3.Row 객체 형태로 장비 기본 마스터 데이터를 획득
    equipment = conn.execute("SELECT * FROM equipments WHERE id = ?", (equipment_id,)).fetchone()

    # [3] 조회 결과에 따른 분기 흐름: 해당 장비가 DB에 존재하는지 검사
    if not equipment:
        # 데이터가 없을 경우 리소스 닫기 후 404 Not Found 응답 반환
        conn.close()
        return jsonify({'error': '해당 장비를 찾을 수 없습니다.'}), 404

    # [4] 연관 데이터 조회: 장비 ID를 외래키로 가진 옵션 스펙 목록을 추가 조회하여 리스트에 적재
    options = conn.execute("SELECT * FROM equipment_options WHERE equipment_id = ?", (equipment_id,)).fetchall()
    conn.close()

    # [5] 최종 페이로드 조립: Row 객체를 딕셔너리로 변환하여 options 배열과 함께 클라이언트로 200 OK 응답 전송
    response_data = dict(equipment)
    response_data['options'] = [dict(opt) for opt in options]
    return jsonify(response_data), 200
```

### 4-2. 프론트엔드 HTML / JS 주석 표준 모델 예시
```html
<!--
=============================================================================
[화면명]: templates/index.html
[역할]: 장비 등록, 계층형 목록 조회, 수정, 삭제(Soft-Delete)를 지원하는 핵심 관리 UI
[의존성 관계]: app.py (/api/equipments, /api/master), static/js/common.js, tailwindcss.js
[변경 시 영향도]: 장비 DB 스키마 컬럼 변경 시 테이블 컬럼 및 모달 폼 필드 동시 수정 필요
=============================================================================
-->

<!-- [UI 섹션: 장비 검색 및 카테고리 필터 툴바] -->
<!-- 사용자가 입력한 키워드(searchKeyword)와 선택한 카테고리(categoryFilter)를 기반으로 API 파라미터를 조립하는 입력 영역 -->
<div id="filterToolbar" class="flex flex-wrap gap-2 mb-4">
    ...
</div>

<script>
/**
 * [역할]: 필터 툴바의 입력값을 수집하여 백엔드 장비 목록 API를 비동기 호출하고 카드를 갱신합니다.
 * [의존성 관계]: /api/equipments API, renderEquipmentCards() 렌더러 함수
 * [변경 시 영향도]: API 쿼리 파라미터 규격 변경 시 전달 payload 키값 동시 수정
 */
async function fetchEquipmentList() {
    // [1] 검색 조건 수집: 검색창 입력값과 카테고리 셀렉트박스의 선택값을 변수에 바인딩
    const keyword = document.getElementById('searchInput').value.trim();
    const category = document.getElementById('categorySelect').value;

    // [2] URLSearchParams 객체를 생성하여 조건이 존재하는 경우에만 쿼리 스트링에 추가
    const params = new URLSearchParams();
    if (keyword) params.append('q', keyword);
    if (category) params.append('category', category);

    // [3] API 비동기 요청 전송: 조립된 URL로 GET 요청을 전송하고 네트워크 상태를 대기
    try {
        const response = await fetch(`/api/equipments?${params.toString()}`);
        // 응답 상태코드가 200이 아닌 경우 에러를 발생시켜 catch 블록으로 흐름 전이
        if (!response.ok) throw new Error('데이터 조회 실패');

        // [4] JSON 파싱 및 데이터 렌더링: 성공 시 파싱된 장비 배열 데이터를 넘겨 화면 카드 그리드를 새로 그림
        const data = await response.json();
        renderEquipmentCards(data.items);
    } catch (err) {
        // [5] 예외 처리: 통신 실패 시 공통 Toast 알림 유틸리티를 호출하여 사용자에게 에러 메시지 팝업 노출
        showToast('장비 목록을 불러오지 못했습니다: ' + err.message, 'error');
    }
}
</script>
```

---

## 5. 세부 페이즈 실행 파이프라인 (1 File = 1 Phase 및 분리된 원격 반영 체계)

모든 개별 파일 페이즈는 아래의 **5단계 세부 순서**에 따라 엄격히 수행됩니다:
- **세부 1단계**: `GEMINI.md` 와 `Rule.md` 를 정독할 것
- **세부 2단계**: `GEMINI.md` 와 `Rule.md` 를 준수할 것
- **세부 3단계**: `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
- **세부 4단계**: 3대 표준 메타주석(`[역할]`, `[의존성 관계]`, `[변경 시 영향도]`) 및 전역 네임스페이스/파일 설계 목적을 기존 의도를 절대 희석하지 않고 더욱 명확하게 상세화
- **세부 5단계**: 각 코드줄(혹은 코드블록)마다 변수 입출력, 실행 흐름, 조건별 분기 결과 등을 포함한 심층 상세 주석 작성

---

### [그룹 A] 백엔드 핵심 및 DB 마이그레이션 스크립트
- **페이즈 1**: `app.py` (메인 Flask 앱 및 전체 API 엔드포인트)
  - 1-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 1-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 1-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 1-4. 3대 표준/메타주석 상세화 (기존 설계 의도 보존)
  - 1-5. 코드 흐름/변수 컨텍스트 심층 주석화
- **페이즈 2**: `utils/mailer.py` (비동기 메일 발송 큐 모듈)
  - 2-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 2-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 2-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 2-4. 3대 표준/메타주석 상세화 (기존 설계 의도 보존)
  - 2-5. 코드 흐름/변수 컨텍스트 심층 주석화
- **페이즈 3**: `utils/__init__.py` (유틸리티 패키지 초기화)
  - 3-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 3-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 3-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 3-4. 모듈 네임스페이스 메타주석 상세화
  - 3-5. 패키지 익스포트 코드 흐름 주석화
- **페이즈 4**: `db_migration.py` (3-Tier 계층형 DB 정방향 마이그레이션 스크립트)
  - 4-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 4-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 4-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 4-4. 3대 표준/안전장치 메타주석 상세화
  - 4-5. 트랜잭션/테이블 생성/데이터 이관 흐름 상세 주석화
- **페이즈 5**: `down_migration.py` (3-Tier -> 1-Tier 역방향 롤백 스크립트)
  - 5-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 5-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 5-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 5-4. 3대 표준/비가역성 경고 메타주석 상세화
  - 5-5. 롤백/압축 복원 트랜잭션 흐름 상세 주석화

---

### [그룹 B] 프론트엔드 스태틱 자바스크립트 및 정적 설정
- **페이즈 6**: `static/js/common.js` (공통 Toast, 모달, 포맷터 유틸)
  - 6-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 6-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 6-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 6-4. 전역 네임스페이스 및 3대 표준 함수 주석 상세화
  - 6-5. DOM 제어 및 타이머 로직 흐름 주석화
- **페이즈 7**: `static/js/session_timer.js` (세션 타이머 및 자동 로그아웃)
  - 7-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 7-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 7-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 7-4. 세션 라이프사이클 3대 표준 주석 상세화
  - 7-5. 경고 모달/연장 API 통신/카운트다운 흐름 상세 주석화
- **페이즈 8**: `static/js/tailwindcss.js` (서드파티 Tailwind 번들)
  - 8-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 8-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 8-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 8-4. 파일 최상단 서드파티 라이브러리 식별 메타주석 1개 블록 부여 (내부 번들 코드 보존)
  - 8-5. 번들 로딩 및 전역 주입 흐름 주석화
- **페이즈 9**: `requirements.txt` (파이썬 의존성 패키지 목록)
  - 9-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 9-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 9-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 9-4. 파일 목적 메타주석 명시
  - 9-5. 패키지별 의존성 목적 및 역할 주석(`#`) 작성
- **페이즈 10**: `Resources/metadata/llms.txt` (LLM 에이전트 크롤러 컨텍스트)
  - 10-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 10-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 10-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 10-4. 메타데이터 규격 및 라우팅 안내 주석 상세화
  - 10-5. 컨텍스트 필드별 의미 및 서빙 흐름 주석화
- **페이즈 11**: `Resources/metadata/robots.txt` (검색엔진 크롤링 정책)
  - 11-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 11-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 11-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 11-4. 파일 목적 메타주석 명시
  - 11-5. 크롤링 차단/허용 디렉토리 정책 흐름 주석화
- **페이즈 12**: `Resources/metadata/security.txt` & `.well-known/security.txt` (RFC 9116 보안 연락처)
  - 12-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 12-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 12-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 12-4. RFC 9116 보안 텍스트 표준 규격 주석 상세화
  - 12-5. 보안 연락처 필드 및 이메일 하드코딩 흐름 주석화

---

### [그룹 C] 프론트엔드 UI 템플릿 (18개 HTML)
- **페이즈 13**: `templates/root_frame.html` (루트 통합 프레임셋)
  - 13-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 13-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 13-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 13-4. 3대 표준 메타주석 상세화
  - 13-5. 프레임셋 레이아웃 DOM 및 상태 전환 흐름 주석화
- **페이즈 14**: `templates/portal.html` (메인 서비스 런처 포털)
  - 14-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 14-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 14-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 14-4. 3대 표준 메타주석 상세화
  - 14-5. 포털 카드 및 라우팅 링크 흐름 주석화
- **페이즈 15**: `templates/index.html` (장비 통합 관리 메인 CRUD 화면)
  - 15-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 15-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 15-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 15-4. 3대 표준 메타주석 상세화
  - 15-5. 3-Tier 모달 폼, 카드 렌더러, 비동기 통신 흐름 주석화
- **페이즈 16**: `templates/dashboard.html` (통계 대시보드 화면)
  - 16-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 16-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 16-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 16-4. 3대 표준 메타주석 상세화
  - 16-5. 통계 집계 카드 및 차트 렌더링 흐름 주석화
- **페이즈 17**: `templates/admin_center.html` (관리자 중앙 제어 센터)
  - 17-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 17-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 17-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 17-4. 3대 표준 메타주석 상세화
  - 17-5. DB 백업/복원, 캐시 제어 통신 흐름 주석화
- **페이즈 18**: `templates/access_logs.html` (웹 접근 로그 실시간 뷰어)
  - 18-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 18-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 18-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 18-4. 3대 표준 메타주석 상세화
  - 18-5. 지연 로딩(Lazy Load), 필터링, 페이로드 모달 흐름 주석화
- **페이즈 19**: `templates/access_logs_error_ips.html` (에러 IP 집계 분석 뷰)
  - 19-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 19-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 19-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 19-4. 3대 표준 메타주석 상세화
  - 19-5. 4xx/5xx 에러 IP 통계 및 딥링크 연동 흐름 주석화
- **페이즈 20**: `templates/audit_logs.html` (시스템 감사 로그 뷰어)
  - 20-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 20-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 20-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 20-4. 3대 표준 메타주석 상세화
  - 20-5. 감사 추적 레코드 및 세부 변경 내역 모달 흐름 주석화
- **페이즈 21**: `templates/master_management.html` (마스터 기준정보 관리)
  - 21-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 21-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 21-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 21-4. 3대 표준 메타주석 상세화
  - 21-5. 제조사/카테고리 CRUD 통신 및 테이블 렌더링 흐름 주석화
- **페이즈 22**: `templates/users_management.html` (사용자 계정 관리)
  - 22-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 22-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 22-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 22-4. 3대 표준 메타주석 상세화
  - 22-5. 사용자 등급 변경, 계정 상태 토글 흐름 주석화
- **페이즈 23**: `templates/permissions.html` (권한 및 접근 제어 관리)
  - 23-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 23-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 23-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 23-4. 3대 표준 메타주석 상세화
  - 23-5. 권한 그룹별 메뉴 체크박스 매핑 및 저장 흐름 주석화
- **페이즈 24**: `templates/approvals.html` (가입 승인 및 결재 관리)
  - 24-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 24-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 24-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 24-4. 3대 표준 메타주석 상세화
  - 24-5. 가입 대기자 목록 조회 및 승인/반려 통신 흐름 주석화
- **페이즈 25**: `templates/login.html` (로그인 인증 화면)
  - 25-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 25-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 25-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 25-4. 3대 표준 메타주석 상세화
  - 25-5. 폼 유효성 검사 및 세션 발급 통신 흐름 주석화
- **페이즈 26**: `templates/register.html` (회원가입 화면)
  - 26-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 26-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 26-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 26-4. 3대 표준 메타주석 상세화
  - 26-5. 아이디 중복 확인 및 회원가입 신청 폼 흐름 주석화
- **페이즈 27**: `templates/reset_password.html` (비밀번호 재설정 화면)
  - 27-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 27-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 27-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 27-4. 3대 표준 메타주석 상세화
  - 27-5. 이메일 토큰 발송 및 신규 비밀번호 갱신 흐름 주석화
- **페이즈 28**: `templates/mypage.html` (마이페이지)
  - 28-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 28-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 28-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 28-4. 3대 표준 메타주석 상세화
  - 28-5. 개인정보 수정, 비밀번호 변경, 계정 탈퇴 처리 흐름 주석화
- **페이즈 29**: `templates/deactivated_notice.html` (계정 잠금 안내 화면)
  - 29-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 29-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 29-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 29-4. 3대 표준 메타주석 상세화
  - 29-5. 비활성화 상태 안내 및 로그아웃 버튼 흐름 주석화
- **페이즈 30**: `templates/miniserver_frame.html` (미니서버 모니터링 프레임)
  - 30-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 30-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 30-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 30-4. 3대 표준 메타주석 상세화
  - 30-5. iframe 임베드 및 로딩 상태 제어 흐름 주석화

---

### [그룹 D] 최종 무결성 검증, 보고서 작성 및 원격 반영
- **페이즈 31**: 전체 소스코드 구문 정합성 및 무결성 검증 (Validation)
  - 31-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 31-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 31-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 31-4. `app.py` 구문 정합성(python -m py_compile) 및 메타주석 무결성 검증
  - 31-5. `utils/mailer.py` 구문 정합성 및 메타주석 무결성 검증
  - 31-6. `utils/__init__.py` 구문 정합성 및 메타주석 무결성 검증
  - 31-7. `db_migration.py` 구문 정합성 및 메타주석 무결성 검증
  - 31-8. `down_migration.py` 구문 정합성 및 메타주석 무결성 검증
  - 31-9. `static/js/common.js` JS 구문 및 메타주석 무결성 검증
  - 31-10. `static/js/session_timer.js` JS 구문 및 메타주석 무결성 검증
  - 31-11. `static/js/tailwindcss.js` JS 구문 및 메타주석 무결성 검증
  - 31-12. `requirements.txt` 구문 무결성 검증
  - 31-13. `Resources/metadata/llms.txt` 포맷 무결성 검증
  - 31-14. `Resources/metadata/robots.txt` 포맷 무결성 검증
  - 31-15. `Resources/metadata/security.txt` 포맷 무결성 검증
  - 31-16. `templates/root_frame.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-17. `templates/portal.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-18. `templates/index.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-19. `templates/dashboard.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-20. `templates/admin_center.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-21. `templates/access_logs.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-22. `templates/access_logs_error_ips.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-23. `templates/audit_logs.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-24. `templates/master_management.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-25. `templates/users_management.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-26. `templates/permissions.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-27. `templates/approvals.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-28. `templates/login.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-29. `templates/register.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-30. `templates/reset_password.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-31. `templates/mypage.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-32. `templates/deactivated_notice.html` HTML 태그/주석 닫힘 및 무결성 검증
  - 31-33. `templates/miniserver_frame.html` HTML 태그/주석 닫힘 및 무결성 검증
- **페이즈 32**: 최종 완료 보고서 작성 (Completion Report)
  - 32-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 32-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 32-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 32-4. `proposal_code_comment_standardization_completion_report.md` 완료 보고서 작성 및 사용자 보고
- **페이즈 33**: 원격 반영 (Git Push)
  - 33-1. `GEMINI.md` 와 `Rule.md` 를 정독할 것
  - 33-2. `GEMINI.md` 와 `Rule.md` 를 준수할 것
  - 33-3. `GEMINI.md` 와 `Rule.md` 를 위배하지 말 것
  - 33-4. 사용자에게 Git Commit 메시지 확인 및 승인 요청
  - 33-5. `git add`, `git commit`, `git push origin main` 수행
