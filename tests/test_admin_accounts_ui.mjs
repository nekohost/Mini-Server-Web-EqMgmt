// ADMIN_ACCOUNTS_BROWSER=1 node --test tests/test_admin_accounts_ui.mjs
// Renders the real Jinja page and intercepts every request. No application or HTTP listener is started.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const root = fileURLToPath(new URL('../', import.meta.url));
const origin = 'https://accounts-fixture.invalid';
const render = `
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
env.globals['url_for'] = lambda name, **kw: '/static/' + kw['filename'] if name == 'static' else {'api_create_user':'/api/users/create','logout':'/logout'}[name]
print(env.get_template('users_management.html').render(user={'UserId':1,'Role':'admin','NickName':'관리자'}, csrf_token='fixture-token', can_create_user=True))
`;

for (const width of [320, 1280]) {
    test(`user creation, retry and single submission at ${width}px`, {
        skip: process.env.ADMIN_ACCOUNTS_BROWSER !== '1', timeout: 45000
    }, async t => {
        const html = execFileSync(process.env.PYTHON || 'python', ['-B', '-c', render], {
            cwd: root, encoding: 'utf8', env: {...process.env, PYTHONIOENCODING: 'utf-8'}
        });
        const {chromium} = createRequire(import.meta.url)('playwright');
        const browser = await chromium.launch({
            channel: process.env.CHROMIUM_CHANNEL || undefined,
            executablePath: process.env.CHROME_BIN || undefined
        });
        t.after(() => browser.close());
        const page = await browser.newPage({viewport: {width, height: width === 320 ? 568 : 800}});
        const pageErrors = [];
        page.on('pageerror', error => pageErrors.push(error.message));
        const attempts = [];
        let release;
        const pending = new Promise(resolve => { release = resolve; });
        let saved = false;
        await page.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin !== origin) return route.abort();
            if (url.pathname === '/users_management') return route.fulfill({contentType: 'text/html', body: html});
            if (/^\/static\/(js|css)\/[\w.-]+\.(js|css)$/.test(url.pathname)) {
                return route.fulfill({path: path.join(root, url.pathname.slice(1))});
            }
            if (url.pathname === '/api/users/create') {
                attempts.push({body: request.postDataJSON(), csrf: request.headers()['x-csrftoken'], method: request.method()});
                if (attempts.length === 1) return route.fulfill({status: 409, json: {success: false, message: '이미 사용 중인 아이디입니다.'}});
                await pending;
                saved = true;
                return route.fulfill({status: 201, json: {success: true, UserId: 2, message: '계정을 생성했습니다.'}});
            }
            if (url.pathname === '/api/users') {
                if (saved && width === 320) return route.fulfill({status: 500, json: {success: false}});
                return route.fulfill({json: {success: true, data: saved ? [{
                    UserId: 2, LoginId: 'new-account', NickName: '별명', Role: 'admin', Status: 'ACTIVE'
                }] : []}});
            }
            return route.fulfill({json: {valid: true, success: true, settings: {}}});
        });

        await page.goto(origin + '/users_management');
        await page.locator('#openCreateUser').click();
        const dialog = page.locator('#createUserDialog');
        const field = name => dialog.locator(`[name="${name}"]`);
        assert.equal(await field('Role').inputValue(), 'user');
        assert.equal(await field('Name').getAttribute('required'), null);
        assert.equal(await field('Password').getAttribute('type'), 'password');
        assert.ok(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1
            && el.getBoundingClientRect().width <= innerWidth && el.getBoundingClientRect().height <= innerHeight));
        await field('LoginId').fill('used-account');
        await field('NickName').fill('별명');
        await field('Password').fill('  Fixture9!account  ');
        await dialog.locator('[type=submit]').click();
        await page.getByRole('alert').filter({hasText: '이미 사용 중인'}).waitFor();
        assert.equal(await field('LoginId').inputValue(), 'used-account');
        await field('LoginId').fill('new-account');
        await field('Role').selectOption('admin');
        try {
            const request = page.waitForRequest(origin + '/api/users/create');
            await dialog.locator('form').evaluate(form => { form.requestSubmit(); form.requestSubmit(); });
            await request;
            assert.ok(await dialog.locator('[type=submit]').isDisabled());
            assert.ok(await page.locator('#global-loading-overlay').isVisible());
            await page.keyboard.press('Escape');
            assert.ok(await dialog.isVisible());
        } finally {
            release();
        }
        await dialog.waitFor({state: 'hidden'});
        if (width === 320) {
            await page.locator('#createUserResult').filter({hasText: '목록을 새로고침'}).waitFor();
        } else {
            await page.locator('#userTableBody').getByText('new-account').waitFor();
        }
        assert.deepEqual(attempts.map(a => [a.body.Role, a.csrf, a.method]), [
            ['user', 'fixture-token', 'POST'], ['admin', 'fixture-token', 'POST']
        ]);
        assert.equal(attempts[1].body.Password, '  Fixture9!account  ');
        assert.equal(page.url(), origin + '/users_management');
        await page.locator('#openCreateUser').click();
        assert.equal(await field('Role').inputValue(), 'user');
        assert.equal(await field('Password').inputValue(), '');
        await field('Password').fill('Cancel9!fixture');
        await page.keyboard.press('Escape');
        await dialog.waitFor({state: 'hidden'});
        await page.locator('#openCreateUser').click();
        assert.equal(await field('Password').inputValue(), '');
        assert.deepEqual(pageErrors, []);
    });
}
