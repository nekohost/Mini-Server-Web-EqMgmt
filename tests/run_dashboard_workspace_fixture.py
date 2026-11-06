"""[Role] Runs the pilot's actual Jinja pages and JS against synthetic read-only data in Linux Chromium.
[Dependencies] The project's loopback-only browser fixtures and authorized SSH host. [Impact] Produces screenshots and checks without loading the Flask production app or either DB.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib


def linux_cases(payload):
    """[Role] Render the reviewed overlays at real breakpoints. [Dependencies] Existing Chromium/Flask fixture on Linux. [Impact] All browser traffic stays in the disposable loopback fixture."""
    project = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
    sys.path.insert(0, str(project / 'tests'))
    from assistant_ui_browser_fixture import run_ui_browser
    from viewport_scrollbar_browser_fixture import capture_real_frames
    from portal_polish_browser_fixture import run_browser as portal_browser
    result = []
    for case, width, theme in payload['cases']:
        os.environ['EQ_FIXTURE_WIDTHS'] = json.dumps([width])
        os.environ['EQ_FIXTURE_THEMES'] = json.dumps([theme])
        assets = dict(payload['assets'])
        if case == 'portal':
            result.extend(dict(row, view=case) for row in portal_browser(project, assets))
            continue
        source = 'dashboard' if case == 'dashboard' else 'index'
        mode = 'public' if case == 'public' else 'my'
        # Insert the read-only synthetic transport before session_timer captures fetch.
        assets['templates/equipment_ai.html'] = ("{% extends '" + source + ".html' %}{% set mode = '" + mode +
            "' %}{% block extra_head %}{{ super() }}<script src=\"/static/js/equipment_ai.js\" defer></script>{% endblock %}")
        driver = assets['tests/dashboard_workspace_driver.js'].replace('__FIXTURE_VIEW__', case)
        result.extend(dict(row, view=case) for row in run_ui_browser(project, assets, driver, sizes=(width,), themes=(theme,), capture=capture_real_frames))
    return result


def main():
    """[Role] Package only relevant text assets over SSH. [Dependencies] Git workspace or sparse staged overlay. [Impact] Keeps screenshot/check details in the requested report directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--case', action='append', choices=['portal','dashboard','my','draft','edit','public'])
    args = parser.parse_args()
    overlay = Path(__file__).resolve().parents[1]
    project = next(p for p in (overlay,*overlay.parents) if (p/'AGENTS.md').is_file())
    assets = {}
    paths = ['templates/'+n+'.html' for n in ('dashboard','portal','index','miniserver_frame','root_frame','roadmap_equipment')]
    paths += ['static/css/'+n+'.css' for n in ('layout','components','roadmap','ai_polish_frame')]
    paths += ['tests/dashboard_workspace_driver.js','tests/test_portal_polish_ui.js']
    for name in paths:
        candidate = overlay/name
        assets[name] = (candidate if candidate.is_file() else project/name).read_text(encoding='utf-8-sig')
    cases = [('dashboard',1440,'dark'),('dashboard',412,'light'),('my',1440,'dark'),('my',412,'light'),
             ('draft',412,'light'),('edit',1440,'dark'),('public',412,'light'),('portal',1440,'light'),('portal',390,'dark')]
    if args.case:
        cases = [v for v in cases if v[0] in args.case]
    package = {'assets':assets,'cases':cases,'module':Path(__file__).read_text(encoding='utf-8-sig')}
    encoded = base64.b64encode(zlib.compress(json.dumps(package,ensure_ascii=False).encode())).decode()
    code = ("import sys,json,zlib,base64\np=json.loads(zlib.decompress(base64.b64decode("+repr(encoded)+")))\n"
            "ns={'__name__':'fixture'};exec(compile(p.pop('module'),'<ui-fixture>','exec'),ns);print(json.dumps(ns['linux_cases'](p)))")
    proc = subprocess.run(['ssh','-o','BatchMode=yes','eqmgmt-backup','/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python','-'],
                          input=code.encode(),capture_output=True)
    if proc.returncode:
        sys.stderr.buffer.write(proc.stderr[-3500:]);return 1
    out=args.artifacts.resolve()
    if not out.is_relative_to((project/'Reports').resolve()):
        raise ValueError('evidence belongs in project Reports')
    out.mkdir(parents=True,exist_ok=True)
    rows=json.loads(proc.stdout)
    for row in rows:
        shot=row.pop('screenshot',None)
        if shot:
            file=out/(row['view']+'-'+str(row['requested_width'])+'-'+row['requested_theme']+'.png')
            file.write_bytes(base64.b64decode(shot));row['image']=file.name
    (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'view':r['view'],'width':r['requested_width'],'status':r['status'],'checks':len(r.get('checks',[])),'error':r.get('error')} for r in rows],ensure_ascii=False))
    return int(len(rows)!=len(cases) or any(r['status']!='pass' or not r.get('image') for r in rows))


if __name__=='__main__':
    raise SystemExit(main())
