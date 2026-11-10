"""Give all three independent reviewers exactly one UTF-8 synthetic dataset and the same instruction."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

folder=Path(sys.argv[1]).resolve()
output=Path(sys.argv[2]).resolve()
instruction=Path(sys.argv[3]).read_text(encoding='utf-8').strip()
expected=int(sys.argv[4]) if len(sys.argv)>4 else 41
source=folder/'blind-mail.json'
assert {f.name for f in folder.iterdir() if f.is_file()}=={source.name}
digest=hashlib.sha256(source.read_bytes()).hexdigest()
rows=json.loads(source.read_bytes())
assert len(rows)==len({row['id'] for row in rows})==expected and all(set(row)=={'id','source','target','L','R'} for row in rows)
models=('gemini-4-argon-high','gemini-3.8-flash-high','claude-opus-5-5-high')

def judge(model):
    capture=output/('grade-'+model+'.json')
    if capture.exists():
        raise RuntimeError('Review already recorded; preserve its first response')
    start=time.monotonic()
    result=subprocess.run([shutil.which('agy'),'--mode','plan','--model',model,'--effort','high',
                '--output-format','json','--print',instruction],cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    direct=result.stdout.decode('utf-8','replace')
    try:
        answer=json.loads(direct)
    except ValueError:
        answer={'status':'INVALID_OUTPUT','response':direct}
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    data={'model':model,'effort':'high','dataset_sha256':digest,'instruction_sha256':hashlib.sha256(instruction.encode()).hexdigest(),
          'seconds':round(time.monotonic()-start,2),'returncode':result.returncode,
          'status':answer.get('status'),'turns':answer.get('num_turns'),'response':answer.get('response')}
    with capture.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    print(model,result.returncode,data['status'],flush=True)
    if result.returncode or data['status']!='SUCCESS':
        raise RuntimeError('Independent review failed: '+model)

with ThreadPoolExecutor(max_workers=len(models)) as pool:
    list(pool.map(judge,models))
