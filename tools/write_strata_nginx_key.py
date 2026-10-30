"""Create a private Nginx include on Linux. Never prints a key or overwrites a file."""
import argparse
import os
from pathlib import Path
import stat


def write_key_include(output, key):
    """[MINI-COMMENT: STRATA.KEY.INCLUDE]
    [EN rev.1]
    [Role] Creates an owner-only Nginx authorization include without shell interpolation.
    [Dependencies] A private parent directory and a key from an environment or protected file.
    [Impact] No key enters Git, HTML, process arguments or successful command output.
    """
    if os.name != 'posix':
        raise RuntimeError('Run this helper on the Linux server')
    if not isinstance(key, str) or not key or len(key) > 4096:
        raise ValueError('A non-empty API key is required')
    if any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ValueError('API key must be one printable line without whitespace')
    if key in ('REPLACE_WITH_API_KEY', '<actual-key>'):
        raise ValueError('Replace the placeholder with the existing upstream key')
    target = Path(output)
    if not target.is_absolute() or target.parent.resolve() != target.parent:
        raise ValueError('Use a real private directory without symlink parents')
    if not target.parent.exists():
        target.parent.mkdir(mode=0o700, parents=True)
    parent = target.parent.stat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise PermissionError('Parent directory must be owned by this user with mode 0700')
    escaped = key.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        stream.write('proxy_set_header Authorization "Bearer ' + escaped + '";\n')


def main():
    """[역할] 비대화형 키 파일 생성 명령입니다. [의존성 관계] Linux 파일 권한과 보호된 입력.
    [변경 시 영향도] 기존 파일 덮어쓰기와 키 값의 출력은 허용하지 않습니다.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--key-file', help='Owner-only plaintext file containing one existing key')
    arguments = parser.parse_args()
    if arguments.key_file:
        key_path = Path(arguments.key_file).absolute()
        metadata = key_path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError('Input key file must be an owner-only regular file')
        if metadata.st_size > 8192:
            raise ValueError('Input key file is too large')
        key = key_path.read_text(encoding='utf-8').rstrip('\r\n')
    else:
        key = os.environ.get('STRATA_API_KEY', '')
    write_key_include(arguments.output, key)
    print('Private Strata authorization include created.')


if __name__ == '__main__':
    main()
