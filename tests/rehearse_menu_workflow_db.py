"""Rehearse only in a private online-copy of the backup DB; never run against live DB."""
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
from unittest.mock import patch

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
RELEASES = Path('/home/nekohost/.local/share/mini-server-eqmgmt/releases')
candidate = Path(__file__).resolve().parents[1]
assert candidate.parent == RELEASES and candidate.name.startswith('menu-workflows-fixture-')
assert (candidate/'source-manifest.json').is_file()
before_path, after_path = candidate/'rehearsal-before.db', candidate/'rehearsal.db'
assert not before_path.exists() and not after_path.exists()
os.umask(0o077)
with sqlite3.connect((ROOT/'equipment.db').as_uri()+'?mode=ro',uri=True) as source:
    with sqlite3.connect(before_path) as target: source.backup(target)
shutil.copy2(before_path,after_path)

def snapshot(path):
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn:
        conn.row_factory=sqlite3.Row
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name:[dict(row) for row in conn.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid')] for name in tables}

before=snapshot(before_path)
output=io.StringIO()
with patch.dict(os.environ,DATABASE_PATH=str(after_path),DATABASE_OPERATION_ROOT=str(candidate/'rehearsal-operations'),
        MAINTENANCE_STATE_PATH=str(candidate/'rehearsal-maintenance.json'),EQUIPMENT_ATTACHMENT_ROOT=str(candidate/'rehearsal-attachments'),
        SECRET_KEY='isolated-rehearsal-key'), patch('dotenv.load_dotenv',return_value=False), redirect_stdout(output), redirect_stderr(output):
    spec=importlib.util.spec_from_file_location('rehearsal_workflow_app',candidate/'app.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ACCESS_LOG_ACCEPTING.clear();module.shutdown_event.set();module.logger_thread.join(timeout=3)
    with module.app.test_request_context('/'):
        for name in ['my_approvals','mypage','permissions','lineup_management']:
            module.render_template(name+'.html',user={'UserId':999999,'LoginId':'fixture','Name':'Fixture','NickName':'Fixture','Role':'user','Email':''})
    after=snapshot(after_path)
    module.migrate_personal_approvals_menu()
    assert after==snapshot(after_path),'repeat migration changed data'
(candidate/'rehearsal-app.log').write_text(output.getvalue())
assert before.keys()==after.keys(),'table set changed'
unchanged={name:before[name]==after[name] for name in before if name not in {'menus','role_menu_permissions','sys_migrations'}}
assert all(unchanged.values()),'unrelated table data changed'
menus_before={row['MenuCode']:row for row in before['menus']}; menus_after={row['MenuCode']:row for row in after['menus']}
assert set(menus_after)-set(menus_before)=={'my_approvals'}
assert all(menus_after[key]==value for key,value in menus_before.items())
assert menus_after['my_approvals']['Url']=='/my_approvals' and menus_after['my_approvals']['ParentMenuCode'] is None
perms_before={(r['Role'],r['MenuCode']):r for r in before['role_menu_permissions']}
perms_after={(r['Role'],r['MenuCode']):r for r in after['role_menu_permissions']}
moved=[]
for key,value in perms_before.items():
    role,menu=key; current=perms_after[key]
    if menu=='approvals' and role!='admin' and value['IsAllowed']==1 and perms_before.get((role,'admin_center'),{}).get('IsAllowed',0)!=1:
        assert current['IsAllowed']==0
        assert all(current[k]==v for k,v in value.items() if k not in {'IsAllowed','UpdatedAt'})
        moved.append(role)
    else: assert current==value,'unrelated permission changed'
roles={r['Role'] for r in before['users']}|{r['Role'] for r in before['role_menu_permissions']}|{'admin','user'}
assert set(perms_after)-set(perms_before)=={(role,'my_approvals') for role in roles}
assert all(perms_after[(role,'my_approvals')]['IsAllowed']==1 for role in roles)
old_migrations={r['MigrationName']:r for r in before['sys_migrations']}; new_migrations={r['MigrationName']:r for r in after['sys_migrations']}
assert set(new_migrations)-set(old_migrations)=={'personal_approvals_portal_20260914'}
assert all(new_migrations[k]==v for k,v in old_migrations.items())
with sqlite3.connect(after_path) as conn:
    assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
result={'status':'pass','candidate':str(candidate),'all_other_tables_identical':unchanged,'new_menu':'my_approvals',
    'personal_roles':sorted(roles),'legacy_grants_moved':moved,'other_menus_permissions_unchanged':True,
    'migration_repeat_noop':True,'integrity':'ok','foreign_key_violations':0,'rendered_templates':4}
(candidate/'rehearsal-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
