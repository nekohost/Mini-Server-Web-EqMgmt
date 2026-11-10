"""Cross-check the chosen reviewer model and tier against its own local run receipt."""
import json, os, re, sys
from pathlib import Path

def read_settings(record):
    model, tid = record['model'],record['thread']
    if not tid or record['status']!='SUCCESS': raise ValueError('missing independent session')
    home=Path.home()
    if model=='gpt-6-astra':
        session,=list((home/'.codex/sessions').rglob('*'+tid+'*.jsonl'))
        context=None
        tiers=set()
        efforts=set()
        models=set()
        for line in session.open(encoding='utf-8'):
            ev=json.loads(line);p=ev.get('payload',{})
            if ev['type']=='turn_context':
                models.add(p['model']);efforts.add(p['effort'])
            if ev['type']=='event_msg' and p.get('type')=='token_count' and p.get('info'):
                context=p['info'].get('model_context_window')
            if ev['type']=='event_msg' and p.get('service_tier'):tiers.add(p['service_tier'])
            for usage in (p.get('info') or {}, p.get('rate_limits') or {}):
                if isinstance(usage,dict) and usage.get('service_tier'):tiers.add(usage['service_tier'])
        if not tiers:
            # Some CLI builds place the actual served tier inside nested usage metadata.
            def walk(v):
                if isinstance(v,dict):
                    for k,x in v.items():
                        if k=='service_tier' and isinstance(x,str):tiers.add(x)
                        elif isinstance(x,(dict,list)):walk(x)
                elif isinstance(v,list):
                    for x in v:walk(x)
            for line in session.open(encoding='utf-8'):
                if 'service_tier' in line:walk(json.loads(line))
        assert models=={model} and efforts=={'max'} and tiers=={'priority'} and context==828400
        return {'session':tid,'model':model,'effort':'max','served_tier':'priority','configured_window':872000,'effective_window':context}
    names={'gemini-4-argon-high':'Gemini 4 Argon (High)','gemini-3.8-flash-high':'Gemini 3.8 Flash (High)','claude-opus-5-5-high':'Claude Opus 5.5 (High)'}
    f=home/'.gemini/antigravity-cli/brain'/tid/'.system_generated/logs/transcript.jsonl'
    assert any(('to '+names[model]+'.') in json.loads(line).get('content','') for line in f.open(encoding='utf-8') if 'USER_SETTINGS_CHANGE' in line)
    return {'session':tid,'model':names[model],'effort':'high'}

if __name__=='__main__':
    folder=Path(sys.argv[1]);out=Path(sys.argv[2])
    docs=[json.loads(f.read_bytes()) for f in folder.glob('*.json') if f.name.startswith(('gemini-','claude-','gpt-'))]
    assert len(docs)==4
    data={v['model']:read_settings(v) for v in docs}
    with out.open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    print(len(data),'verified')
