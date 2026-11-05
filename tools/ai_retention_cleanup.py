#!/usr/bin/env python3
"""[MINI-COMMENT: ASSISTANT.RETENTION.CLI]
[EN rev.1]
[Role] Runs bounded AI-only expiration cleanup independently of logins, workers and model connections.
[Dependencies] Linux flock, a protected configured v4 AI path/epoch and Store's atomic purge transactions.
[Impact] Installation is explicit; shared Strata, equipment data and retained audit artifacts are never contacted.
"""
import argparse
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sqlite3
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.ai_assistant.store import Store

LOG = logging.getLogger('equipment_assistant_retention')


def unique_json_object(pairs):
    """[Role] Rejects duplicate ledger keys. [Dependencies] JSON object pairs. [Impact] No ambiguous restore identities."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate deletion ledger field')
        result[key] = value
    return result


@contextmanager
def cleanup_lock(path):
    """[Role] Admits only one cleanup process for the exact configured AI database.
    [Dependencies] Linux nonblocking flock and a private no-follow lock file beside the AI database.
    [Impact] Concurrent timer/manual launches exit safely; the kernel releases the lock after crashes.
    """
    if os.name != 'posix':
        raise RuntimeError('retention cleanup requires Linux')
    import fcntl
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


def main(argv=None):
    """[Role] Validates explicit maintenance bounds and reports counts or a retryable cleanup failure.
    [Dependencies] Deployment environment, independent process lock and short Store transactions.
    [Impact] No exception includes conversation content, a title, a model route or credentials.
    """
    parser = argparse.ArgumentParser(description='Purge expired AI conversation content in bounded batches.')
    parser.add_argument('--database', default=os.environ.get('USER_AI_DATABASE'))
    parser.add_argument('--epoch', default=os.environ.get('USER_AI_DATABASE_EPOCH'))
    parser.add_argument('--batch-size', type=int, default=25)
    parser.add_argument('--max-batches', type=int, default=4)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--export-deletions', action='store_true', help='export content-free tombstones before offline DB replacement')
    actions.add_argument('--reconcile-deletions', metavar='PROTECTED_LEDGER_JSON', help='apply latest tombstones to a restored offline v4 DB')
    args = parser.parse_args(argv)
    if not args.database or not args.epoch or not 1 <= args.batch_size <= 100 or not 1 <= args.max_batches <= 100:
        parser.error('configure USER_AI_DATABASE/USER_AI_DATABASE_EPOCH and batch bounds 1..100')
    path = Path(args.database).absolute()
    if not path.is_file() or path.is_symlink() or path.parent.is_symlink():
        parser.error('the existing protected AI database is required')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        with cleanup_lock(path.with_name(path.name + '.retention.lock')) as acquired:
            if not acquired:
                result = {'status': 'already_running', 'purged': 0}
            else:
                # A timer is never an activation/migration entry point for a v3 or partial deployment.
                with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5) as db:
                    if [r[0] for r in db.execute('SELECT version FROM ai_meta')] != [4]:
                        raise ValueError('retention requires an explicitly activated v4 database')
                store = Store(path, epoch=args.epoch)
                if args.export_deletions:
                    print(json.dumps(store.export_deletion_ledger(), separators=(',', ':')))
                    return 0
                if args.reconcile_deletions:
                    ledger_path = Path(args.reconcile_deletions)
                    if not ledger_path.is_file() or ledger_path.is_symlink() or ledger_path.stat().st_size > 8 * 1024 * 1024:
                        raise ValueError('protected deletion ledger must be a regular file up to 8 MiB')
                    ledger_fd = os.open(str(ledger_path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                    with os.fdopen(ledger_fd, 'rb') as ledger_file:
                        if not stat.S_ISREG(os.fstat(ledger_file.fileno()).st_mode):
                            raise ValueError('deletion ledger must be a regular file')
                        raw = ledger_file.read(8 * 1024 * 1024 + 1)
                    if len(raw) > 8 * 1024 * 1024:
                        raise ValueError('deletion ledger exceeds 8 MiB')
                    ledger = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_json_object)
                    result = {'status': 'ok', 'purged': 0, **store.reconcile_deletion_ledger(ledger)}
                else:
                    result = {'status': 'ok', **store.purge_expired(args.batch_size, args.max_batches)}
        print(json.dumps(result, separators=(',', ':')))
        LOG.info('retention status=%s purged=%s more_expired=%s', result['status'], result['purged'], result.get('more_expired', False))
        return 0
    except Exception as error:
        error_code = getattr(error, 'sqlite_errorname', None)
        if error_code is None and isinstance(error, OSError) and type(error.errno) is int:
            error_code = 'OS_ERRNO_' + str(error.errno)
        LOG.error('retention failed type=%s cause=%s retry=next-run', type(error).__name__, error_code or type(error).__name__)
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__, 'error_code': error_code, 'retry': 'next-run'}, separators=(',', ':')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
