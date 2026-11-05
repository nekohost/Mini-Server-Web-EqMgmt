"""Retirement boundary for the former equipment-management Strata browser UI.

[MINI-COMMENT: STRATA.INTEGRATION]
[EN rev.2]
[Role] Keeps authenticated retirement notices and denies every legacy browser gateway.
[Dependencies] Existing login validation and a static retirement template; no network client or UI flags.
[Impact] Preserves new assistant adapters, private keys, stored history and shared model services.
"""
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, render_template, request, session

MENU_CODE = 'strata'
RETIRED_ASSETS = frozenset({
    '/static/js/strata_page.js', '/static/js/strata_bridge.js', '/static/css/strata.css',
})


def visible_portal_menus(rows, role, config):
    """[Role] Always hides the retired menu, including administrators who bypass grants.
    [Dependencies] Existing menu rows; legacy enabled flags are deliberately ignored.
    [Impact] Preserves every other menu and does not mutate metadata or role permissions.
    """
    return [dict(row) for row in rows if row['MenuCode'] != MENU_CODE]


def request_allowed(method, original_uri):
    """[MINI-COMMENT: STRATA.PROXY.PATHS]
    [EN rev.2]
    [Role] Denies all former upstream paths and methods after retirement.
    [Dependencies] Kept as a fail-closed compatibility function for old integrations.
    [Impact] No stale flag, cookie, path encoding or CSRF header can reenable the gateway.
    """
    return False


def canonical_origin(value):
    """[Role] Retains the former pure origin parser for source compatibility.
    [Dependencies] urlsplit only; this parser does not authorize any retired request.
    [Impact] Existing imports remain safe without contacting a provider.
    """
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.path or parsed.query or parsed.fragment:
            return None
        return parsed.scheme.lower(), parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == 'https' else 80)
    except (ValueError, TypeError):
        return None


def register_menu(get_connection):
    """[MINI-COMMENT: STRATA.MENU.REGISTER]
    [EN rev.2]
    [Role] Retains an inert compatibility entry point; retired menus/grants are never seeded.
    [Dependencies] The former connection argument is intentionally never invoked.
    [Impact] Existing metadata remains available for audited backup and explicit later cleanup.
    """
    return None


def upstream_health(url):
    """[Role] Fails closed for callers left over from the removed UI health checker.
    [Dependencies] No network library or upstream configuration is read.
    [Impact] Retirement cannot create hidden LAN health requests or expose private addresses.
    """
    raise RuntimeError('The equipment Strata browser gateway has been retired')


def install_strata(app, get_connection, login_required, check_permission):
    """[MINI-COMMENT: STRATA.ROUTES.INSTALL]
    [EN rev.2]
    [Role] Installs authenticated notices plus unconditional API/proxy/static tombstones.
    [Dependencies] Existing login_required; old menu grants and enabled settings confer no access.
    [Impact] No legacy request reaches upstream; new assistant and other services stay independent.
    """
    blueprint = Blueprint('strata_admin', __name__)

    @blueprint.after_request
    def private_response(response):
        """[Role] Prevents caching and framing of retired responses.
        [Dependencies] This retirement blueprint only.
        [Impact] No model addresses, tokens or old browser-storage namespace are emitted.
        """
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
            'X-Content-Type-Options': 'nosniff',
        })
        return response

    @blueprint.get('/ai')
    @login_required
    def page():
        """[Role] Shows the replacement assistant link after current-login validation.
        [Dependencies] A dedicated retirement template, without iframe or legacy assets.
        [Impact] Does not convert old prompts or clear local browser conversations.
        """
        return render_template('strata_retired.html', user=session['user'])

    @blueprint.get('/ai/console')
    @login_required
    def console():
        """[MINI-COMMENT: STRATA.CONSOLE.CONTEXT]
        [EN rev.2]
        [Role] Replaces the old embedded console with the same authenticated retirement notice.
        [Dependencies] Existing live login and the replacement assistant URL.
        [Impact] No namespace, raw token, CSRF bridge or legacy JavaScript is emitted.
        """
        return render_template('strata_retired.html', user=session['user'])

    @blueprint.route('/api/strata/status', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
    def status():
        """[Role] Returns a terminal retirement response without running a health check.
        [Dependencies] No account, menu flag, provider or network client.
        [Impact] Stale health clients cannot reach shared Strata.
        """
        return jsonify(success=False, state='retired', message='기존 Strata 웹 연결은 종료되었습니다. AI 도우미를 이용해 주세요.'), 410

    @blueprint.route('/api/strata/access', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
    def proxy_access():
        """[MINI-COMMENT: STRATA.PROXY.AUTHORIZE]
        [EN rev.2]
        [Role] Never authorizes an old Nginx auth subrequest, regardless of supplied headers.
        [Dependencies] No login grant, enabled flag, CSRF or upstream key.
        [Impact] A stale proxy include receives 410 instead of a successful 2xx authorization.
        """
        return '', 410

    @app.before_request
    def block_retired_gateway():
        """[MINI-COMMENT: STRATA.RETIREMENT.BLOCK]
        [EN rev.2]
        [Role] Denies all gateway aliases and publicly served legacy UI assets before routing.
        [Dependencies] Exact retired namespaces and a separately reviewed Nginx deny snippet.
        [Impact] Non-cacheable Flask fallback cannot serve old bridge/vendor UI while files await removal.
        """
        path = request.path
        if (path in ('/strata', '/api/strata', '/_eqmgmt_strata_auth', '/static/vendor/strata') or
                path.startswith(('/strata/', '/api/strata/', '/static/vendor/strata/')) or path in RETIRED_ASSETS):
            response = jsonify(success=False, state='retired', message='기존 Strata 웹 연결은 종료되었습니다.')
            response.status_code = 410
            response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            return response

    app.register_blueprint(blueprint)
