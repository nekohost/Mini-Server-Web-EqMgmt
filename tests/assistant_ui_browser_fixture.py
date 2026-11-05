"""[MINI-COMMENT: ASSISTANT.UI.LIFECYCLE.BROWSER.FIXTURE]
[EN rev.7]
[Role] Runs the candidate chat UI in isolated Linux Chromium with synthetic transport and two same-origin tabs.
[Dependencies] Flask/Jinja, Linux Chromium, candidate asset strings and test_equipment_ai_ui.js supplied by the caller.
[Impact] Exercises narrow cover-screen384/412px and existing320/360/390/430/760/761/820/1440 CSS-pixel viewports in both themes, rejects requested/actual width mismatches and permits a1425px baseline comparison without production authentication, model calls or real database writes.
"""
import base64
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.serving import make_server


def run_browser(project, assets):
    """[MINI-COMMENT: ASSISTANT.UI.BROWSER.REAL.FRAMES] [EN rev.1]
    [Role] Runs the existing JavaScript regression checks on actual animation frames, including live thought opening.
    [Dependencies] The reviewed viewport fixture's private Linux CDP capture and run_ui_browser's existing width/theme filters.
    [Impact] Virtual-time timers cannot skip intermediate presenter frames; feature assertions and synthetic data remain unchanged.
    """
    from viewport_scrollbar_browser_fixture import capture_real_frames
    script = assets.get("tests/test_equipment_ai_ui.js")
    if script is None:
        path = Path(project) / "tests/test_equipment_ai_ui.js"
        if not path.is_file():
            path = Path(project) / "Staging/20261105-ai-ux-trash/tests/test_equipment_ai_ui.js"
        script = path.read_text(encoding="utf-8-sig")
    return run_ui_browser(project, assets, script, capture=capture_real_frames)


def run_ui_browser(project, assets, script, sizes=(320, 360, 384, 390, 412, 430, 760, 761, 820, 1440), themes=("light", "dark"), capture=None):
    """[Role] Serves loopback candidate UI and supports a reviewed real-frame capture for geometry-sensitive checks."""
    selected_widths = json.loads(os.environ.get('EQ_FIXTURE_WIDTHS', '[]'))
    selected_themes = json.loads(os.environ.get('EQ_FIXTURE_THEMES', '[]'))
    sizes = tuple(width for width in sizes if not selected_widths or width in selected_widths)
    themes = tuple(theme for theme in themes if not selected_themes or theme in selected_themes)
    if not sizes or not themes:
        raise ValueError('requested fixture width/theme is not covered by this suite')
    app = Flask("assistant_ui_lifecycle_fixture", static_folder=None)
    app.secret_key = "synthetic-ui-fixture-not-a-production-key"
    app.jinja_loader = ChoiceLoader([
        DictLoader({key.removeprefix("templates/"): value for key, value in assets.items() if key.startswith("templates/")}),
        FileSystemLoader(Path(project) / "templates"),
    ])

    @app.get("/static/<path:filename>", endpoint="static")
    def static(filename):
        """[Role] Prefers candidate assets and otherwise reads existing static dependencies."""
        key = "static/" + filename
        if key in assets:
            return Response(assets[key], content_type="text/css" if filename.endswith(".css") else "application/javascript")
        return send_from_directory(Path(project) / "static", filename)

    @app.get("/")
    def page():
        """[Role] Injects the deterministic browser fixture before the actual candidate client loads."""
        markup = render_template("equipment_ai.html", user={"NickName": "격리 회귀", "Role": "user"}, assistant_csrf="fixture-csrf", csrf_token="fixture-csrf")
        markup = markup.replace('src="https://cdn.tailwindcss.com"', 'src="/static/js/tailwindcss.js"')
        anchor = '<script src="/static/js/equipment_ai.js"'
        if anchor not in markup:
            raise ValueError("assistant fixture script anchor missing")
        markup = markup.replace(anchor, "<script>" + script.replace("</script", "<\\/script") + "</script>" + anchor)
        response = Response(markup, content_type="text/html; charset=utf-8")
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self'; font-src 'none'; img-src 'self' data:"
        return response

    @app.get("/viewport")
    def viewport():
        """[Role] Creates an exact child viewport below Chromium's minimum top-window width."""
        width = int(request.args.get("width", "430"))
        if width not in (320, 360, 384, 390, 412, 430, 760, 761, 820, 1425, 1440):
            return Response("unsupported fixture width", status=400)
        theme = "dark" if request.args.get("theme") == "dark" else "light"
        markup = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;background:#e9edf2;display:flex;justify-content:center"><iframe id="fixture-viewport" title="격리 UI 회귀" src="/?theme=THEME" style="width:WIDTHpx;height:1000px;flex:none;border:0;background:white"></iframe><pre id="browser-test-result" hidden></pre><script>addEventListener('message',event=>{if(event.origin===location.origin&&event.source===document.getElementById('fixture-viewport').contentWindow&&event.data.fixtureResult)document.getElementById('browser-test-result').textContent=event.data.fixtureResult;});</script></body></html>'''
        return Response(markup.replace("WIDTH", str(width)).replace("THEME", theme), content_type="text/html; charset=utf-8")

    @app.get("/api/check_session")
    def session():
        """[Role] Supplies the independent frame session check without a real login."""
        return jsonify(valid=True)

    @app.get("/api/user_settings")
    def preferences():
        """[Role] Keeps synthetic server preferences consistent with the requested theme without opening a database."""
        theme = parse_qs(urlsplit(request.referrer or "").query).get("theme", ["light"])[0]
        return jsonify(success=True, settings={"theme": "dark" if theme == "dark" else "light"})

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        for width in sizes:
            for theme in themes:
                with tempfile.TemporaryDirectory(prefix="eq-assistant-ui-") as tmp:
                    screenshot = Path(tmp) / "screen.png"
                    command = ["/usr/bin/chromium", "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--no-proxy-server", "--disable-background-networking", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--user-data-dir=" + str(Path(tmp) / "profile"), "--window-size=" + str(max(width + 40, 500)) + ",1100", "--virtual-time-budget=30000", "--screenshot=" + str(screenshot), "--dump-dom", "http://127.0.0.1:" + str(server.server_port) + "/viewport?width=" + str(width) + "&theme=" + theme]
                    process = capture(command, screenshot) if capture else subprocess.run(command, capture_output=True, text=True, timeout=50)
                    match = re.search(r'<pre id="browser-test-result"[^>]*>(.*?)</pre>', process.stdout, re.S)
                    result = json.loads(html.unescape(match[1])) if match and match[1] else {"status": "fail", "error": "UI browser fixture did not complete"}
                    actual_width = result.get("width")
                    result.update(requested_width=width, requested_theme=theme, exit_code=process.returncode)
                    if actual_width != width:
                        prior_error = result.get("error")
                        result["status"] = "fail"
                        result["error"] = f"UI browser viewport mismatch: requested {width}px, actual {actual_width}px" + ("; " + prior_error if prior_error else "")
                    if screenshot.exists():
                        result["screenshot"] = base64.b64encode(screenshot.read_bytes()).decode()
                    results.append(result)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    return results
