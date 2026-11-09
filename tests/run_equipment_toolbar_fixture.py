"""[Role] Renders the intrinsic-width equipment toolbar and its existing workflows in Linux Chromium.
[Dependencies] Reviewed loopback fixture, actual Jinja/JS and synthetic GET transport. [Impact] No real DB, account, model or running web service is modified.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib


def linux_cases(package):
    """[Role] Uses actual child widths and live iframe resizing with retained form state.
    [Dependencies] Existing Chromium real-frame capture. [Impact] Runs one disposable fixture at a time without production authentication.
    """
    project = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
    sys.path.insert(0, str(project / 'tests'))
    from assistant_ui_browser_fixture import run_ui_browser
    from viewport_scrollbar_browser_fixture import capture_real_frames
    rows = []
    for view, width, theme in package['cases']:
        os.environ['EQ_FIXTURE_WIDTHS'] = json.dumps([width])
        os.environ['EQ_FIXTURE_THEMES'] = json.dumps([theme])
        assets = dict(package['assets'])
        mode = 'public' if view == 'public' else 'my'
        assets['templates/equipment_ai.html'] = ("{% extends 'index.html' %}{% set mode = '" + mode +
            "' %}{% block extra_head %}{{ super() }}<script src=\"/static/js/equipment_ai.js\" defer></script>{% endblock %}")
        driver = assets['tests/equipment_toolbar_driver.js'].replace('__FIXTURE_VIEW__', view).replace('__BASELINE__', str(package['baseline']).lower())
        rows.extend(dict(row, view=view) for row in run_ui_browser(project, assets, driver,
                    sizes=(width,), themes=(theme,), capture=capture_real_frames))
    return rows


def main():
    """[Role] Packages source-only overlays and writes reproducible screenshot/check artifacts.
    [Dependencies] Windows stdlib, authorized SSH and fixed Reports destination. [Impact] Baseline comparison never changes production source.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--view', action='append', choices=('my','public','draft','advanced','csv','error','empty','long','future','edit'))
    parser.add_argument('--width', action='append', type=int, choices=(320,384,412,820,1440))
    args = parser.parse_args()
    overlay = Path(__file__).resolve().parents[1]
    project = next(p for p in (overlay, *overlay.parents) if (p / 'AGENTS.md').is_file())
    paths = ['templates/' + n + '.html' for n in ('index','miniserver_frame','root_frame','roadmap_equipment')]
    paths += ['static/css/' + n + '.css' for n in ('layout','components','roadmap','ai_polish_frame')]
    paths += ['tests/equipment_toolbar_driver.js']
    assets = {}
    for name in paths:
        candidate = overlay / name
        assets[name] = (candidate if candidate.is_file() and (not args.baseline or name.startswith('tests/')) else project / name).read_text(encoding='utf-8-sig')
    cases = [('my',w,t) for w in (320,384,412,820,1440) for t in ('light','dark')]
    cases += [(v,w,t) for v in ('public','draft','advanced','csv','long','future','edit') for w,t in ((1440,'dark'),(384,'light'))]
    cases += [(v,384,'light') for v in ('error','empty')]
    if args.baseline:
        cases = [('my',w,'light') for w in (384,820,1440)]
    if args.view:
        cases = [c for c in cases if c[0] in args.view]
    if args.width:
        cases = [c for c in cases if c[1] in args.width]
    if not cases:
        raise ValueError('At least one supported screenshot case is required')
    package = {'assets':assets,'cases':cases,'baseline':args.baseline,'module':Path(__file__).read_text(encoding='utf-8-sig')}
    encoded = base64.b64encode(zlib.compress(json.dumps(package,ensure_ascii=False).encode())).decode()
    code = ("import json,zlib,base64\np=json.loads(zlib.decompress(base64.b64decode("+repr(encoded)+")))\n"
            "ns={'__name__':'fixture'};exec(compile(p.pop('module'),'<toolbar-fixture>','exec'),ns);print(json.dumps(ns['linux_cases'](p)))")
    proc = subprocess.run(['ssh','-o','BatchMode=yes','eqmgmt-backup','/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python','-'],input=code.encode(),capture_output=True)
    if proc.returncode:
        sys.stderr.buffer.write(proc.stderr[-3500:])
        return 1
    output = args.artifacts.resolve()
    if not output.is_relative_to((project/'Reports').resolve()):
        raise ValueError('Evidence must remain under Reports')
    output.mkdir(parents=True,exist_ok=True)
    rows = json.loads(proc.stdout)
    for row in rows:
        shot = row.pop('screenshot',None)
        if shot:
            name = row['view']+'-'+str(row['requested_width'])+'-'+row['requested_theme']+'.png'
            (output/name).write_bytes(base64.b64decode(shot))
            row['image'] = name
    (output/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'view':r['view'],'width':r['requested_width'],'status':r['status'],'rows':r.get('geometry',{}).get('final',{}).get('rows'),'checks':len(r.get('checks',[])),'error':r.get('error')} for r in rows],ensure_ascii=False))
    return int(len(rows)!=len(cases) or any(r['status']!='pass' or not r.get('image') for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
