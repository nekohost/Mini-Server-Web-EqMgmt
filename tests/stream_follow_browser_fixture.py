"""[MINI-COMMENT: ASSISTANT.STREAM.FOLLOW.BROWSER.FIXTURE]
[EN rev.1]
[Role] Runs the virtual-answer-model follow scenario in isolated Linux Chromium with trusted CDP mouse-wheel (PC) and touch-drag (mobile) input, one screenshot per frozen stage.
[Dependencies] The reviewed stream-polish synthetic transport prefix, test_ai_stream_follow_browser.js, run_ui_browser and a private Linux CDP pipe (stdlib only).
[Impact] Screenshots show following, detached and reattached reader states for the pane and the reasoning box; no debugger port, production account, model, service or database is used, and every process/descriptor is released.
"""
import base64
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
from urllib.parse import parse_qs, urlsplit

from assistant_ui_browser_fixture import run_ui_browser

STAGES = ('reasoning-follow', 'reasoning-detached', 'answer-detached', 'answer-reattached', 'complete')


def capture_scroll_input(command, screenshot):
    """[Role] Serves the driver's gesture requests as trusted CDP wheel or touch-drag input, then captures the frozen stage.
    [Dependencies] Linux stdlib descriptors and the driver's window.parent.__followAction / __followAck bridge.
    [Impact] Touch emulation is enabled only for the mobile width; the Chromium process group is always terminated.
    """
    incoming, send = os.pipe()
    receive, outgoing = os.pipe()
    child_in = fcntl.fcntl(incoming, fcntl.F_DUPFD_CLOEXEC, 10)
    child_out = fcntl.fcntl(outgoing, fcntl.F_DUPFD_CLOEXEC, 10)
    quiet = os.open(os.devnull, os.O_WRONLY)
    args = [part for part in command[:-1] if not part.startswith(('--virtual-time-budget=', '--screenshot=')) and part != '--dump-dom']
    args += ['--remote-debugging-pipe', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', 'about:blank']
    pid = None
    try:
        pid = os.posix_spawn(args[0], args, os.environ, file_actions=[
            (os.POSIX_SPAWN_DUP2, child_in, 3), (os.POSIX_SPAWN_DUP2, child_out, 4),
            (os.POSIX_SPAWN_DUP2, quiet, 1), (os.POSIX_SPAWN_DUP2, quiet, 2),
        ], setpgroup=0)
        os.close(incoming); incoming = None
        os.close(outgoing); outgoing = None
        serial, pending, exceptions = 0, b'', []

        def call(method, params=None, session=None):
            """[Role] Correlates one bounded CDP reply while retaining JavaScript exception diagnostics."""
            nonlocal serial, pending
            serial += 1
            message = {'id': serial, 'method': method, 'params': params or {}}
            if session:
                message['sessionId'] = session
            os.write(send, json.dumps(message).encode() + b'\0')
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if b'\0' not in pending:
                    if not select.select([receive], [], [], max(0, deadline - time.monotonic()))[0]:
                        break
                    chunk = os.read(receive, 65536)
                    if not chunk:
                        raise RuntimeError('isolated Chromium CDP pipe closed')
                    pending += chunk
                    continue
                raw, pending = pending.split(b'\0', 1)
                value = json.loads(raw)
                if value.get('method') == 'Runtime.exceptionThrown':
                    exceptions.append(value.get('params', {}).get('exceptionDetails', {}).get('text', 'JavaScript exception'))
                if value.get('id') == serial:
                    if 'error' in value:
                        raise RuntimeError(str(value['error']))
                    return value.get('result', {})
            raise TimeoutError('isolated Chromium CDP reply timed out: ' + method)

        target = call('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        call('Runtime.enable', session=session)
        call('Page.enable', session=session)
        width = int(parse_qs(urlsplit(command[-1]).query)['width'][0])
        mobile = width <= 760
        if mobile:
            call('Emulation.setDeviceMetricsOverride', {'width': width, 'height': 900, 'deviceScaleFactor': 3, 'mobile': True, 'screenWidth': width, 'screenHeight': 900}, session)
            call('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 5}, session)
        call('Page.navigate', {'url': command[-1]}, session)
        handled = None
        deadline = time.monotonic() + 110
        while time.monotonic() < deadline:
            state = call('Runtime.evaluate', {'expression': "({result:document.getElementById('browser-test-result')?.textContent||'',action:window.__followAction||null})", 'returnByValue': True}, session)['result'].get('value', {})
            if state.get('result'):
                break
            action = state.get('action')
            if action and action['id'] != handled:
                handled = action['id']
                x, y, distance = float(action['x']), float(action['y']), float(action['distance'])
                steps = max(4, min(24, int(abs(distance) // 12)))
                if action['kind'] == 'touch':
                    # Positive distance scrolls up, so the finger moves down the screen.
                    call('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'radiusX': 1, 'radiusY': 1}]}, session)
                    for step in range(1, steps + 1):
                        time.sleep(.016)
                        call('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y + distance * step / steps, 'radiusX': 1, 'radiusY': 1}]}, session)
                    time.sleep(.03)
                    call('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}, session)
                elif action['kind'] == 'wheel':
                    call('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y}, session)
                    for _ in range(steps):
                        call('Input.dispatchMouseEvent', {'type': 'mouseWheel', 'x': x, 'y': y, 'deltaX': 0, 'deltaY': -distance / steps}, session)
                        time.sleep(.016)
                else:
                    raise ValueError('unsupported follow fixture action')
                call('Runtime.evaluate', {'expression': 'window.__followAck=' + json.dumps(handled)}, session)
            time.sleep(.01)
        else:
            raise TimeoutError('follow fixture did not complete; exceptions=' + repr(exceptions[-3:]))
        markup = call('Runtime.evaluate', {'expression': 'document.documentElement.outerHTML', 'returnByValue': True}, session)['result']['value']
        capture = call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False}, session)
        screenshot.write_bytes(base64.b64decode(capture['data']))
        return subprocess.CompletedProcess(args, 0, markup, '')
    finally:
        if pid is not None:
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        for descriptor in (incoming, send, receive, outgoing, child_in, child_out, quiet):
            if descriptor is not None:
                os.close(descriptor)


def run_browser(project, assets):
    """[Role] Reuses the transport prefix unchanged and appends the follow driver for every stage, width and theme."""
    def read(relative):
        value = assets.get(relative)
        return value if value is not None else (Path(project) / relative).read_text(encoding='utf-8-sig')

    transport = read('tests/test_stream_polish_browser.js')
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if transport.count(anchor) != 1:
        raise ValueError('reviewed stream transport bootstrap changed')
    prefix = transport.split(anchor, 1)[0]
    driver = read('tests/test_ai_stream_follow_browser.js')
    results = []
    for stage in STAGES:
        script = prefix + '    window.__streamFollowStage = ' + json.dumps(stage) + ';\n' + driver
        # Every check runs in both themes on the complete pass; frozen screenshot stages use the light theme to bound runtime.
        themes = ('light', 'dark') if stage == 'complete' else ('light',)
        for item in run_ui_browser(project, assets, script, sizes=(390, 1440), themes=themes, capture=capture_scroll_input):
            item['view'] = 'stream-follow-' + stage
            results.append(item)
    return results
