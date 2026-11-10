"""Keep changes of instruction separate from sampling variation on a byte-identical request."""
import json, sys
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads((p/'confirmation/measurements.json').read_bytes())
rows=[]
for key,v in d.items():
    a,b=v['control'],v['selected']
    same=all(a[n]==b[n] for n in ['model','effort','source_sha256','instruction_sha256'])
    rows.append({'case':key,'same_wire_instruction':same,'same_stored_answer':a['stored']==b['stored'],
                 'control_state':a['state'],'selected_state':b['state']})
(p/'confirmation/scopes.json').write_text(json.dumps(rows,indent=2))
print('changed', [v['case'] for v in rows if not v['same_wire_instruction']])
