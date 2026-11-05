"""[MINI-COMMENT: PORTAL.POLISH.BROWSER.FIXTURE]
[EN rev.1]
[Role] Renders the actual candidate portal and authenticated frame with synthetic administrator menus.
[Dependencies] Shared loopback UI harness, real-frame Chromium capture and in-memory Jinja aliases only.
[Impact] Four width/theme views include the complete portal while production templates, authentication and databases remain untouched.
"""
from urllib.parse import parse_qs, urlsplit

from assistant_ui_browser_fixture import run_ui_browser
from viewport_scrollbar_browser_fixture import capture_real_frames


def capture_portal_frames(command, screenshot):
    """[Role] Gives the narrow full-page portal enough real viewport height for its existing card layout.
    [Dependencies] The shared isolated CDP capture and the already validated loopback URL width.
    [Impact] Only the disposable Chromium window height changes; candidate CSS and page sources are preserved.
    """
    width = int(parse_qs(urlsplit(command[-1]).query)['width'][0])
    height = 1900 if width == 390 else 1100
    expanded = [part.rsplit(',', 1)[0] + ',' + str(height) if part.startswith('--window-size=') else part for part in command]
    return capture_real_frames(expanded, screenshot)


def run_browser(project, assets):
    """[Role] Aliases the real portal into the shared renderer, setting only a synthetic administrator and injection anchor.
    [Dependencies] Candidate portal/frame/menu assets, Jinja inheritance and this suite's deterministic API driver.
    [Impact] The portal's own loaders/rendering execute unchanged; the unrelated AI client finds no assistant root and exits.
    """
    portal = assets['templates/portal.html']
    if 'MenuCards.orderPortal(menus)' not in portal:
        raise ValueError('candidate portal does not call its scoped admin-last ordering')
    candidate = dict(assets)
    candidate['templates/fixture_portal_polish.html'] = portal
    candidate['templates/equipment_ai.html'] = (
        "{% extends 'fixture_portal_polish.html' %}\n"
        "{% set user = {'NickName': '격리 관리자', 'Role': 'admin'} %}\n"
        "{% block extra_scripts %}{{ super() }}\n"
        '<script src="/static/js/equipment_ai.js" defer></script>\n'
        '{% endblock %}\n'
    )
    return run_ui_browser(project, candidate, assets['tests/test_portal_polish_ui.js'],
        sizes=(390, 1440), themes=('light', 'dark'), capture=capture_portal_frames)
