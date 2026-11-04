"""[MINI-COMMENT: ASSISTANT.LINUX.FIXTURE.RUNNER]
[EN rev.4]
[Role] Transfers audited candidate source in memory to the authorized Linux fixture host over SSH.
[Dependencies] Local source reads, subprocess SSH and Python stdlib; never imports the app on Windows.
[Impact] Reports measured Linux test duration; no remote source/config file is modified and synthetic DBs are removed by their tests.
"""
import argparse
import base64
import json
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
    args=parser.parse_args()
    overlay=Path(__file__).resolve().parents[1]
    project=overlay if (overlay/'AGENTS.md').is_file() else overlay.parents[2]
    sources={'utils':{'source':'','package':True}}
    for file in (project/'utils').glob('*.py'):
        sources['utils.'+file.stem]={'source':file.read_text(encoding='utf-8-sig'),'package':False}
    for file in (overlay/'utils'/'ai_assistant').glob('*.py'):
        name='utils.ai_assistant'+('' if file.stem=='__init__' else '.'+file.stem)
        sources[name]={'source':file.read_text(encoding='utf-8-sig'),'package':file.stem=='__init__'}
    candidate_paths=('templates/equipment_ai.html','templates/equipment_ai_providers.html',
        'static/css/equipment_ai.css','static/css/equipment_ai_providers.css',
        'static/js/equipment_ai.js','static/js/equipment_ai_providers.js','static/js/session_timer.js')
    assets={relative:(overlay/relative).read_text(encoding='utf-8-sig') for relative in candidate_paths}
    # Pin the reviewed local frame/common assets too; the fixture host may be on an older deployment.
    for relative in ('templates/root_frame.html','templates/miniserver_frame.html','static/css/layout.css','static/css/components.css',
            'static/css/roadmap.css','static/js/common.js','static/js/roadmap_preferences.js',
            'static/js/navigation.js','static/js/menu_cards.js','static/js/catalog_requests.js','static/js/tailwindcss.js'):
        assets.setdefault(relative,(project/relative).read_text(encoding='utf-8-sig'))
    payload={'sources':sources,'assets':assets,'app':(overlay/'app.py').read_text(encoding='utf-8-sig'),
             'test':(overlay/'tests'/'test_equipment_ai.py').read_text(encoding='utf-8-sig'),
             'provider_test':(overlay/'tests'/'test_multi_provider_ai.py').read_text(encoding='utf-8-sig'),
             'browser':(overlay/'tests'/'assistant_browser_fixture.py').read_text(encoding='utf-8-sig') if args.browser or args.browser_only else None,
             'browser_only':args.browser_only,'provider_only':args.provider_only}
    encoded=base64.b64encode(zlib.compress(json.dumps(payload,ensure_ascii=False).encode())).decode()
    script='''import base64,zlib,json,os,sys,time,types,importlib.abc,importlib.util,unittest,tempfile,subprocess
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
dependency_tmp=tempfile.TemporaryDirectory(prefix='eq-ai-dependencies-')
if importlib.util.find_spec('cryptography') is None:
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-cache-dir','--only-binary=:all:','--quiet','--target',dependency_tmp.name,'cryptography==50.0.2'],check=True,timeout=90)
    sys.path.insert(0,dependency_tmp.name)
os.chdir('/home/nekohost/services/Mini-Server-Web-EqMgmt')
os.environ['EQ_TEST_PROJECT_ROOT']=os.getcwd()
payload=json.loads(zlib.decompress(base64.b64decode(PAYLOAD)))
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
    exec(compile(payload['provider_test'],'<candidate>/tests/test_multi_provider_ai.py','exec'),providers.__dict__)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(providers.ProviderTests))
started=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'platform':sys.platform,'python':sys.version.split()[0],'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'elapsed_seconds':round(time.monotonic()-started,3),'production_app_imported':False,'production_database_opened':False}))
if payload['browser'] and result.wasSuccessful():
    browser=types.ModuleType('assistant_browser_fixture')
    exec(compile(payload['browser'],'<candidate>/tests/assistant_browser_fixture.py','exec'),browser.__dict__)
    results=browser.run_browser(os.getcwd(),payload['assets'])
    print('BROWSER_RESULT='+json.dumps(results))
    sys.exit(0 if all(r['status']=='pass' for r in results) else 1)
sys.exit(0 if result.wasSuccessful() else 1)
'''.replace('PAYLOAD',repr(encoded))
    result=subprocess.run(['ssh','-o','BatchMode=yes',args.host,'/home/nekohost/services/Mini-Server-Web-EqMgmt/.venv/bin/python','-'],input=script,text=True,
        encoding='utf-8',capture_output=True,timeout=360)
    for line in result.stdout.splitlines():
        if line.startswith('BROWSER_RESULT='):
            browser_results=json.loads(line[len('BROWSER_RESULT='):])
            if not args.include_images:
                for item in browser_results:
                    item.pop('screenshot',None)
            print('BROWSER_RESULT='+json.dumps(browser_results))
        else:
            print(line)
    print(result.stderr,end='')
    raise SystemExit(result.returncode)


if __name__=='__main__':
    main()
