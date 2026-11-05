"""[MINI-COMMENT: ASSISTANT.RECOVERY.BROWSER] [EN rev.1]
[Role] Reproduces a stopped request and verifies authenticated terminal reconciliation in real candidate DOM.
[Dependencies] Existing synthetic owner transport, Linux Chromium and the reviewed real-frame capture.
[Impact] Does not use real accounts, release a guard, dispatch inference or modify production data.
"""
from assistant_ui_browser_fixture import run_ui_browser


def run_browser(project, assets):
    """[Role] Composes unchanged synthetic model/history routes with explicit stopped-request races."""
    from viewport_scrollbar_browser_fixture import capture_real_frames
    source=assets['tests/test_equipment_ai_ui.js']
    anchor="    document.addEventListener('DOMContentLoaded', async () => {"
    if source.count(anchor)!=1:
        raise ValueError('reviewed synthetic transport bootstrap changed')
    setup=source.split(anchor,1)[0].replace('used_chars: 32000001','used_chars: 7025').replace('above_base: true','above_base: false')
    script=setup+assets['tests/test_ai_recovery_ui.js']+'\nrunAiRecoveryFixture(server,cid,oldCid,modelId,jid,sleep,theme);\n})();\n'
    results=run_ui_browser(project,assets,script,sizes=(320,390,1440),themes=('light','dark'),capture=capture_real_frames)
    for item in results:
        item['template_mode']='current'
    cached=dict(assets)
    import re
    cached['templates/equipment_ai.html']=re.sub(r'<button type="button" id="ai-refresh-state"[^>]*>상태 다시 확인</button>','',assets['templates/equipment_ai.html'])
    if cached['templates/equipment_ai.html']==assets['templates/equipment_ai.html']:
        raise ValueError('cached-template compatibility control was not removed')
    legacy=run_ui_browser(project,cached,script,sizes=(320,390,1440),themes=('light','dark'),capture=capture_real_frames)
    for item in legacy:
        item['template_mode']='cached-before-recovery'
    return results+legacy
