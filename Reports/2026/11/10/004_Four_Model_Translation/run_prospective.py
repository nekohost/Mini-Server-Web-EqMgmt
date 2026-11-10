"""Two locked, unseen domain emails, same source in both arms; preserve each first completion."""
import json
import os
from pathlib import Path
import subprocess
import sys
from blind_review import blind, collect, write_new

p = Path(sys.argv[1]).resolve()
out = p/'prospective'
out.mkdir()
cases = json.loads((p/'prospective-cases.json').read_bytes())
arms = {}
for name, project in [('control',p/'base'),('selected',p/'verified/candidate')]:
    folder = out/name
    folder.mkdir()
    arms[name] = folder
    os.link(p/'exclusive.lock',folder/'exclusive.lock')
    (folder/'candidate').symlink_to(project,target_is_directory=True)
    write_new(folder/'cases.json',cases)
    with (folder/'run.log').open('x') as log:
        subprocess.run([sys.executable,'-u',str(p/'study.py'),str(folder),'candidate'],cwd=p,stdout=log,stderr=subprocess.STDOUT,check=True)
data, ledger = collect(arms,cases)
write_new(out/'measurements.json',data)
write_new(out/'ledger.json',ledger)
print(blind(cases,data,out))
