"""Test the same rejected audit text at the finish boundary, independently of prompt changes."""
from pathlib import Path
import hashlib
import json
import os
import sys
trial = Path(sys.argv[1]).resolve()
root = trial/'verified/candidate'
sys.path[:0] = [str(root/'tests'),str(root)]
os.environ['EQ_TEST_PROJECT_ROOT'] = str(root)
from mail_fixture import fixture
from test_mail_translation import assistant, request, stream
from utils.ai_assistant.translation import KOREAN_SIGNOFF_REVISION, translation_completion
from utils.ai_assistant.policy import canonical

source = json.loads((trial/'prospective-cases.json').read_bytes())[0]['original']
first = json.loads((trial/'prospective/measurements.json').read_bytes())['Y1']['control']
assert first['state']=='failed'
with fixture(assistant) as f:
    jid = f.submit(request(source)).get_json()['job_id']
    packet = f.claim()
    with f.store.db() as db:
        row = dict(f.store.job(jid,db))
    data = {'content':first['raw'],'termination':first['termination']}
    old = {**packet['route'],'mail_display_revision':KOREAN_SIGNOFF_REVISION}
    assert translation_completion({**row,'route_snapshot':canonical(old)},'en-ko',data)[0] == 'failed'
    f.drive(packet,lambda _:stream(first['raw']))
    with f.store.db() as db:
        saved = db.execute("SELECT content FROM messages WHERE job=? AND role='assistant'",(jid,)).fetchone()[0]
        audited = db.execute('SELECT content FROM message_steps WHERE job=?',(jid,)).fetchone()[0]
    assert f.finish_reports[-1][1]['state']=='done' and audited==first['raw']
record = {'case':'Y1','same_source_and_raw':True,'old_display_gate':'failed','new_display_gate':'done',
          'original_first_inference_still':'failed','new_inferences':0,'stored':saved,
          'raw_sha256':hashlib.sha256(audited.encode()).hexdigest()}
(trial/'envelope-counterfactual.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
