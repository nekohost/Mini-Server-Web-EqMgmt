"""[MINI-COMMENT: ASSISTANT.STATUS.BANNER.BROWSER] [EN rev.1]
[Role] Verifies one server-evidence stream synchronizes the header and input-adjacent warning in actual Linux frames.
[Dependencies] Reviewed synthetic transport prefix, candidate status module and private CDP capture without external services.
[Impact] Checks TTL/races, safe text, announcement deduplication and responsive normal-flow space without production accounts, model requests or database access.
"""
from assistant_ui_browser_fixture import run_ui_browser


def run_browser(project, assets):
    """[Role] Composes a dedicated status/banner driver with the existing opt-in-free synthetic transport."""
    from viewport_scrollbar_browser_fixture import capture_real_frames
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 1234').replace('above_base: true', 'above_base: false')
    script = setup + assets['tests/test_ai_status_banner_ui.js'] + '\nrunAiStatusBannerFixture(server,cid,modelId,jid,sleep,theme);\n})();\n'
    return run_ui_browser(project, assets, script, sizes=(320,390,820,1440), themes=('light','dark'), capture=capture_real_frames)
