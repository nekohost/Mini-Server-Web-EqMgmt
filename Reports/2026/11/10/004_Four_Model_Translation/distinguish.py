"""Distinguish close business-vocabulary finalists on new, opposite-direction custody and document contrasts."""
import json,sys,os,subprocess
from pathlib import Path
from blind_review import collect,blind,write_new
p=Path(sys.argv[1]);out=p/'finalist';out.mkdir()
examples=json.loads((p/'contrast.json').read_bytes())
cases=[c for c in examples if c['id'] in ('X1','X2')]
assert len(cases)==2
for arm in ('a','b'):
    fold=out/arm;fold.mkdir()
    os.link(p/'exclusive.lock',fold/'exclusive.lock')
    (fold/'candidate').symlink_to(p/'micro'/arm/'candidate',target_is_directory=True)
    write_new(fold/'cases.json',cases)
    with (fold/'run.log').open('x') as f:
        subprocess.run([sys.executable,'-u',str(p/'study.py'),str(fold),'candidate'],stdout=f,stderr=subprocess.STDOUT,check=True)
data,ledger=collect({arm:out/arm for arm in ('a','b')},cases)
base,_=collect({'control':p/'contrast-control'},examples)
for c in cases:
    k=c['id'];data[k]['control']=base[k]['control']
write_new(out/'measurements.json',data);write_new(out/'ledger.json',ledger)
print(blind(cases,data,out))
