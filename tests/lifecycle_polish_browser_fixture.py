"""[MINI-COMMENT: ASSISTANT.POLISH.LIFECYCLE.BROWSER]
[EN rev.1]
[Role] Runs title and bulk-selection workflows in the real candidate DOM against a synthetic in-memory server.
[Dependencies] The established loopback Linux Chromium harness and separately reviewable JavaScript fixture.
[Impact] Tests both themes and required widths without any production login, database, worker or model call.
"""
import sys


def run_browser(project, assets):
    """[Role] Reuses the shared exact-viewport harness while choosing this feature's deterministic behavior script."""
    harness = sys.modules.get('assistant_ui_browser_fixture')
    if harness is None:
        import assistant_ui_browser_fixture as harness
    return harness.run_ui_browser(project, assets, assets['tests/test_ai_polish_lifecycle_ui.js'],
        sizes=(320, 390, 820, 1440), themes=('light', 'dark'))
