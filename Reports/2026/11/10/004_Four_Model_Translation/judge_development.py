"""Wait for the four measured arms, export anonymous evidence, and dispatch fresh reviewers."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

host, remote, scratch = 'eqmgmt-backup', sys.argv[1], Path(sys.argv[2])
here=Path(__file__).resolve().parent
def ssh(cmd):
    return subprocess.run(['ssh','-o','BatchMode=yes',host,cmd],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True).stdout.strip()
while True:
    n=ssh('cd '+remote+' && if test -f d/candidate-results.jsonl; then wc -l < d/candidate-results.jsonl; else echo 0; fi')
    if int(n)==8: break
    if 'Traceback' in ssh('tail -12 '+remote+'/queue-retry.log'): raise RuntimeError('candidate runner interrupted')
    time.sleep(12)
ssh('cd '+remote+' && python3 blind_review.py '+remote)
for name in ['blind.json','mapping.json','measurements.json','ledger.json']:
    subprocess.run(['scp','-q',host+':'+remote+'/development-judgment/'+name,str(here/('dev-'+name))],check=True)
shutil.copyfile(here/'dev-blind.json',scratch/'judge/blind.json')
subprocess.run([sys.executable,str(here/'review.py'),str(scratch),'judge'],check=True)
