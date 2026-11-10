"""Evaluate a frozen release hypothesis against unused and historic source texts; generation remains serial."""
import json,os
from pathlib import Path
import subprocess,sys

root=Path(sys.argv[1]).resolve()
selected=root/'selected'
project=selected/'candidate'
assert project.joinpath('utils/ai_assistant/translation.py').is_file()
for name, cases in [('hold-selected',root/'holdout.json'),('contrast-selected',root/'contrast.json'),('historic-selected',None)]:
    fold=root/name
    fold.mkdir(exist_ok=True)
    if not(fold/'exclusive.lock').exists():os.link(root/'exclusive.lock',fold/'exclusive.lock')
    if not(fold/'candidate').exists():(fold/'candidate').symlink_to(project,target_is_directory=True)
    if cases:
        (fold/'cases.json').write_bytes(cases.read_bytes())
    else:
        (fold/'historic-source.json').write_bytes((root/'historic-control/historic-source.json').read_bytes())
        subprocess.run([sys.executable,str(root/'historic_replay.py'),str(project),str(fold)],check=True)
    if json.loads((fold/'cases.json').read_bytes()):
        with (fold/'run.log').open('a') as out:
            subprocess.run([sys.executable,'-u',str(root/'study.py'),str(fold),'candidate'],stdout=out,stderr=subprocess.STDOUT,check=True)
