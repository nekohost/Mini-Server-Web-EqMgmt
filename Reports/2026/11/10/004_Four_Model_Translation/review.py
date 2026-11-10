"""Run the same prompt in four fresh CLI sessions, retaining all public model messages."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

MODELS = ('gemini-4-argon-high','gemini-3.8-flash-high','claude-opus-5-5-high','gpt-6-astra')
root, phase = Path(sys.argv[1]).resolve(), sys.argv[2]
models = sys.argv[3:] or MODELS

def run(model):
    assert model in MODELS
    folder = root/phase/model
    folder.mkdir(parents=True, exist_ok=True)
    prompt = (root/phase/'instruction.txt').read_text(encoding='utf-8').strip()
    if (root/phase/'blind.json').is_file():
        shutil.copyfile(root/phase/'blind.json',folder/'blind.json')
    out = root/phase/(model+'.json')
    if out.exists(): raise RuntimeError('Responded already: '+model)
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    if model == 'gpt-6-astra':
        cmd = [shutil.which('codex'), 'exec','--skip-git-repo-check','--sandbox','read-only','--json','-m',model,
               '-c','model_reasoning_effort="max"','-c','service_tier="fast"','-c','model_context_window=872000','-']
        p = subprocess.run(cmd,input=prompt.encode(),cwd=folder,capture_output=True)
        rows = [json.loads(line) for line in p.stdout.decode('utf-8','replace').splitlines() if line.startswith('{')]
        texts = [row['item']['text'] for row in rows if row.get('type')=='item.completed' and row.get('item',{}).get('type')=='agent_message']
        thread = next((row.get('thread_id') for row in rows if row.get('type')=='thread.started'),None)
        status = 'SUCCESS' if any(row.get('type')=='turn.completed' for row in rows) and texts and p.returncode==0 else 'FAILED'
        errors = [row.get('message') or row.get('error') for row in rows if row.get('type') in ('error','turn.failed')]
    else:
        cmd = [shutil.which('agy'),'--mode','plan','--model',model,'--effort','high','--output-format','json','--print',prompt]
        p = subprocess.run(cmd,cwd=folder,capture_output=True)
        try: envelope = json.loads(p.stdout.decode('utf-8','replace'))
        except ValueError: envelope = {}
        texts = [envelope['response']] if envelope.get('response') else []
        status = envelope.get('status','FAILED'); thread = envelope.get('session_id') or envelope.get('conversation_id')
        errors = [envelope.get('error')] if envelope.get('error') else []
    result={'model':model,'effort':'max' if model=='gpt-6-astra' else 'high','phase':phase,'thread':thread,
            'started':started,'seconds':round(time.monotonic()-clock,2),'status':status,'code':p.returncode,'messages':texts,
            'errors':errors,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    if not texts or status!='SUCCESS' or p.returncode:
        (root/phase/(model+'.stderr')).write_bytes(p.stderr)
    print(model, status, p.returncode, len(texts), flush=True)

with ThreadPoolExecutor(max_workers=len(models)) as pool:
    for future in as_completed([pool.submit(run,m) for m in models]):
        future.result()
