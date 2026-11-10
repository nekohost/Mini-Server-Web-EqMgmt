"""Reduce the synthetic first-attempt records, then verify the wire instructions on the shipped tree."""
import json
from pathlib import Path
from statistics import median
import sys

root=Path(sys.argv[1])
delivery=root/'delivery'
sets=[('baseline',root,'baseline'),('candidate1',root,'candidate'),('candidate2',root/'final','candidate'),
      ('extra_baseline',delivery/'base-new','baseline'),('extra_final',delivery,'candidate')]
all_sets={}
intervals=[]
engine_ids=set()
health={}
cases_for_replay=[]
def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]
for label,folder,arm in sets:
    rows=lines(folder/(arm+'-results.jsonl'))
    expected=2 if label=='extra_baseline' else 3 if label=='extra_final' else 10
    wires={v['id']:v for v in lines(folder/(arm+'-wire.jsonl'))}
    metrics=lines(folder/(arm+'-metrics.jsonl'))
    health[label]={'models':sorted({v['engine'] for v in metrics if 'engine' in v}),
                   'sample_errors':sum('sample_error' in v for v in metrics),
                   'max_provider_queued':max(v['queued'] for v in metrics if 'queued' in v),
                   'counter_delta':metrics[-1]['total']-metrics[0]['total']}
    assert len(rows)==len(wires)==len({r['case'] for r in rows})==expected
    data={}
    for r in rows:
        step,=r['steps']
        assert step['wire_calls']==1 and step['termination']=={'done':True,'finish_reason':'stop'} and not step['calls']
        assert step['server_request_id'] not in engine_ids
        engine_ids.add(step['server_request_id'])
        intervals.append((step['wire_start'],step['wire_end']))
        wire=wires[r['case']]
        data[r['case']]={'source':r['original'],'direction':r['direction'],'state':r['state'],'error':r['error'],
                         'model':wire['model'],'effort':wire['effort'],'elapsed_s':r['elapsed'],'prompt_sha256':wire['instruction_sha256'],
                         'raw':step['content'],'display':r['answer']}
        if (label=='candidate2' and r['case']!='E3') or label=='extra_final':
            cases_for_replay.append({'case':r['case'],'direction':r['direction'],'source':r['original'],'effort':wire['effort'],
                    'prompt_sha256':wire['instruction_sha256'],'expected_state':r['state'],'expected_display':r['answer'],
                    'measured_finish':{'outcome':step['outcome'],'termination':step['termination'],'calls':step['calls'],'content':step['content']}})
    all_sets[label]=data
intervals.sort()
gaps=[b[0]-a[1] for a,b in zip(intervals,intervals[1:])]
assert len(intervals)==35 and min(gaps)>=0
baseline={**all_sets['baseline'],**all_sets['extra_baseline']}
final={**all_sets['candidate2'],**all_sets['extra_final']}
assert len(final)==len(baseline)==len(cases_for_replay)==12 and set(final)==set(baseline)
timings={}
for lang in ('en-ko','ko-en'):
    timings[lang]={n:round(median(y['elapsed_s'] for y in group.values() if y['direction']==lang),2)
                   for n,group in [('baseline',baseline),('final',final)]}
out={'attempts':all_sets,'study':health,'wire_count':len(intervals),'different_upstream_ids':len(engine_ids),
     'overlapping_requests':sum(g<0 for g in gaps),'minimum_client_gap_s':round(min(gaps),3),
     'median_seconds_on_same_12':timings}
(delivery/'observations.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
(delivery/'delivery12.json').write_text(json.dumps(cases_for_replay,ensure_ascii=False,indent=2))
