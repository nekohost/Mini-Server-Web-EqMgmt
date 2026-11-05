"""[MINI-COMMENT: ASSISTANT.POLISH.BROWSER.FIXTURE] [EN rev.1]
[Role] Exercises staged status, navigation, disclosure and portal presentation with deterministic synthetic transport.
[Dependencies] Reviewed lifecycle transport prefix, real-frame Linux Chromium capture and candidate template/assets.
[Impact] Uses no production accounts, database or provider calls; preserves existing functional suites and records measured cross-theme geometry.
"""
from assistant_ui_browser_fixture import run_ui_browser


def run_browser(project, assets):
    """[Role] Composes the existing in-memory transport with dedicated polish assertions at four viewport widths."""
    from viewport_scrollbar_browser_fixture import capture_real_frames
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    if 'MenuCards.orderPortal(menus)' not in assets['templates/portal.html']:
        raise ValueError('portal loader must use its scoped stable admin-last order')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 1234').replace('above_base: true', 'above_base: false')
    script = setup + assets['tests/test_ai_polish_layout_ui.js'] + '\nrunAiPolishLayoutFixture(server,cid,modelId,jid,sleep,theme);\n})();\n'
    return run_ui_browser(project, assets, script, sizes=(320,390,820,1440), themes=('light','dark'), capture=capture_real_frames)
