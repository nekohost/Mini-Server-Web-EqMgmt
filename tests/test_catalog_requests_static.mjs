// 독립 카탈로그 신청과 장비/메뉴 UI 공통 규격의 정적 회귀 테스트입니다.
import test from 'node:test'; // Node 내장 테스트만 사용합니다.
import assert from 'node:assert/strict'; // 실패를 엄격하게 판정합니다.
import {readFileSync} from 'node:fs'; // 저장소 소스만 읽습니다.
import {fileURLToPath} from 'node:url'; // 프로젝트 상대 경로를 고정합니다.
import path from 'node:path'; // 플랫폼별 경로를 안전하게 결합합니다.
import vm from 'node:vm'; // 후보 JavaScript 문법을 서버 없이 검사합니다.

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'); // 프로젝트 루트입니다.
const read = name => readFileSync(path.join(root, name), 'utf8'); // UTF-8 원문을 읽습니다.

test('portal and admin use the same menu-grid contract', () => {
    const portal = read('templates/portal.html'); // 사용자 포털입니다.
    const admin = read('templates/admin_center.html'); // 관리자 포털입니다.
    assert.match(portal, /max-w-7xl/); // 관리자 센터와 같은 컨테이너 폭입니다.
    assert.match(portal, /id="menuContainer" class="menu-grid /); // 공통 카드 배열 클래스입니다.
    assert.match(admin, /id="admin-menus-grid" class="menu-grid /); // 관리자도 같은 클래스입니다.
});

test('equipment badges share one row below the equipment name', () => {
    const index = read('templates/index.html'); // 나의/공개 장비가 공유하는 템플릿입니다.
    const css = read('static/css/components.css'); // 컴포넌트 규격입니다.
    assert.match(index, /class="equipment-name[^>]*">\$\{escapeHtml\(item\.Name\)\}<\/div>/); // 이름은 독립 줄입니다.
    assert.match(index, /class="equipment-badges">\$\{badge\}\$\{window\.Roadmap\.badges\(item\)\}<\/div>/); // 공개·상태·기한을 같은 줄 컨테이너에 둡니다.
    assert.match(css, /\.app-badge, \.equipment-badges \.roadmap-badge/); // 기존 상태 배지도 공통 치수를 받습니다.
    assert.match(css, /--ui-badge-height: 1\.5rem/); // 정보 배지 기준 높이를 고정합니다.
});

test('catalog request UI is shared and does not gain approval actions', () => {
    const inbox = read('templates/my_approvals.html'); // 개인 결재함입니다.
    const index = read('templates/index.html'); // 장비 등록 화면입니다.
    const ui = read('static/js/catalog_requests.js'); // 공통 신청 모듈입니다.
    assert.match(inbox, /data-catalog-request-toolbar/); // 결재함에 독립 신청 진입점이 있습니다.
    assert.match(index, /data-catalog-request-toolbar/); // 장비 등록에도 같은 진입점이 있습니다.
    assert.match(ui, /CatalogRequests/); // 전역 공통 API를 한 번만 노출합니다.
    assert.match(ui, /\/api\/catalog_requests/); // 단일 접수 endpoint를 사용합니다.
    assert.match(ui, /getCSRFToken\(\)/); // 기존 CSRF helper를 사용합니다.
    assert.ok(!ui.includes('innerHTML')); // 신청서 입력과 서버 메시지를 HTML로 삽입하지 않습니다.
    assert.ok(!ui.includes('/process')); // 개인 화면에서 승인·반려 API를 호출하지 않습니다.
    new vm.Script(ui, {filename: 'catalog_requests.js'}); // 실제 운영 JS가 파싱되어야 합니다.
});

test('catalog request route keeps session actor, csrf and atomic audit before commit', () => {
    const route = read('utils/catalog_request_routes.py'); // HTTP 경계입니다.
    assert.match(route, /@login_required[\s\S]*@csrf_required[\s\S]*def create_request/); // 인증과 CSRF를 모두 요구합니다.
    assert.match(route, /session\.get\('user'\)/); // RequesterId를 본문에서 신뢰하지 않습니다.
    assert.match(route, /BEGIN IMMEDIATE/); // 중복 검사와 쓰기를 직렬화합니다.
    assert.ok(route.indexOf("audit(connection,") < route.indexOf('connection.commit()')); // 감사 성공 전 commit하지 않습니다.
    assert.match(route, /connection\.rollback\(\)/); // 예상 오류와 내부 오류 모두 rollback 경로가 있습니다.
});

test('root frame loads the shared component assets after existing base assets', () => {
    const rootFrame = read('templates/root_frame.html'); // 모든 인증 화면의 공통 frame입니다.
    assert.ok(rootFrame.indexOf("css/layout.css") < rootFrame.indexOf("css/components.css")); // 기존 레이아웃 후에 제한된 컴포넌트 규격을 적용합니다.
    assert.ok(rootFrame.indexOf('/static/js/common.js') < rootFrame.indexOf('/static/js/catalog_requests.js')); // CSRF helper가 먼저 정의됩니다.
});
