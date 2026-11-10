"""Make the confirmation packet from both measured arms, keep timing and separate historic replays."""
from pathlib import Path
import json,sys
from blind_review import collect,blind,write_new
p=Path(sys.argv[1]);out=p/'confirmation';out.mkdir(exist_ok=True)
cases=[];data={};ledger=[]
for name,source in [('hold','holdout.json'),('contrast','contrast.json')]:
    group=json.loads((p/source).read_bytes())
    run,trace=collect({'control':p/(name+'-control'),'selected':p/(name+'-selected')},group)
    cases.extend(group);data.update(run);ledger.extend(trace)
ledger.sort(key=lambda x:x['start'])
assert all(a['end']<=b['start'] for a,b in zip(ledger,ledger[1:]))
write_new(out/'measurements.json',data)
write_new(out/'ledger.json',ledger)
print(blind(cases,data,out))
