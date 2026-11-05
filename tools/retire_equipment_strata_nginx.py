#!/usr/bin/env python3
"""[MINI-COMMENT: ASSISTANT.RETIRE.NGINX]
[EN rev.2]
[Role] Replaces only the equipment site's legacy Strata include with the reviewed terminal deny rules.
[Dependencies] Explicit sudo by the existing operator, exact Git commit and successful assistant activation.
[Impact] Backs up the original, syntax-checks and rolls back on failure; never opens or changes the private upstream key.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROOT = Path('/home/nekohost/services/Mini-Server-Web-EqMgmt')
TARGET = Path('/etc/nginx/snippets/eqmgmt-strata.conf')
KEY = Path('/etc/nginx/private/strata-upstream-key.conf')


def save(path, content):
    """[Role] Creates a private operator-owned backup/result. [Dependencies] Exclusive no-follow descriptor. [Impact] Preserves prior artifacts."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chown(path, 1000, 1000)


def install(content, metadata):
    """[Role] Atomically installs one fixed include. [Dependencies] Root-owned canonical target directory. [Impact] Retains original owner/group/mode."""
    fd, pending = tempfile.mkstemp(prefix='.eqmgmt-strata-release-', dir=TARGET.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(pending, stat.S_IMODE(metadata.st_mode))
        os.chown(pending, metadata.st_uid, metadata.st_gid)
        os.replace(pending, TARGET)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


def main():
    """[Role] Executes one pre-reviewed privileged deployment step. [Dependencies] Exact release identity and activated marker. [Impact] No arbitrary target/key/service mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get('SUDO_USER') != 'nekohost':
        raise PermissionError('explicit operator sudo required')
    if not re.fullmatch('[0-9a-f]{40}', args.expected_head):
        raise ValueError('exact release commit required')
    head = subprocess.check_output(['git', '-c', 'safe.directory='+str(ROOT), '-C', str(ROOT), 'rev-parse', 'HEAD'], env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}, text=True).strip()
    if head != args.expected_head:
        raise ValueError('deployed commit mismatch')
    release = args.release
    if release.parent != ROOT/'instance/releases' or release.resolve() != release or release.stat().st_uid != 1000 or stat.S_IMODE(release.stat().st_mode) != 0o700:
        raise ValueError('private release boundary mismatch')
    if not (release/'activated.json').is_file():
        raise ValueError('assistant activation must succeed before old gateway retirement')
    metadata = TARGET.lstat()
    if TARGET.resolve() != TARGET or not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0:
        raise ValueError('fixed root-owned include required')
    matches = []
    for site in Path('/etc/nginx/sites-enabled').iterdir():
        if site.is_file():
            active = re.sub(r'#.*', '', site.read_text())
            if re.search(r'\binclude\s+'+re.escape(str(TARGET))+r'\s*;', active):
                if 'nekohost.org' not in active:
                    raise ValueError('include is referenced by an unrelated site')
                matches.append(site.name)
    if len(matches) != 1:
        raise ValueError('equipment include reference must be unique')
    source = (ROOT/'systemd/nginx-strata.conf.example').read_bytes()
    tracked = subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'-C',str(ROOT),'show',head+':systemd/nginx-strata.conf.example'],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    if source != tracked:
        raise ValueError('deny candidate differs from the exact committed release')
    if re.search(rb'(?m)^\s*(?:proxy_pass|auth_request|include|proxy_set_header)\b', source) or b'return 410;' not in source:
        raise ValueError('candidate is not a terminal retirement deny snippet')
    original = TARGET.read_bytes()
    key_before = KEY.stat() if KEY.exists() else None
    subprocess.run(['nginx','-t'], check=True)
    save(release/'nginx-include-before.conf', original)
    install(source, metadata)
    try:
        subprocess.run(['nginx','-t'], check=True)
        subprocess.run(['systemctl','reload','nginx'], check=True)
    except Exception:
        install(original, metadata)
        subprocess.run(['nginx','-t'], check=True)
        subprocess.run(['systemctl','reload','nginx'], check=True)
        raise
    key_after = KEY.stat() if KEY.exists() else None
    stable = lambda item: None if item is None else (item.st_dev,item.st_ino,item.st_mode,item.st_uid,item.st_gid,item.st_size,item.st_mtime_ns,item.st_ctime_ns)
    if stable(key_before) != stable(key_after):
        raise ValueError('private key metadata changed unexpectedly')
    result = {'status':'applied','include':str(TARGET),'site':matches[0],'commit':head,
              'old_sha256':hashlib.sha256(original).hexdigest(),'new_sha256':hashlib.sha256(source).hexdigest(),
              'nginx_test':'pass','nginx_reload':'pass','private_key_read_by_helper':False,'private_key_unchanged':True}
    save(release/'nginx-result.json', json.dumps(result,indent=2).encode())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
