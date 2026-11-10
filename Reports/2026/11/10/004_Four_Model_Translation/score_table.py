"""Unblind only the completely graded panel, retaining genuine disagreements and ties."""
from collections import Counter, defaultdict
import json,re,sys
from pathlib import Path
from review_settings import read_settings

models=('gemini-4-argon-high','gemini-3.8-flash-high','claude-opus-5-5-high','gpt-6-astra')
def parse(answer, packet):
    rows={}
    for line in answer.splitlines():
        parts=[part.strip().strip('*').strip() for part in line.strip().strip('|').split('|')]
        if len(parts)<3:continue
        match=re.fullmatch(r'(?:\d+[.)]\s*)?(m\d+)',parts[0],re.I)
        if not match:continue
        key=match[1].lower()
        grades=''.join(c for c in parts[1].upper() if c in 'ABC')
        best=[int(v) for v in re.findall(r'\d+',parts[2])]
        assert key not in rows and key in packet and len(grades)==len(packet[key]['options']),line
        assert best and all(1<=v<=len(grades) for v in best),line
        rows[key]={'grades':grades,'best':best,'reason':' | '.join(parts[3:])}
    if set(rows)!=set(packet):raise ValueError('missing rows '+str(set(packet)-set(rows)))
    return rows

def load_json(p):return json.loads(p.read_bytes())
if __name__=='__main__':
    phase=Path(sys.argv[1]);evidence=Path(sys.argv[2]);label=sys.argv[3]
    packet={x['id']:x for x in load_json(phase/'blind.json')}
    mapping=load_json(evidence/(label+'-mapping.json'))
    coordinator=load_json(evidence/(label+'-coordinator-blind.json'))
    assert set(coordinator)==set(packet) and all(len(coordinator[k]['grades'])==len(x['options']) for k,x in packet.items())
    votes={'coordinator':coordinator}; receipts={}; replies={}
    for m in models:
        response=load_json(phase/(m+'.json'))
        receipts[m]=read_settings(response)
        replies[m]=response
        votes[m]=parse(response['messages'][-1],packet)
    matrix={}
    for k,record in mapping.items():
        matrix[record['case']]={arm:{m:vote[k]['grades'][idx] for m,vote in votes.items()} for idx,arm in enumerate(record['arms'])}
    result={'matrix':matrix,'rubrics':votes,'settings':receipts}
    for suffix,d in [('scores',result),('replies',replies)]:
        with (evidence/(label+'-'+suffix+'.json')).open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
    print('graded',len(matrix),'sources',len(votes),'evaluators')
