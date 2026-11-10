"""Distribute the review suite across separate isolated fixture processes and verify the union."""
import ast
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys

p = Path(sys.argv[1]).resolve()
root = p/'verified/candidate'
runner = p/'check_candidate.py'
modules = next(ast.literal_eval(node.value) for node in ast.parse(runner.read_text()).body
               if isinstance(node,ast.Assign) and any(isinstance(n,ast.Name) and n.id=='modules' for n in node.targets))
sizes = {m:sum(isinstance(n,ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(ast.parse((root/'tests'/(m+'.py')).read_text()))) for m in modules}
groups = [[],[],[]]
for name in sorted(modules,key=sizes.get,reverse=True):
    min(groups,key=lambda group:sum(sizes[n] for n in group)).append(name)
children = []
for names in groups:
    with (p/('test-'+names[0]+'.log')).open('xb') as log:
        children.append(subprocess.Popen(['nice','-n','5',sys.executable,'-B',str(runner)],cwd=root,env={**os.environ,'EQ_QA_MODULES':','.join(names)},stdout=log,stderr=log))
assert [proc.wait() for proc in children]==[0]*len(children)
results = [json.loads((root.parent/('linux-'+names[0]+'.json')).read_bytes()) for names in groups]
assert Counter(name for record in results for name in record['modules'])==Counter(modules)
assert all(r['skipped']==0 and not r['failures'] and not r['errors'] for r in results)
total=sum(r['run'] for r in results)
assert total==306,total
summary={'run':total,'failures':0,'errors':0,'skipped':0,'python':results[0]['python'],'shards':results}
(p/'release-qa.json').write_text(json.dumps(summary,indent=2))
print('complete',total,'tests')
