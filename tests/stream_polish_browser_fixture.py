"""[MINI-COMMENT: ASSISTANT.STREAM.POLISH.BROWSER.FIXTURE]
[EN rev.1]
[Role] Measures the actual integrated chat/presenter/Markdown DOM using real Linux Chromium frames.
[Dependencies] Existing loopback UI fixture, reviewed private-pipe capture and a separate synthetic transport/driver.
[Impact] Covers mobile/desktop and both themes without a production account, model or database; screenshots are distinct from recorded frame/cost evidence.
"""
from pathlib import Path

from assistant_ui_browser_fixture import run_ui_browser
from viewport_scrollbar_browser_fixture import capture_real_frames


def run_browser(project, assets):
    """[Role] Injects only reviewed synthetic checks while running the candidate's real main JavaScript and safe renderer."""
    script = assets.get("tests/test_stream_polish_browser.js")
    if script is None:
        script = (Path(project) / "tests/test_stream_polish_browser.js").read_text(encoding="utf-8-sig")
    if "static/js/ai_stream_presenter.js" not in assets:
        raise ValueError("stream fixture requires the candidate presenter asset")
    return run_ui_browser(project, assets, script, sizes=(390, 1440), themes=("light", "dark"), capture=capture_real_frames)
