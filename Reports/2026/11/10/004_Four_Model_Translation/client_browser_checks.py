"""Run the three browser-only drivers on isolated Flask pages in Linux Chromium."""
from pathlib import Path
import base64
import importlib
import json
import os
import sys

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root/'tests'))
os.environ['EQ_FIXTURE_WIDTHS'] = '[390,1440]'
os.environ['EQ_FIXTURE_THEMES'] = '["light"]'
assets = {name:(root/name).read_text(encoding='utf-8-sig') for name in
          ('templates/portal.html','tests/test_equipment_ai_ui.js','tests/test_ai_polish_lifecycle_ui.js','tests/test_portal_polish_ui.js')}
summary = {}
for name in ('assistant_ui_browser_fixture','lifecycle_polish_browser_fixture','portal_polish_browser_fixture'):
    try:
        results = importlib.import_module(name).run_browser(root, assets)
    except Exception as exc:
        results = [{'status':'fail','error':str(exc)}]
    for row in results:
        data = row.pop('screenshot', None)
        if data:
            (out/(name+'-'+str(row['requested_width'])+'.png')).write_bytes(base64.b64decode(data))
    summary[name] = results
    (out/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print({k:[(v.get('requested_width'),v.get('status'),v.get('error','')) for v in vs] for k,vs in summary.items()})
