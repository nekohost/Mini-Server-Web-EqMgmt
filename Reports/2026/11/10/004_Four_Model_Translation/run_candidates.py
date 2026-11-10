"""Freeze all study arms before a single candidate runs. Only substitute the measured system-text addition."""
import json, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1]).resolve()
public=(root/'control'/'cases.json').read_bytes()
policies=json.loads((root/'authors.json').read_bytes())
original=(root/'base/utils/ai_assistant/translation.py').read_text()
point="    messages = [{'role': 'system', 'content': instruction},"
assert original.count(point)==1 and set(policies)==set('abcd')
for arm, item in policies.items():
    folder=root/arm
    assert not (folder/'candidate-results.jsonl').exists()
    (folder/'cases.json').write_bytes(public)
    addition="    instruction += '\\n' + "+repr(item['instructions'])+"[direction]\n"
    (folder/'candidate/utils/ai_assistant/translation.py').write_text(original.replace(point,addition+point))
print('Four locked candidate sources ready.',flush=True)
for arm in 'abcd':
    folder=root/arm
    with (folder/'run.log').open('a') as out:
        subprocess.run([sys.executable,'-u',str(root/'study.py'),str(folder),'candidate'],cwd=root,stdout=out,stderr=subprocess.STDOUT,check=True)
