"""Submit the two synthetic regression mails through a normal production browser, once each."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

# The release directory is private and sits outside the app's Python import path.
sys.path.append('/home/nekohost/services/Mini-Server-Web-EqMgmt')
from verify_live_mail import exercise, reload_chat
from verify_production_entry import BASE, LOGIN, ROOT, LiveBrowser, read_db, record


def main():
    release = Path(sys.argv[1]).resolve()
    out = release/'live-mail'
    if socket.gethostname() != 'nkhst-pentium' or release.parent != ROOT/'instance/releases' or not release.name.startswith('20261105-ai-ux-mail-fidelity-'):
        raise RuntimeError('unexpected target')
    os.umask(0o077)
    out.mkdir(mode=0o700, exist_ok=True)
    if (out/'verified.json').exists():
        raise RuntimeError('browser verification already completed')
    cases = json.loads((release/'cases.json').read_bytes())
    ids = {'E1':('en-ko','xhigh','mail-20261109-r2','negative-scope-20261110-v1'),
           'K1':('ko-en','low','mail-20261110-terms-r3','source-sender-20261110-v1')}
    with read_db(ROOT/'equipment.db') as db:
        user = db.execute("SELECT UserId,Role,IsDeleted,IsDeactivated FROM users WHERE LoginId=?",(LOGIN,)).fetchone()
        assert user and user[1]=='user' and all((v or 'N')=='N' for v in user[2:])
    with read_db(ROOT/'instance/ai/assistant.sqlite3') as db:
        models = db.execute('SELECT m.id FROM ai_provider_models m JOIN ai_providers p ON p.id=m.provider WHERE m.upstream=? AND p.name=? AND p.enabled=1 AND p.retired=0 AND m.published=1 AND m.present=1',('qwen3.8-flash-next-iq3_xxs','260Strata')).fetchall()
        assert len(models)==1
    password = sys.stdin.readline().rstrip('\r\n')
    assert password
    with tempfile.TemporaryDirectory(prefix='eqmail-browser-') as profile:
        browser = LiveBrowser(profile,1380,960)
        try:
            browser.navigate('/login')
            browser.wait_for("document.querySelector('#loginForm') && typeof window.getCSRFToken==='function'",'login')
            browser.script("document.getElementById('LoginId').value=arguments[0];document.getElementById('Password').value=arguments[1];document.getElementById('loginForm').requestSubmit()",LOGIN,password)
            del password
            browser.wait_for("location.origin==='https://nekohost.org' && location.pathname!=='/login' && document.readyState!=='loading'",'user logged in')
            conversation = None
            for row in cases:
                if row['id'] not in ids:
                    continue
                direction,level,revision,policy = ids[row['id']]
                subject,rest = row['original'].split('\n',1)
                source = subject + ' [' + release.name[-6:] + ']\n' + rest
                language = '한국어' if direction=='en-ko' else '영어'
                question = f'다음 이메일을 {language}로 번역해 주세요.\n\n'+source
                from verify_live_mail import state
                saved = state(user[0],question)
                if saved:
                    reload_chat(browser,saved['conversation'])
                conversation = exercise(browser,user[0],models[0][0],out,conversation,(direction,level,revision,source))
                file = out/(direction+'.json')
                evidence = json.loads(file.read_bytes())
                saved = state(user[0],question)
                assert saved and json.loads(saved['route_snapshot'])['mail_fidelity_revision']==policy
                assert evidence['state']=='done' and evidence['restored_same'] and evidence['display']==evidence['stored']
                evidence['settings']['mail_fidelity_revision']=policy
                record(file,evidence)
            record(out/'verified.json',{'status':'pass','account':LOGIN,'role':'user','origin':BASE,'reopened':True,
                                       'conversation':conversation,'chromium':browser.cdp('Browser.getVersion',{})['product']})
        finally:
            browser.close()


if __name__=='__main__':
    main()
