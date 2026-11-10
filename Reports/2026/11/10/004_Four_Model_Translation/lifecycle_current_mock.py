"""Replay the existing browser assertions with the resume field supplied by the current API."""
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'tests'))
from assistant_ui_browser_fixture import run_ui_browser
from viewport_scrollbar_browser_fixture import capture_real_frames

driver = (root/'tests/test_ai_polish_lifecycle_ui.js').read_text()
before = 'conversations: clone(items.slice(offset, offset + 2)),'
after = "resume_conversation: view === 'active' && url.searchParams.get('resume') === '1' ? clone(items[0] || null) : null, " + before
assert driver.count(before) == 1
results = run_ui_browser(root,{},driver.replace(before,after,1),sizes=(390,1440),themes=('light',),capture=capture_real_frames)
for row in results:
    row.pop('screenshot',None)
Path(sys.argv[2]).write_text(json.dumps(results,ensure_ascii=False,indent=2))
print([(row['requested_width'],row['status'],len(row.get('checks',[])),row.get('error','')) for row in results])
