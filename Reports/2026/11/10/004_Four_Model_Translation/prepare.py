"""Provision a private, independent evaluation copy of the shipped source and one shared measurement lock."""
import json, os, pathlib, shutil, subprocess, tarfile, tempfile
from io import BytesIO
root=pathlib.Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
old=pathlib.Path('/tmp/equipment-business-003-gj8ciulh')
rev='27af22a432006f3af4753b133878b7aff65b3642'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==rev
os.umask(0o077)
p=pathlib.Path(tempfile.mkdtemp(prefix='equipment-translation-four-'))
for n in ('study.py','evaluate_live.py'):shutil.copy2(old/n,p/n)
archive=subprocess.check_output(['git','archive',rev,'app.py','tests','utils','tools','templates','static'],cwd=root)
base=p/'base'
base.mkdir()
with tarfile.open(fileobj=BytesIO(archive)) as f:f.extractall(base,filter='data')
(p/'exclusive.lock').touch()
for arm in ('control','a','b','c','d'):
    f=p/arm;f.mkdir();os.link(p/'exclusive.lock',f/'exclusive.lock')
    if arm=='control':(f/'candidate').symlink_to(base,target_is_directory=True)
    else:shutil.copytree(base,f/'candidate')
print(p)
