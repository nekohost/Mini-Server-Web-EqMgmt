"""[MINI-COMMENT: USER.PREFERENCES.BROWSER.FIXTURE] [EN rev.3]
[Role] Runs candidate account input shortcuts at exact mobile/desktop sizes in Linux Chromium.
[Dependencies] Reviewed loopback-only UI fixture, synthetic owner transport and native private-pipe keyboard delivery.
[Impact] Both settings, acceptance/initial-history/new-chat races, drafts and synthetic IME orders are verified without model calls, credentials or production database access.
"""
from assistant_ui_browser_fixture import run_ui_browser


def capture_keyboard(command, screenshot):
    """[Role] Sends real Enter/Shift+Enter to the focused synthetic frame through a private Chromium CDP pipe.
    [Dependencies] Reviewed isolated pipe transport, fixed Enter key fields and bounded same-origin fixture requests.
    [Impact] Native textarea editing and trusted keyboard events are exercised without a debugger TCP listener or production browser; all processes and descriptors are released.
    """
    import base64
    import fcntl
    import json
    import os
    import select
    import signal
    import subprocess
    import time

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
            """[Role] Correlates one bounded CDP reply while retaining diagnostic JavaScript exception events."""
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

        target = call('Target.createTarget', {'url': command[-1]})['targetId']
        session = call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        call('Runtime.enable', session=session)
        call('Page.enable', session=session)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            value = call('Runtime.evaluate', {'expression': "JSON.stringify({report:document.getElementById('browser-test-result')?.textContent || '',key:window.__aiInputKeyRequest || null})", 'returnByValue': True}, session)
            state = json.loads(value.get('result', {}).get('value') or '{}')
            key = state.get('key')
            if key:
                if type(key.get('id')) is not int or type(key.get('shift')) is not bool:
                    raise ValueError('invalid synthetic keyboard request')
                fields = {'key': 'Enter', 'code': 'Enter', 'windowsVirtualKeyCode': 13,
                          'nativeVirtualKeyCode': 13, 'modifiers': 8 if key['shift'] else 0}
                call('Input.dispatchKeyEvent', dict(fields, type='keyDown', text='\r', unmodifiedText='\r'), session)
                call('Input.dispatchKeyEvent', dict(fields, type='keyUp'), session)
                call('Runtime.evaluate', {'expression': "window.__aiInputKeyRequest=null;window.__aiInputKeyDone=" + str(key['id']), 'returnByValue': True}, session)
            if state.get('report'):
                break
            time.sleep(.05)
        else:
            raise TimeoutError('real-frame UI fixture did not complete; exceptions=' + repr(exceptions[-3:]))
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
    """[Role] Reuses reviewed synthetic transport for keyboard checks and separately held startup snapshots."""
    import json
    import os
    source = assets['tests/test_equipment_ai_ui.js']
    anchor = "    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor) != 1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup = source.split(anchor, 1)[0].replace('used_chars: 32000001', 'used_chars: 7025').replace('above_base: true', 'above_base: false')
    script = setup + assets['tests/test_ai_input_preferences.js'] + '\nrunAiInputPreferenceFixture(server,cid,modelId,sleep,theme);\n})();\n'
    results = run_ui_browser(project, assets, script, sizes=(320, 390, 412, 820, 1440), themes=('light', 'dark'), capture=capture_keyboard)
    race_sizes = tuple(json.loads(os.environ.get('EQ_FIXTURE_WIDTHS', '[]'))) or (320, 1440)
    for scenario in ('early-submit', 'history-view'):
        driver = '\nrunAiStartupRaceFixture(server,cid,modelId,sleep,theme,' + json.dumps(scenario) + ');\n})();\n'
        script = setup + assets['tests/test_ai_input_preferences.js'] + driver
        results.extend(run_ui_browser(project, assets, script, sizes=race_sizes, themes=('light', 'dark'), capture=capture_keyboard))
    return results

