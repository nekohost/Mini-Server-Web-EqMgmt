"""Create author-blind workspaces for grading the two already completed public UI deliveries."""
import json
from pathlib import Path
import sys

e = Path(__file__).resolve().parent
w = Path(sys.argv[1]).resolve()/'production'
w.mkdir()
p = []
for i,d in enumerate(('en-ko','ko-en'),1):
    row = json.loads((e/'live-mail'/(d+'.json')).read_bytes())
    assert row['state']=='done' and row['restored_same'] and row['model_steps']==1
    p.append({'id':'m'+str(i),'source':row['source'],'target':d.split('-')[1],'options':[row['display']]})
instruction = ('Grade each independently completed translation against its source. A is sendable unchanged, '
               'B requires a mandatory edit, C has material meaning loss or is unusable. Preserve signer identity. '
               'Check who owns, collects or pays, and what document, quantity and restriction the source actually states. '
               'For each row return: id | grade | 1 | decisive evidence in at most ten words. Do not use tools.')
payload = instruction+'\n\n'+json.dumps(p,ensure_ascii=False,separators=(',',':'))
for path in (e/'production-instruction.txt',w/'instruction.txt'):
    path.write_text(payload,encoding='utf-8')
for path in (e/'production-blind.json',w/'blind.json'):
    path.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
(e/'production-mapping.json').write_text(json.dumps({'m1':{'case':'live-en-ko','arms':['deployed']},'m2':{'case':'live-ko-en','arms':['deployed']}},indent=2))
print(instruction)
