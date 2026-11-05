"""[MINI-COMMENT: ASSISTANT.WEB.BROWSER] [EN rev.1]
[Role] Checks explicit search consent and safe persistent sources in the actual candidate UI at real animation frames.
[Dependencies] Existing synthetic transport and private loopback Chromium; no production accounts/search/model/data.
[Impact] Covers narrow/desktop light/dark geometry, hostile evidence text, version ACK and source state through reload/model switches.
"""
from assistant_ui_browser_fixture import run_ui_browser


def run_browser(project, assets):
    """[Role] Composes the reviewed transport with the dedicated search driver without changing production state."""
    from viewport_scrollbar_browser_fixture import capture_real_frames
    source=assets['tests/test_equipment_ai_ui.js']
    anchor="    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor)!=1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup=source.split(anchor,1)[0].replace('used_chars: 32000001','used_chars: 1234').replace('above_base: true','above_base: false')
    script=setup+assets['tests/test_ai_web_search_ui.js']+'\nrunAiWebSearchFixture(server,cid,oldCid,modelId,jid,sleep,theme);\n})();\n'
    return run_ui_browser(project,assets,script,sizes=(320,390,820,1440),themes=('light','dark'),capture=capture_real_frames)
