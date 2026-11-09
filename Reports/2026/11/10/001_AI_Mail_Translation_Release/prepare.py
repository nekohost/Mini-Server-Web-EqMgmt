"""Assemble only the reviewed mail changes on the verified running Git revision."""
import ast
import difflib
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT=Path(__file__).resolve().parents[5]
STAGING=ROOT/'Staging'
OWNER=STAGING/'20261109-ai-translation'
RELEASE=STAGING/'20261110-mail-production'
BASE='b2271fd1b7829eb16ee9485f616dc7f78b7c5040'
OLD_ZIP='cc51d0d797ae6d535c07a3cad98f8e3b139bd70a1a3192d307bcaf3c5b5df36f'
FINAL_ZIP='e9b2076186da95dbb5d5cfdf5df1c7bd6811f811de92ced313786d834b36d114'


def lf(b):
    return b.replace(b'\r\n', b'\n')


def sha(b):
    return sha256(b).hexdigest()


def one(text, old, new):
    if text.count(old)!=1:
        raise ValueError('source anchor does not match exactly once: '+old[:75])
    return text.replace(old,new,1)


def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==BASE
    lock=json.loads((OWNER/'handoff.lock.json').read_text('utf8'))
    assert lock['base_commit']==BASE
    def owner(name):
        data=(OWNER/name).read_bytes()
        assert sha(data)==lock['files_sha256'][name] or sha(lf(data))==lock['files_sha256'][name]
        return lf(data)
    before=STAGING/'20261109-ai-integrated/handoff/operational.zip'
    after=STAGING/'20261109-ai-translation-gemini/handoff/operational.zip'
    assert sha(before.read_bytes())==OLD_ZIP and sha(after.read_bytes())==FINAL_ZIP
    files={k:owner(k) for k in ('utils/ai_assistant/__init__.py','utils/ai_assistant/providers.py')}
    with ZipFile(before) as prev, ZipFile(after) as final:
        read=lambda z,k:lf(z.read('source/'+k))
        for path in ('tests/test_mail_translation_ui.js','static/js/equipment_ai.js'):
            files[path]=read(final,path)
            assert files[path]==lf((OWNER/path).read_bytes())
        files['utils/ai_assistant/translation.py']=read(final,'utils/ai_assistant/translation.py')
        key='utils/ai_assistant/store.py'
        old=read(prev,key).decode().splitlines(keepends=True)
        new=read(final,key).decode().splitlines(keepends=True)
        text=owner(key).decode()
        hunks=[(i,j,k,h) for tag,i,j,k,h in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes() if tag!='equal']
        assert len(hunks)==3
        for i,j,k,h in hunks:
            # Integrate the entire tested hunk against the pre-CA store; verify unchanged trailing context.
            if i==j:
                text=one(text,''.join(old[i:i+2]),''.join(new[k:h])+''.join(old[i:i+2]))
            else:
                text=one(text,''.join(old[i:j]),''.join(new[k:h]))
        files[key]=text.encode()
        # Retain all final mail tests, using the fixture registration contract of the running provider registry.
        suite=read(final,'qa/test_mail_translation.py').decode()
        owner_suite=owner('evaluation/test_mail_translation.py').decode()
        method='    def test_other_providers_and_models_keep_selected_reasoning_and_block_mail_tool_calls('
        start=owner_suite.index(method)
        prior=owner_suite[start:owner_suite.index('\n    def ',start+len(method))]
        start=suite.index(method)
        suite=suite[:start]+prior+suite[suite.index('\n    def ',start+len(method)):]
        suite=one(suite,'Run with python -B evaluation/test_mail_translation.py in the staged tree.',
                  'Exercise the installed mail route with isolated equipment and model fixtures.')
        suite=one(suite,'from fixture import MODEL, ORIGIN, fixture, load_assistant','from mail_fixture import MODEL, ORIGIN, fixture')
        suite=one(suite,'from replay import','from mail_replay import')
        suite=one(suite,"assistant = load_assistant('candidate')",'from utils import ai_assistant as assistant')
        files['tests/test_mail_translation.py']=suite.encode()
        fx=owner('evaluation/fixture.py').decode()
        header=fx[:fx.index('STAGE =')].replace('import importlib.util\n','').replace('import sys\n','')
        files['tests/mail_fixture.py']=(header+fx[fx.index('MODEL ='):fx.index('def load_assistant')]+fx[fx.index('class Response:'):]).encode()
        replay=owner('evaluation/replay.py').decode()
        replay=replay[replay.index('def read_cases('):replay.index('def main():')].rstrip()+'\n'
        replay=one(replay,"STAGE / 'evaluation' / 'inputs'","Path(__file__).resolve().parent / 'mail_inputs'")
        files['tests/mail_replay.py']=('"""Drive recorded mail requests through the real worker with a synthetic transport."""\nimport json\nfrom pathlib import Path\nimport time\n\n\n'+replay).encode()
        for split in ('regression','unused'):
            files['tests/mail_inputs/'+split+'.json']=read(final,'evaluation/inputs/'+split+'.json')
    for name,data in files.items():
        if name.endswith('.py'):
            ast.parse(data.decode(),filename=name)
    RELEASE.mkdir(exist_ok=True)
    archive=RELEASE/'translation-release.zip'
    with ZipFile(archive,'w',compression=ZIP_DEFLATED) as out:
        for name,data in sorted(files.items()):
            info=ZipInfo(name,date_time=(2026,11,10,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=0o100644<<16
            out.writestr(info,data)
    result=dict(base_commit=BASE,reviewed_package=FINAL_ZIP,translation_only_zip=sha(archive.read_bytes()),
                files={k:sha(b) for k,b in sorted(files.items())})
    (Path(__file__).resolve().parent/'release-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(archive.name,result['translation_only_zip'],len(files))


if __name__=='__main__':
    main()
