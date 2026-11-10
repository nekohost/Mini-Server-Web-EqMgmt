"""Compose the reviewed security/provider changes onto the exact current release worktree."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[5]
STAGE = ROOT / 'Staging/20261110-provider-security'
HANDOFF = ROOT / 'Staging/20261109-ai-integrated/handoff'
SECURITY = ROOT / 'Staging/20261109-security-static'
TRANSLATION = ROOT / 'Staging/20261109-ai-translation'
CURRENT = 'dc60ed88a30274b22f1b752849bdd1b7e37db36d'


def lf(data):
    return data.replace(b'\r\n', b'\n')


def merge(path, current, candidate):
    """Apply the security/provider delta relative to the translation-only shared ancestor."""
    ancestor = lf((TRANSLATION / path).read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        inputs = [Path(tmp) / str(index) for index in range(3)]
        for target, data in zip(inputs, (current, ancestor, candidate)):
            target.write_bytes(data)
        result = subprocess.run(['git', 'merge-file', '-p', '-L', 'live', '-L', 'translation',
                                 '-L', 'security', *inputs], capture_output=True)
    if result.returncode == 0:
        return result.stdout
    old = (b'<<<<<<< live\n        [Role] Finalizes outcomes, persists verified mail text and releases definitively terminated execution guards.\n'
           b'=======\n        [Role] Finalizes the job and releases its guard in the same transaction as candidate promotion.\n>>>>>>> security\n')
    if path != 'utils/ai_assistant/store.py' or result.returncode != 1 or result.stdout.count(old) != 1:
        raise ValueError('unreviewed conflict in ' + path)
    return result.stdout.replace(old, b'        [Role] Persists verified mail output and releases execution guards in the transaction that finalizes a job or promotes a provider.\n')


def main():
    """Only selected product and test files enter the reversible Git patch."""
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=STAGE, text=True).strip() == CURRENT
    manifest = json.loads((HANDOFF / 'security.manifest.json').read_bytes())
    paths = set(manifest['changed_against_variant_base'])
    paths.update(p.relative_to(SECURITY).as_posix() for p in SECURITY.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths -= {'static/js/equipment_ai.js', 'tests/test_mail_translation_ui.js', 'utils/ai_assistant/translation.py'}
    changes = []
    with ZipFile(HANDOFF / 'security.zip') as archive:
        for path in sorted(paths):
            candidate = lf(archive.read('source/' + path))
            assert hashlib.sha256(candidate).hexdigest() == manifest['files'][path], path
            dest = STAGE / path
            current = lf(dest.read_bytes()) if dest.is_file() else b''
            if path in ('utils/ai_assistant/__init__.py', 'utils/ai_assistant/providers.py', 'utils/ai_assistant/store.py'):
                candidate = merge(path, current, candidate)
            else:
                base = subprocess.run(['git', 'show', manifest['base_commit'] + ':' + path], cwd=STAGE, capture_output=True)
                assert (lf(base.stdout) if base.returncode == 0 else b'') == current, path
            if current == candidate:
                continue
            changes.append(f'diff --git a/{path} b/{path}\n'.encode())
            if not dest.exists():
                changes.append(b'new file mode 100644\n')
            diff = list(difflib.diff_bytes(difflib.unified_diff, current.splitlines(True), candidate.splitlines(True),
                                           (f'a/{path}' if dest.exists() else '/dev/null').encode(), f'b/{path}'.encode()))
            for line in diff:
                changes.append(line if line.endswith(b'\n') else line + b'\n\\ No newline at end of file\n')
    patch = b''.join(changes)
    for mode in ('--check', '--index'):
        subprocess.run(['git', 'apply', mode, '--whitespace=nowarn', '-'], cwd=STAGE, input=patch, check=True)
    print('Verified handoff and applied source patch for', len(paths), 'reviewed paths.')


if __name__ == '__main__':
    main()
