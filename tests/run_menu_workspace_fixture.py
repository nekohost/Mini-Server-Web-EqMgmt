"""[Role] Checks every compact menu using actual Jinja and Linux Chromium.
[Dependencies] Existing loopback fixtures, SSH and candidate text assets. [Impact] Synthetic GET-only data; no Flask production app, database, account or AI generation is used.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import zlib


VIEWS = ['admin_center', 'dashboard', 'public', 'my_approvals', 'mypage', 'users_management',
         'permissions', 'master_management', 'lineup_management', 'approvals', 'audit_logs',
         'access_logs', 'access_logs_error_ips', 'maintenance_admin', 'backup_restore']


def linux_cases(package):
    """[Role] Renders all menus with one reviewed overlay and isolated transport.
    [Dependencies] Server's read-only static files and real-frame capture. [Impact] Browser traffic remains on loopback and all non-GET calls fail the run.
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
        source = 'index' if view == 'public' else view
        assets['templates/equipment_ai.html'] = (
            "{% extends '" + source + ".html' %}{% set mode = 'public' %}"
            "{% set user = {'UserId':900,'LoginId':'fixture','Name':'검증','NickName':'검증 사용자','Role':'admin','Email':''} %}"
            "{% set maintenance = {'state':'NORMAL','message':''} %}{% set restore_confirmation = '복원 확인' %}"
            "{% block extra_head %}{{ super() }}<script src=\"/static/js/equipment_ai.js\" defer></script>{% endblock %}")
        driver = assets['tests/menu_workspace_driver.js'].replace('__FIXTURE_VIEW__', view)
        rows.extend(dict(row, view=view) for row in run_ui_browser(project, assets, driver,
                    sizes=(width,), themes=(theme,), capture=capture_real_frames))
    return rows


def main():
    """[Role] Packages candidate files and persists evidence under Reports.
    [Dependencies] Windows stdlib and authorized SSH Python. [Impact] Only disposable server fixtures execute the actual Jinja/JS.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--view', action='append', choices=VIEWS)
    parser.add_argument('--width', type=int, choices=(320,384,820,1440))
    parser.add_argument('--theme', choices=('light','dark'))
    args = parser.parse_args()
    overlay = Path(__file__).resolve().parents[1]
    project = next(p for p in (overlay, *overlay.parents) if (p / 'AGENTS.md').is_file())
    paths = {p.relative_to(project).as_posix() for p in (project / 'templates').glob('*.html')}
    paths |= {'static/css/' + n + '.css' for n in ('layout', 'components', 'roadmap', 'ai_polish_frame')}
    paths.add('tests/menu_workspace_driver.js')
    assets = {}
    for name in sorted(paths):
        candidate = overlay / name
        assets[name] = (candidate if candidate.is_file() else project / name).read_text(encoding='utf-8-sig')
    views = args.view or VIEWS
    cases = [(v, w, theme) for v in views for w, theme in ((1440, 'dark'), (384, 'light'))]
    if not args.view:
        cases += [(v, 320, 'dark') for v in ('master_management', 'permissions', 'my_approvals')]
        cases += [(v, 820, 'light') for v in ('dashboard', 'mypage', 'users_management')]
    if args.width:
        cases = [(v, args.width, t) for v in views for t in ((args.theme,) if args.theme else ('light', 'dark'))]
    elif args.theme:
        cases = [c for c in cases if c[2] == args.theme]
    if not cases:
        raise ValueError('The requested browser case set must not be empty')
    package = {'assets': assets, 'cases': cases, 'module': Path(__file__).read_text(encoding='utf-8-sig')}
    encoded = base64.b64encode(zlib.compress(json.dumps(package, ensure_ascii=False).encode())).decode()
    code = ("import json,zlib,base64\np=json.loads(zlib.decompress(base64.b64decode(" + repr(encoded) + ")))\n"
            "ns={'__name__':'fixture'};exec(compile(p.pop('module'),'<menu-fixture>','exec'),ns);print(json.dumps(ns['linux_cases'](p)))")
    process = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'eqmgmt-backup',
                              '/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python', '-'],
                             input=code.encode(), capture_output=True)
    if process.returncode:
        sys.stderr.buffer.write(process.stderr[-4000:])
        return 1
    output = args.artifacts.resolve()
    if not output.is_relative_to((project / 'Reports').resolve()):
        raise ValueError('Evidence must stay under Reports')
    output.mkdir(parents=True, exist_ok=True)
    rows = json.loads(process.stdout)
    for row in rows:
        screenshot = row.pop('screenshot', None)
        if screenshot:
            name = row['view'] + '-' + str(row['requested_width']) + '-' + row['requested_theme'] + '.png'
            (output / name).write_bytes(base64.b64decode(screenshot))
            row['image'] = name
    (output / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{'view': r['view'], 'width': r['requested_width'], 'status': r['status'],
                       'checks': len(r.get('checks', [])), 'error': r.get('error')} for r in rows], ensure_ascii=False))
    return int(len(rows) != len(cases) or any(r['status'] != 'pass' or not r.get('image') for r in rows))


if __name__ == '__main__':
    raise SystemExit(main())
