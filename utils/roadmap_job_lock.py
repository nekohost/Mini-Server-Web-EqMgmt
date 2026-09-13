"""제안 008 외부 알림 작업과 DB 복원의 교차 프로세스 배제."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def notification_lock(database):
    """[역할] 같은 DB의 알림/복원을 직렬화. [의존성 관계] Linux flock. [변경 시 영향도] 충돌 시 즉시 실패, 기존 DB 유지."""
    if os.name != 'posix':
        raise OSError('notification/restore coordination requires Linux')
    import fcntl
    database = Path(database).resolve(strict=True)
    descriptor = os.open(database.with_name(database.name + '.notification.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
