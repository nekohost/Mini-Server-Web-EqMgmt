"""[MINI-COMMENT: ASSISTANT.LINUX.FIXTURE.RUNNER]
[EN rev.12]
[Role] Transfers audited candidate source in memory to the authorized Linux fixture host over SSH.
[Dependencies] Root source plus staged overlays, subprocess SSH and Python stdlib; never imports the app on Windows.
[Impact] Sparse overlays retain unchanged baseline tests/assets; full generated browser evidence is saved beside screenshots with compact stdout, and no remote source/config or production DB is modified.
"""
import argparse
import base64
import json
import hashlib
from pathlib import Path
import subprocess
import zlib


def main():
    """[Role] Packages only source/assets and executes synthetic tests on Linux, with no production DB access."""
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='eqmgmt-backup',choices=['eqmgmt-backup'])
    parser.add_argument('--browser',action='store_true')
    parser.add_argument('--browser-only',action='store_true')
    parser.add_argument('--provider-only',action='store_true')
    parser.add_argument('--include-images',action='store_true')
    parser.add_argument('--focus',action='append',default=[],help='Run named synthetic unittest targets on Linux only.')
    parser.add_argument('--artifact-dir',help='Create new screenshot artifacts under this project Reports directory.')
    parser.add_argument('--summary-only',action='store_true',help='Keep check names and failures while suppressing routine fixture logs.')
    parser.add_argument('--tmpfs-fixtures',action='store_true',help='Use private Linux tmpfs for disposable functional fixtures; never changes SQLite durability settings.')
    parser.add_argument('--browser-target',choices=['all','legacy','admin','chat','popup-short','viewport','disclosure'],default='all')
    args=parser.parse_args()
    overlay=Path(__file__).resolve().parents[1]
    project=overlay if (overlay/'AGENTS.md').is_file() else overlay.parents[2]
    fixture_roots=(overlay/'tests',) if overlay==project else (project/'tests',overlay.parent/'tests',overlay/'tests')
    extra_test_names={'test_admin_release.py','test_ai_conversation_lifecycle.py','test_ai_ux_integration.py','test_strata_integration.py'}
    browser_fixture_names={'admin_providers_browser_fixture.py','assistant_ui_browser_fixture.py','compact_measure_browser_fixture.py','csv_popup_browser_fixture.py','viewport_scrollbar_browser_fixture.py','model_disclosure_browser_fixture.py'}
    def candidate_file(relative):
        """[Role] Selects a changed overlay source or the unchanged reviewed project baseline. [Impact] No production app import occurs on Windows."""
        staged=overlay/relative
        return staged if staged.is_file() else project/relative
    sources={'utils':{'source':'','package':True}}
    for source_root in (project,overlay):
        for file in sorted((source_root/'utils').rglob('*.py')):
            relative=file.relative_to(source_root).with_suffix('')
            parts=relative.parts[:-1] if file.stem=='__init__' else relative.parts
            sources['.'.join(parts)]={'source':file.read_text(encoding='utf-8-sig'),'package':file.stem=='__init__'}
    candidate_paths=('templates/equipment_ai.html','templates/equipment_ai_providers.html',
        'static/css/equipment_ai.css','static/css/equipment_ai_providers.css',
        'static/js/equipment_ai.js','static/js/equipment_ai_providers.js','static/js/session_timer.js')
    assets={relative:((overlay/relative) if (overlay/relative).is_file() else project/relative).read_text(encoding='utf-8-sig') for relative in candidate_paths}
    for source_root in (project,overlay):
        for file in sorted((source_root/'templates').glob('strata*.html')):
            assets[file.relative_to(source_root).as_posix()]=file.read_text(encoding='utf-8-sig')
    for fixture_root in fixture_roots:
        for file in sorted(fixture_root.glob('*.js')):
            assets['tests/'+file.name]=file.read_text(encoding='utf-8-sig')
    admin_paths=('tools/deploy_user_ai.py','tools/deploy_strata.py','tools/write_strata_nginx_key.py',
                 'systemd/nginx-strata.conf.example','docs/strata-retirement-manifest.json',
                 'tools/ai_retention_cleanup.py','systemd/equipment-ai-retention.service','systemd/equipment-ai-retention.timer')
    # Pin the reviewed local frame/common assets too; the fixture host may be on an older deployment.
    for relative in ('templates/root_frame.html','templates/miniserver_frame.html','static/css/layout.css','static/css/components.css',
            'static/css/roadmap.css','static/js/common.js','static/js/roadmap_preferences.js',
            'static/js/navigation.js','static/js/menu_cards.js','static/js/catalog_requests.js','static/js/tailwindcss.js'):
        assets.setdefault(relative,(project/relative).read_text(encoding='utf-8-sig'))
    payload={'sources':sources,'assets':assets,'app':candidate_file('app.py').read_text(encoding='utf-8-sig'),
             'test':candidate_file('tests/test_equipment_ai.py').read_text(encoding='utf-8-sig'),
             'provider_test':candidate_file('tests/test_multi_provider_ai.py').read_text(encoding='utf-8-sig'),
             'browser':candidate_file('tests/assistant_browser_fixture.py').read_text(encoding='utf-8-sig') if args.browser or args.browser_only else None,
             'browser_only':args.browser_only,'provider_only':args.provider_only,
             'focus':args.focus,
             'tmpfs_fixtures':args.tmpfs_fixtures,
             'browser_target':args.browser_target,
             'extra_tests':{p.name:p.read_text(encoding='utf-8-sig') for folder in fixture_roots for p in sorted(folder.glob('test_*.py'))
                            if p.name in extra_test_names},
             'admin_files':{relative:((overlay/relative) if (overlay/relative).is_file() else project/relative).read_text(encoding='utf-8-sig')
                            for relative in admin_paths if (overlay/relative).is_file() or (project/relative).is_file()},
             'browser_fixtures':{p.name:p.read_text(encoding='utf-8-sig')
                                 for folder in fixture_roots
                                 for p in sorted(folder.glob('*_browser_fixture.py')) if p.name in browser_fixture_names}}
    payload['fixture_digest']=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    encoded=base64.b64encode(zlib.compress(json.dumps(payload,ensure_ascii=False).encode())).decode()
    script='''import base64,zlib,json,os,sys,time,types,importlib.abc,importlib.util,unittest,tempfile,subprocess,logging
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
logging.getLogger('werkzeug').setLevel(logging.ERROR)
payload=json.loads(zlib.decompress(base64.b64decode(PAYLOAD)))
fixture_storage='disk-temp'
if payload['tmpfs_fixtures']:
    memory_fixture=tempfile.TemporaryDirectory(prefix='eq-ai-functional-',dir='/dev/shm')
    tempfile.tempdir=memory_fixture.name
    fixture_storage='linux-tmpfs-functional-only'
dependency_tmp=tempfile.TemporaryDirectory(prefix='eq-ai-dependencies-')
if importlib.util.find_spec('cryptography') is None:
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--only-binary=:all:','--quiet','--target',dependency_tmp.name,'cryptography==50.0.2'],check=True,timeout=90)
    sys.path.insert(0,dependency_tmp.name)
os.chdir('/home/nekohost/services/Mini-Server-Web-EqMgmt')
os.environ['EQ_TEST_PROJECT_ROOT']=os.getcwd()
class MemorySource(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def find_spec(self,name,path=None,target=None):
        item=payload['sources'].get(name)
        return importlib.util.spec_from_loader(name,self,is_package=item['package']) if item else None
    def create_module(self,spec):return None
    def exec_module(self,module):
        item=payload['sources'][module.__name__]
        module.__file__='<candidate>/'+module.__name__.replace('.','/')+'.py'
        if item['package']:module.__path__=[]
        exec(compile(item['source'],module.__file__,'exec'),module.__dict__)
sys.meta_path.insert(0,MemorySource())
module=types.ModuleType('assistant_fixture_tests')
module.__file__='<candidate>/tests/test_equipment_ai.py'
module.CANDIDATE_ASSETS=payload['assets']
module.SOURCE_APP=payload['app']
sys.modules[module.__name__]=module
exec(compile(payload['test'],module.__file__,'exec'),module.__dict__)
suite=unittest.TestSuite() if payload['browser_only'] or payload['provider_only'] else unittest.defaultTestLoader.loadTestsFromModule(module)
if not payload['browser_only']:
    providers=types.ModuleType('assistant_provider_fixture_tests')
    providers.__file__='<candidate>/tests/test_multi_provider_ai.py'
    sys.modules[providers.__name__]=providers
    exec(compile(payload['provider_test'],'<candidate>/tests/test_multi_provider_ai.py','exec'),providers.__dict__)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(providers.ProviderTests))
    for name,source in payload['extra_tests'].items():
        if payload['focus'] and not any(target.startswith(name.removesuffix('.py')+'.') for target in payload['focus']):
            continue
        extra=types.ModuleType(name.removesuffix('.py'))
        extra.__file__='<candidate>/tests/'+name
        extra.CANDIDATE_ASSETS=payload['assets']
        extra.CANDIDATE_FILES=payload['admin_files']
        extra.SOURCE_APP=payload['app']
        sys.modules[extra.__name__]=extra
        exec(compile(source,extra.__file__,'exec'),extra.__dict__)
        # Imported helper TestCases must not inflate the measured count by running the baseline twice.
        for candidate in vars(extra).values():
            if isinstance(candidate,type) and issubclass(candidate,unittest.TestCase) and candidate.__module__==extra.__name__:
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(candidate))
if payload['focus']:
    suite=unittest.defaultTestLoader.loadTestsFromNames(payload['focus'])
started=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'platform':sys.platform,'python':sys.version.split()[0],'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'elapsed_seconds':round(time.monotonic()-started,3),'production_app_imported':False,'production_database_opened':False,'fixture_digest':payload['fixture_digest'],'fixture_storage':fixture_storage}))
if payload['browser'] and result.wasSuccessful():
    browser=types.ModuleType('assistant_browser_fixture')
    browser.__file__='<candidate>/tests/assistant_browser_fixture.py'
    sys.modules[browser.__name__]=browser
    exec(compile(payload['browser'],browser.__file__,'exec'),browser.__dict__)
    for name,source in payload['browser_fixtures'].items():
        extra=types.ModuleType(name.removesuffix('.py'))
        extra.__file__='<candidate>/tests/'+name
        sys.modules[extra.__name__]=extra
        exec(compile(source,extra.__file__,'exec'),extra.__dict__)
    admin=sys.modules.get('admin_providers_browser_fixture')
    if admin is not None:
        browser.ADMIN_SCRIPT=getattr(admin,'ADMIN_SCRIPT',getattr(admin,'SCRIPT',browser.ADMIN_SCRIPT))
        browser.FRAME_DIAGNOSTIC_SCRIPT=getattr(admin,'FRAME_DIAGNOSTIC_SCRIPT','')
    results=browser.run_browser(os.getcwd(),payload['assets']) if payload['browser_target'] in ('all','legacy') else []
    for name in payload['browser_fixtures']:
        if payload['browser_target']=='disclosure':
            if name=='model_disclosure_browser_fixture.py':
                results.extend(sys.modules[name.removesuffix('.py')].run_browser(os.getcwd(),payload['assets']))
            continue
        if payload['browser_target']=='viewport':
            if name=='viewport_scrollbar_browser_fixture.py':
                results.extend(sys.modules[name.removesuffix('.py')].run_browser(os.getcwd(),payload['assets']))
            continue
        if payload['browser_target']=='popup-short':
            if name=='csv_popup_browser_fixture.py':
                results.extend(sys.modules[name.removesuffix('.py')].run_short_browser(os.getcwd(),payload['assets']))
            continue
        if payload['browser_target']=='legacy' or payload['browser_target']=='admin' and 'admin' not in name or payload['browser_target']=='chat' and 'admin' in name:
            continue
        results.extend(sys.modules[name.removesuffix('.py')].run_browser(os.getcwd(),payload['assets']))
    print('BROWSER_RESULT='+json.dumps(results))
    sys.exit(0 if all(r['status']=='pass' for r in results) else 1)
sys.exit(0 if result.wasSuccessful() else 1)
'''.replace('PAYLOAD',repr(encoded))
    result=subprocess.run(['ssh','-o','BatchMode=yes',args.host,'/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python','-'],input=script,text=True,
        encoding='utf-8',capture_output=True,timeout=900)
    backend_result=None
    for line in result.stdout.splitlines():
        if line.startswith('BROWSER_RESULT='):
            browser_results=json.loads(line[len('BROWSER_RESULT='):])
            if args.artifact_dir:
                destination=(project/args.artifact_dir).resolve()
                if not destination.is_relative_to((project/'Reports').resolve()) or destination.exists():
                    raise ValueError('screenshot artifacts require a new directory under Reports')
                destination.mkdir(parents=True)
                for index,item in enumerate(browser_results):
                    if item.get('screenshot'):
                        target=destination/('screen-'+str(index).zfill(3)+'.png')
                        with target.open('xb') as generated:
                            generated.write(base64.b64decode(item['screenshot'],validate=True))
                        item['screenshot_path']=target.relative_to(project).as_posix()
            if not args.include_images:
                for item in browser_results:
                    item.pop('screenshot',None)
            if args.summary_only:
                for item in browser_results:
                    if 'requests' in item:
                        captured=item.pop('requests')
                        item['request_count']=len(captured) if isinstance(captured,(list,dict)) else captured
            if args.artifact_dir:
                report_path=destination/'results.json'
                with report_path.open('x',encoding='utf-8',newline='\n') as generated:
                    json.dump({'backend':backend_result,'browser':browser_results,'fixture_digest':payload['fixture_digest']},generated,ensure_ascii=False,indent=2)
            if args.summary_only and args.artifact_dir:
                print('BROWSER_SUMMARY='+json.dumps({'views':len(browser_results),'checks':sum(len(item.get('checks',[])) for item in browser_results),
                    'failures':[{'view':item.get('view'),'width':item.get('width'),'theme':item.get('theme'),'error':item.get('error')} for item in browser_results if item['status']!='pass'],
                    'details':str(report_path.relative_to(project))}))
            else:
                print('BROWSER_RESULT='+json.dumps(browser_results))
        else:
            if line.startswith('{"platform":'):
                backend_result=json.loads(line)
            print(line)
    if args.summary_only:
        separator=result.stderr.find('='*10)
        detail=result.stderr[separator:] if separator>=0 else '\n'.join(result.stderr.splitlines()[-5:])
        print(detail,end='')
    else:
        print(result.stderr,end='')
    raise SystemExit(result.returncode)


if __name__=='__main__':
    main()
