#!/usr/bin/env python3
"""[MINI-COMMENT: ASSISTANT.WEB.RUNTIME] [EN rev.1]
[Role] Prepares only the equipment assistant's private, hash-locked search virtualenv on its authorized Linux host.
[Dependencies] Existing Python venv/pip and reviewed binary wheel lock; no sudo, container, listener or base app package change.
[Impact] Existing ready environments are verified and reused; partial installs stay fail-closed for review and are never recursively removed or overlaid.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
NAME = 'runtime-ddgs-9.6.1-primp-0.15.0'


def prepare(lock):
    """[Role] Installs pinned wheels in a new private child directory after validating host/user/path and lock digest.
    [Dependencies] Python3.12 Linux and an immutable reviewed lock string. [Impact] No application code, DB, settings, service or existing virtualenv is overwritten.
    """
    if os.name != 'posix' or socket.gethostname() != 'nkhst-pentium' or os.geteuid() != 1000 or sys.version_info[:2] != (3,12):
        raise PermissionError('fixed equipment Linux Python3.12 host/user required')
    base = ROOT/'instance/web-search'
    if not base.exists():
        base.mkdir(mode=0o700)
    for path in (ROOT/'instance',base):
        info = path.lstat()
        if path.resolve()!=path or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid():
            raise PermissionError('owned private runtime parent required')
    os.chmod(base,0o700)
    runtime = base/NAME
    digest = hashlib.sha256(lock).hexdigest()
    if runtime.exists():
        marker = json.loads((runtime/'ready.json').read_text())
        if runtime.is_symlink() or runtime.stat().st_uid!=os.geteuid() or marker.get('lock_sha256')!=digest or marker.get('runtime')!=NAME:
            raise ValueError('existing or partial search runtime requires review; no overwrite performed')
        return {'status':'ready','runtime':NAME,'lock_sha256':digest,'reused':True}
    os.umask(0o077)
    runtime.mkdir(mode=0o700)
    (runtime/'requirements.lock').write_bytes(lock)
    subprocess.run([sys.executable,'-m','venv',str(runtime)],check=True,timeout=35)
    install = subprocess.run([str(runtime/'bin/python'),'-m','pip','install','--disable-pip-version-check','--no-cache-dir',
        '--require-hashes','--only-binary=:all:','-r',str(runtime/'requirements.lock')],capture_output=True,text=True,timeout=150)
    (runtime/'installation.log').write_text(install.stdout+install.stderr)
    if install.returncode:
        raise RuntimeError('search dependency installation failed; private log retained')
    check = subprocess.run([str(runtime/'bin/python'),'-I','-B','-c',
        "from importlib.metadata import version;assert version('ddgs')=='9.6.1' and version('primp')=='0.15.0'"],check=True,capture_output=True,timeout=10)
    marker={'status':'ready','runtime':NAME,'lock_sha256':digest,'separate_application_environment':True,'listener':False}
    with (runtime/'ready.json').open('x') as stream:
        json.dump(marker,stream)
    return {**marker,'reused':False}


def main():
    """[Role] Accepts only the reviewed lock file path; there is no shell, endpoint, command or delete option."""
    parser=argparse.ArgumentParser()
    parser.add_argument('--lock',type=Path,default=ROOT/'tools/requirements-web-search.lock')
    args=parser.parse_args()
    print(json.dumps(prepare(args.lock.read_bytes())))


if __name__=='__main__':
    main()
