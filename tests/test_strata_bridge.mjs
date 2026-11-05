/* [MINI-COMMENT: STRATA.RETIREMENT.STATIC.TEST]
 * [EN rev.1]
 * [Role] Checks deployed-source retirement contracts in place of executing the removed browser bridge.
 * [Dependencies] Node test/assert/fs; the real URL/auth denial behavior is covered by Linux Flask tests.
 * [Impact] Does not call shared models or manipulate browser-local conversations.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

/** [Role] Reads only the source tree containing this test, without a production API call. */
const source = name => readFileSync(new URL('../' + name, import.meta.url), 'utf8');

test('retirement notice links to assistant without loading the old bridge or iframe', () => {
    const html = source('templates/strata_retired.html');
    assert.match(html, /href="\/assistant"/);
    assert.doesNotMatch(html, /<iframe|strata_bridge\.js|strata_page\.js|vendor\/strata\//);
});

test('dedicated Nginx candidate has only terminal legacy locations', () => {
    const active = source('systemd/nginx-strata.conf.example').split('\n').filter(line => !line.trim().startsWith('#')).join('\n');
    assert.doesNotMatch(active, /\b(?:proxy_pass|auth_request|include)\b/);
    assert.match(active, /location \^~ \/strata\//);
    assert.match(active, /location = \/_eqmgmt_strata_auth \{ return 410;/);
});

test('removal manifest preserves private keys, assistant runtime, attribution and browser history', () => {
    const manifest = JSON.parse(source('docs/strata-retirement-manifest.json'));
    for (const name of manifest.remove_public_files_after_denial) {
        assert(!name.includes('..') && !name.includes('*') && !name.startsWith('/'));
        assert(!manifest.preserve_attribution_in_repository.includes(name));
        assert(!name.startsWith('utils/ai_assistant/') && !name.startsWith('instance/'));
    }
    assert(manifest.preserve_runtime_paths_or_names.includes('USER_AI_*'));
    assert.match(manifest.browser_history, /Do not delete or merge/);
});
