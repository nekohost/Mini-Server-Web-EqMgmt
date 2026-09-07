# WebMCP 선제 적용 구현 계획서

## 1. 배경

### 1-1. WebMCP란

WebMCP(Web Model Context Protocol)는 Chrome 149에서 Origin Trial로 시작된 W3C 커뮤니티 그룹 표준 초안이다. 웹사이트가 자신의 기능을 브라우저 내 AI 에이전트에게 **구조화된 도구(Tool)**로 노출하여, 에이전트가 DOM 스크래핑이나 컴퓨터 비전에 의존하지 않고 **정의된 함수를 호출**하여 작업을 수행할 수 있게 한다.

### 1-2. 적용 동기

현재 프로젝트에는 이미 `robots.txt`, `llms.txt`, `security.txt` 등 봇/AI 대응 메타데이터가 구현되어 있다([제안-038]). WebMCP는 이 연장선에서, AI 에이전트가 우리 시스템의 **장비 조회, 등록, 수정** 등의 기능을 안전하게 사용할 수 있도록 "안내"하는 선제적 대응이다.

### 1-3. WebMCP의 2개 API

| API | 방식 | 적합 용도 |
|---|---|---|
| **Declarative API** | HTML `<form>`에 `toolname`, `tooldescription` 등 속성 추가 | 기존 폼을 AI 도구로 노출 |
| **Imperative API** | JavaScript `document.modelContext.registerTool()` 호출 | 동적/복합 로직, REST API 래핑 |

---

## 2. 현재 시스템 현황

### 2-1. 기존 메타데이터 자산

| 파일 | 경로 | 역할 |
|---|---|---|
| robots.txt | `/robots.txt` | 검색 엔진 크롤러 선별 차단 |
| llms.txt | `/llms.txt` | AI 크롤러에 프로젝트 명세 안내 |
| security.txt | `/security.txt`, `/.well-known/security.txt` | 보안 제보 채널 안내 |

### 2-2. 동적 메타데이터 라우팅 엔진

`app.py`의 `register_dynamic_metadata_routes()` 함수가 `Resources/metadata/` 하위 파일을 자동 스캔하여 Flask URL 규칙으로 등록한다. 새 파일을 추가하면 코드 수정 없이 자동 라우팅된다.

### 2-3. 주요 HTML 폼

| 페이지 | 폼/기능 | 위치 |
|---|---|---|
| index.html | 장비 등록/수정 폼 (`#equipmentForm`) | `templates/index.html` |
| index.html | 사용자 검색 모달 | `templates/index.html` |
| login.html | 로그인 폼 | `templates/login.html` |
| register.html | 회원가입 폼 | `templates/register.html` |

---

## 3. 제안 변경 사항

### 3-1. 서버 사이드 디스커버리 — `/.well-known/webmcp.json`

> [!IMPORTANT]
> `/.well-known/webmcp.json`은 현재 W3C 표준의 정식 필수 항목이 아니라 커뮤니티 탐색 단계의 제안이다. 선제 적용의 목적에 부합하므로 포함하되, 표준 확정 시 스키마 변경이 필요할 수 있다.

#### [NEW] `Resources/metadata/.well-known/webmcp.json`

에이전트가 페이지 로드 전에 사이트의 도구 목록을 사전 발견할 수 있도록 하는 디스커버리 파일이다.

```json
{
  "name": "Mini-Server Equipment Manager",
  "description": "Personal equipment and asset management system on a local mini-server.",
  "version": "1.0.0",
  "tools": [
    {
      "name": "search_equipment",
      "description": "Search registered equipment by keyword (name, category, manufacturer, model).",
      "url": "/",
      "requires_auth": true
    },
    {
      "name": "add_equipment",
      "description": "Register a new equipment item with name, category, manufacturer, model, purchase date, serial number, and memo.",
      "url": "/",
      "requires_auth": true
    },
    {
      "name": "view_equipment_list",
      "description": "View the full list of registered equipment items.",
      "url": "/",
      "requires_auth": true
    }
  ],
  "authentication": {
    "type": "session",
    "login_url": "/login"
  },
  "contact": "mailto:nekohost@nekohost.org",
  "policy": {
    "robots_txt": "/robots.txt",
    "security_txt": "/.well-known/security.txt",
    "llms_txt": "/llms.txt"
  }
}
```

이 파일은 기존 동적 메타데이터 라우팅 엔진(`register_dynamic_metadata_routes`)에 의해 `/.well-known/webmcp.json` 경로로 자동 서빙된다. `.well-known/` 하위 디렉토리는 이미 `security.txt`용으로 존재하므로 추가 코드 변경이 불필요하다.

---

### 3-2. Declarative API — 장비 등록 폼 어노테이션

#### [MODIFY] `templates/index.html`

기존 `#equipmentForm`에 WebMCP Declarative API 속성을 추가한다. `toolautosubmit`은 **의도적으로 생략**하여 에이전트가 폼을 채우되, 최종 제출은 반드시 사용자가 수행하도록 한다.

**변경 전:**
```html
<form id="equipmentForm" class="p-6">
```

**변경 후:**
```html
<form id="equipmentForm" class="p-6"
      toolname="add_equipment"
      tooldescription="Register or edit personal equipment. Agent fills the form; human must click submit.">
```

각 `<input>`, `<select>` 요소에 `toolparamdescription` 속성 추가:

```html
<input type="text" name="name" toolparamdescription="Equipment nickname or alias" ... />
<select name="category" toolparamdescription="Equipment category (e.g., Laptop, Monitor, Battery)" ... />
<input type="text" name="manufacturer" toolparamdescription="Manufacturer name" ... />
<input type="text" name="model_name" toolparamdescription="Model name or number" ... />
<input type="date" name="purchase_date" toolparamdescription="Purchase date (YYYY-MM-DD)" ... />
<input type="text" name="serial_number" toolparamdescription="Serial number" ... />
<textarea name="memo" toolparamdescription="Additional notes or memo" ... />
```

> [!NOTE]
> 이 속성들은 WebMCP를 지원하지 않는 브라우저에서 무시되므로, 기존 기능에 영향이 없는 **순수 점진적 향상(progressive enhancement)**이다.

---

### 3-3. Imperative API — 장비 조회 도구 등록

#### [MODIFY] `templates/index.html` 또는 [NEW] `static/js/webmcp-tools.js`

REST API를 래핑하여 에이전트가 장비 목록을 조회할 수 있도록 한다.

```javascript
// WebMCP Imperative API - 장비 조회 도구 등록
// [역할]: AI 에이전트가 장비 검색/조회를 구조화된 함수 호출로 수행
// [의존성 관계]: /api/equipment (GET), 로그인 세션 필요
// [변경 시 영향도]: API 엔드포인트 변경 시 이 파일의 fetch URL 동시 수정 필요

if ('modelContext' in document) {
  // 장비 목록 조회 도구
  document.modelContext.registerTool({
    name: "search_equipment",
    description: "Search registered equipment items. Returns a list of equipment matching the query.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Search keyword to filter equipment by name, category, manufacturer, or model. Leave empty to list all."
        }
      },
      required: []
    },
    async execute({ query }) {
      try {
        const response = await fetch('/api/equipment');
        if (!response.ok) {
          return { error: `Server returned ${response.status}. User may need to log in first.` };
        }
        const equipment = await response.json();
        if (query) {
          const q = query.toLowerCase();
          const filtered = equipment.filter(item =>
            (item.name || '').toLowerCase().includes(q) ||
            (item.category || '').toLowerCase().includes(q) ||
            (item.manufacturer || '').toLowerCase().includes(q) ||
            (item.model_name || '').toLowerCase().includes(q)
          );
          return { results: filtered, total: filtered.length };
        }
        return { results: equipment, total: equipment.length };
      } catch (e) {
        return { error: e.message };
      }
    }
  });
}
```

---

### 3-4. `llms.txt` 업데이트

#### [MODIFY] `Resources/metadata/llms.txt`

WebMCP 지원 사실을 AI 크롤러에 안내한다.

**추가 내용:**
```text
## AI Agent Integration
This site supports WebMCP (Web Model Context Protocol).
- Discovery: /.well-known/webmcp.json
- Declarative tools: Equipment registration form (toolname="add_equipment")
- Imperative tools: Equipment search (document.modelContext)
- Authentication required: Yes (session-based login at /login)
- Auto-submit: Disabled. Agents populate forms; humans confirm submission.
```

---

### 3-5. 로그인/회원가입 폼 — 의도적 제외

> [!WARNING]
> `/login`, `/register` 폼에는 WebMCP 속성을 **추가하지 않는다.** `robots.txt`에서 이미 차단 중이며, 인증 폼을 AI 도구로 노출하면 brute-force 공격 표면이 확대된다. 이는 Rule.md 제4-5조(보안 및 환경 설정)에 의거한 판단이다.

---

## 4. 파일 변경 요약

### 메타데이터

#### [NEW] `Resources/metadata/.well-known/webmcp.json`
- WebMCP 디스커버리 파일. 도구 목록, 인증 요구사항, 관련 정책 파일 링크 포함.
- 기존 동적 라우팅 엔진에 의해 `/.well-known/webmcp.json`으로 자동 서빙.

#### [MODIFY] `Resources/metadata/llms.txt`
- WebMCP 지원 정보 섹션 추가.

---

### 프론트엔드

#### [MODIFY] `templates/index.html`
- `#equipmentForm`에 `toolname`, `tooldescription` 속성 추가 (Declarative API).
- 각 입력 요소에 `toolparamdescription` 속성 추가.
- `toolautosubmit` 의도적 생략 (사용자 확인 필수).

#### [NEW] `static/js/webmcp-tools.js`
- Imperative API로 `search_equipment` 도구 등록.
- `document.modelContext` feature detection 포함.
- `index.html`에서 `<script src>` 로드.

---

### 백엔드 (app.py)

**변경 없음.** 기존 `register_dynamic_metadata_routes()` 함수가 `.well-known/webmcp.json`을 자동 서빙하므로 백엔드 코드 수정이 불필요하다.

---

## 5. 보안 고려사항

| 항목 | 대응 |
|---|---|
| 인증 폼 노출 금지 | `/login`, `/register` 폼에 WebMCP 속성 미적용 |
| 자동 제출 방지 | `toolautosubmit` 속성 생략 → 사용자 최종 확인 필수 |
| 세션 의존 | 모든 도구가 로그인 세션 필요. 미인증 시 에이전트에 에러 반환 |
| 에이전트 입력 검증 | 에이전트 입력은 사용자 입력과 동일하게 불신. 기존 서버측 검증 유지 |
| HTTPS 요구 | WebMCP API는 Secure Context 필요. 현재 내부 네트워크 HTTP 운영이므로 Origin Trial 등록 또는 향후 HTTPS 전환 시 활성화 |

---

## 6. 긍정적 측면

1. **기존 인프라 재사용**: `register_dynamic_metadata_routes()`가 새 파일을 자동 서빙하므로 백엔드 변경 없이 디스커버리 파일 추가 가능.
2. **점진적 향상**: WebMCP 미지원 브라우저에서 속성이 무시되므로 기존 사용자 경험에 영향 없음.
3. **선제 표준 대응**: AI 에이전트의 웹 접속이 일반화되기 전에 구조화된 도구 노출 체계를 갖춤.
4. **보안 계층 유지**: `toolautosubmit` 생략과 인증 폼 제외로 기존 보안 정책과 일관.

## 7. 부정적 측면 / 리스크

1. **표준 미확정**: WebMCP는 Origin Trial 단계이며 W3C 초안이다. API가 `navigator.modelContext`에서 `document.modelContext`로 변경된 이력이 있으며, 향후 추가 변경 가능성이 있다.
2. **Chrome 전용**: 현재 Chrome 149+ 에서만 지원. Firefox, Safari, Edge는 관망 중이다. 우리 시스템이 내부 네트워크 전용이므로 실질적 영향은 제한적이나, 에이전트 브라우저가 Chrome이 아닌 경우 무용.
3. **HTTP 환경 제약**: WebMCP는 Secure Context(HTTPS)를 요구한다. 현재 `http://192.168.0.166:5000`으로 운영 중이므로, HTTPS 전환 없이는 실제 에이전트 연동이 제한될 수 있다.
4. **`/.well-known/webmcp.json` 스키마 미확정**: 커뮤니티 제안 수준이므로 표준 확정 시 형식 변경이 필요할 수 있다.

---

## 8. 검증 계획

### 자동 검증
- Staging에 변경 파일 배치 후 정적 검증 수행.
- `webmcp.json`의 JSON 유효성 검사.
- `index.html` 변경 후 기존 폼 동작이 깨지지 않는지 확인 (WebMCP 속성은 기존 동작에 무영향이므로 비파괴적).

### 수동 검증
- Chrome 149+ 에서 `document.modelContext`가 존재하는지 콘솔에서 확인.
- (가능 시) Model Context Tool Inspector 확장으로 등록된 도구 목록 확인.
- 미지원 브라우저에서 기존 폼이 정상 동작하는지 확인.

---

## 9. 작업 순서

1. `Resources/metadata/.well-known/webmcp.json` 생성
2. `Resources/metadata/llms.txt`에 WebMCP 섹션 추가
3. `static/js/webmcp-tools.js` 생성 (Imperative API)
4. `templates/index.html`의 `#equipmentForm`에 Declarative API 속성 추가
5. `templates/index.html`에 `webmcp-tools.js` 스크립트 로드 추가
6. Staging 배치 및 정적 검증
7. FEATURES.md / PROPOSALS.md 업데이트

---

## 문서 상태

- 상태: 사용자 승인 대기
- 참조 표준: [WebMCP | Chrome for Developers](https://developer.chrome.com/docs/ai/webmcp)
- 관련 기존 제안: [제안-038] 동적 메타데이터 라우팅
- Rule.md 준수 확인: 제4-5조(보안), 제7-3조(Staging), 제8-2조(구조화된 편집)

