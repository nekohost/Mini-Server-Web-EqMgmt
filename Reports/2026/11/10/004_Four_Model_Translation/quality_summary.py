"""Separate held-out, matched control, elicitation and replay evidence; retain every reviewer vote."""
from collections import Counter
import json
from pathlib import Path
from statistics import median

root = Path(__file__).resolve().parent
def read(name):
    return json.loads((root/(name+'.json')).read_bytes())
def counts(values):
    c = Counter(values)
    return {k:c[k] for k in 'ABC'}

cases = {c['id']:c for src in ('holdout','contrast','development','prospective-cases') for c in read(src)}
matrix = read('confirmation-scores')['matrix']
measured = read('confirmation-measurements')
matrix.update(read('prospective-scores')['matrix'])
measured.update(read('prospective-measurements'))
ruling = read('ruling-scores')['matrix']
micro = read('ruling-measured-options')
pooled = ['P-en-ko','P-ko-en','X1','X2','T1','T2']
fresh = ['T1','T2','T3','T4','T5','T6','X3','X4']
def pair(key):
    if key in ('P-en-ko','P-ko-en'):
        return {a:(ruling[key][b],micro[key][b]) for a,b in [('control','control'),('selected','micro-a')]}
    return {a:(matrix[key][a],measured[key][a]) for a in ('control','selected')}

def summarize(group):
    result = {}
    for direction in ('en-ko','ko-en','both'):
        keys = [k for k in group if direction=='both' or cases[k]['direction']==direction]
        result[direction] = {}
        for arm in ('control','selected'):
            rows = [pair(k)[arm] for k in keys]
            result[direction][arm] = {
                'sources':keys,'coordinator':counts(v['coordinator'] for v,_ in rows),
                'panel':{m:counts(v[m] for v,_ in rows) for m in rows[0][0] if m!='coordinator'},
                'median_seconds':round(median(r['elapsed'] for _,r in rows),2)}
    return result
ledger = sorted(({**v,'round':name} for name in ('dev','micro','finalist','confirmation','prospective') for v in read(name+'-ledger')),key=lambda v:v['start'])
assert len({v['server_id_sha256'] for v in ledger})==len(ledger)==76
assert all(x['end']<=y['start'] for x,y in zip(ledger,ledger[1:]))
history = read('historic-final-replays')
assert history == read('historic-control-replays') and all(row['same'] for row in history.values())
historic_grades = json.loads((root.parent/'003_Business_Translation/adjudication.json').read_bytes())['cases']
hist_by_dir = {d:counts(v['release'] for v in historic_grades if v['id'] in history and v['id'].split('-')[1].startswith(letter)) for d,letter in [('en-ko','E'),('ko-en','K')]}
assert sum(sum(v.values()) for v in hist_by_dir.values())==20
shared = read('shared-control-replays')
assert len(shared)==6 and not any(v['display_changed'] for v in shared)
out = {
    'scale':{'A':'sendable unchanged','B':'requires editing','C':'substantive error, missing or unusable'},
    'matched_targeted_examples':summarize(pooled),'never_used_for_selection':summarize(fresh),
    'all_targeted_examples':summarize(pooled+['Y1','Y2']),'all_never_used_for_selection':summarize(fresh+['Y1','Y2']),
    'prospective_only':summarize(['Y1','Y2']),
    'withheld_with_instruction_change':summarize(['T1','T2']),
    'no_instruction_change':summarize([s['case'] for s in read('confirmation-scopes') if s['same_wire_instruction']]),
    'historical_20_identical_saved_frames':hist_by_dir,'same_instruction_control_replays':len(shared),
    'staging_inferences':{'count':len(ledger),'max_simultaneous_observed':1,
        'first_pass_states':dict(Counter(row['state'] for row in ledger)),
        'failures':[{k:row[k] for k in ('round','case','arm')} for row in ledger if row['state']!='done']},
    'correction_replay':next(v for v in read('confirmation-replays') if v['display_changed']),
    'general_guides_development':{arm:counts(v[arm]['coordinator'] for v in read('dev-scores')['matrix'].values()) for arm in ('control','a','b','c','d')},
}
(root/'quality-summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for group in ('all_targeted_examples','all_never_used_for_selection','prospective_only','withheld_with_instruction_change'):
    print(group,[(d,*[(q['coordinator'],q['median_seconds']) for q in v.values()]) for d,v in out[group].items()])
print(out['historical_20_identical_saved_frames'], out['staging_inferences'],out['general_guides_development'])
