"""Test every domain-specific micro-guide on the two shared failure probes using the current ordinary route."""
import json,os,shutil,subprocess,sys
from pathlib import Path
from blind_review import blind,collect,write_new
root=Path(sys.argv[1]); micro=root/'micro'; micro.mkdir()
policies=json.loads((root/'micro-authors.json').read_bytes())
cases=[r for r in json.loads((root/'control/cases.json').read_bytes()) if r['id'].startswith('P-')]
assert len(cases)==2 and set(policies)==set('abcd')
source=(root/'base/utils/ai_assistant/translation.py').read_text()
point="    messages = [{'role': 'system', 'content': instruction},"
assert source.count(point)==1
for arm,v in policies.items():
    folder=micro/arm; folder.mkdir(); shutil.copytree(root/'base',folder/'candidate')
    os.link(root/'exclusive.lock',folder/'exclusive.lock')
    write_new(folder/'cases.json',cases)
    addition="    instruction += '\\n' + " + repr(v['instructions']) + "[direction]\n"
    (folder/'candidate/utils/ai_assistant/translation.py').write_text(source.replace(point,addition+point))
    with (folder/'run.log').open('x') as out:
        subprocess.run([sys.executable,'-u',str(root/'study.py'),str(folder),'candidate'],stdout=out,stderr=subprocess.STDOUT,check=True)
data,ledger=collect({arm:micro/arm for arm in policies},cases)
prior=json.loads((root/'development-judgment/measurements.json').read_bytes())
for case in cases:
    k=case['id'];data[k]['control']=prior[k]['control']
write_new(micro/'measurements.json',data)
write_new(micro/'ledger.json',ledger)
print(blind(cases,data,micro))
