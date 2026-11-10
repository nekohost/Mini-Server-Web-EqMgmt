"""Create a per-email random permutation. Only blind.json is copied to a judge's fresh directory."""
import hashlib
import json
from pathlib import Path
from secrets import SystemRandom
import sys

def write_new(path, data):
    with path.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')

def blind(cases, measurements, out, subset=None):
    out.mkdir(exist_ok=True,parents=True)
    cipher = {}
    packet = []
    rng = SystemRandom()
    for i, case in enumerate(cases,1):
        key = case['id']
        labels = list(subset[key]) if subset else list(measurements[key])
        rng.shuffle(labels)
        ident='m'+str(i)
        cipher[ident]={'case':key,'arms':labels}
        choices = [measurements[key][arm]['stored'] or '[NO COMPLETED TRANSLATION]' for arm in labels]
        packet.append({'id':ident,'source':case['original'],'target':case['direction'].split('-')[-1],'options':choices})
    write_new(out/'blind.json',packet)
    write_new(out/'mapping.json',cipher)
    return hashlib.sha256((out/'blind.json').read_bytes()).hexdigest()

def collect(arms, cases):
    result = {c['id']:{} for c in cases}
    ledger = []
    for label,folder in arms.items():
        def read(suffix):
            return [json.loads(line) for line in (folder/('candidate-'+suffix+'.jsonl')).read_bytes().splitlines()]
        wires = read('wire')
        results = read('results')
        assert len(results)==len(wires)==len(cases)
        for case,row,wire in zip(cases,results,wires):
            key=case['id']; assert row['case']==wire['id']==key and row['original']==case['original']
            step,=row['steps']
            assert wire['source_sha256']==hashlib.sha256(case['original'].encode()).hexdigest()
            assert step['wire_calls']==1 and wire['tools']==0 and wire['stream'] and wire['model']=='qwen3.8-flash-next-iq3_xxs'
            assert wire['effort']=={'en-ko':'xhigh','ko-en':'low'}[case['direction']]
            entry={'model':wire['model'],'effort':wire['effort'],'source_sha256':wire['source_sha256'],
                   'instruction_sha256':wire['instruction_sha256'],'stored':row['answer'],'raw':step['content'],
                   'elapsed':row['elapsed'],'termination':step['termination'],'state':row['state'],'error':row['error'],
                   'server_id_sha256':hashlib.sha256(str(step['server_request_id']).encode()).hexdigest(),
                   'start':step['wire_start'],'end':step['wire_end']}
            assert row['state'] in ('done','failed') and bool(entry['stored'])==(row['state']=='done')
            result[key][label]=entry
            ledger.append({'case':key,'arm':label,**{k:entry[k] for k in ['start','end','server_id_sha256','state']}})
    ledger.sort(key=lambda x:x['start'])
    assert len(ledger)==len({v['server_id_sha256'] for v in ledger})
    assert all(a['end']<=b['start'] for a,b in zip(ledger,ledger[1:]))
    return result, ledger

if __name__=='__main__':
    root=Path(sys.argv[1])
    cases=json.loads((root/'control/cases.json').read_bytes())
    arms={label:root/label for label in ['control','a','b','c','d']}
    data,ledger=collect(arms,cases)
    out=root/'development-judgment'
    out.mkdir(exist_ok=True)
    write_new(out/'measurements.json',data)
    write_new(out/'ledger.json',ledger)
    print(blind(cases,data,out))
