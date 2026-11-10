"""Mix the four new measured arms with a control and fresh aliases for disputed earlier outputs."""
from pathlib import Path
import json,sys
from blind_review import blind,write_new
root=Path(sys.argv[1]);folder=root/'ruling'
initial=json.loads((root/'development-judgment/measurements.json').read_bytes())
micro=json.loads((root/'micro/measurements.json').read_bytes())
sources={c['id']:c for c in json.loads((root/'control/cases.json').read_bytes())}
out={}
for k in ('E2','D05'):
    out[k] = {arm:initial[k][arm] for arm in ['control','c','d']}
for k in ('P-en-ko','P-ko-en'):
    out[k]={('control' if name=='control' else 'micro-'+name):record for name,record in micro[k].items()}
    out[k]['ordinary-d']=initial[k]['d']
    out[k]['ordinary-c']=initial[k]['c']
folder.mkdir(exist_ok=True)
write_new(folder/'measured-options.json',out)
print(blind([sources[k] for k in out],out,folder))
