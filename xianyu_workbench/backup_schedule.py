"""Opt-in offline backup tick. No host scheduler installation or online backup."""
from __future__ import annotations

import os
import re
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

from filelock import FileLock, Timeout

from .backup import check_local_paths, create_backup, validate_archive

NAME = re.compile(r'^scheduled-(\d{16})-[a-f0-9]{32}\.zip$')


def tick(directory, destination, vault, *, enabled=False, interval_s=86400, keep=7, now=None):
    if not enabled:
        return 'disabled'
    if type(interval_s) is not int or not 3600 <= interval_s <= 2592000 or type(keep) is not int or not 1 <= keep <= 100:
        raise ValueError('备份间隔须为3600～2592000秒，保留1～100份')
    directory, destination = Path(directory).absolute(), Path(destination).absolute()
    check_local_paths(directory)
    check_local_paths(destination)
    if destination == directory or directory in destination.parents:
        raise ValueError('调度备份目录必须在数据目录之外')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.chmod(0o700)
    for name in ('schedule.lock', 'owner'):
        if (destination / name).is_symlink():
            raise ValueError('调度元数据不可为符号链接')
    try:
        with FileLock(str(destination / 'schedule.lock'), timeout=0):
            owner = destination / 'owner'
            identity = {'purpose': 'offline-backup-schedule-v1', 'source': str(directory)}
            if owner.exists():
                if vault.open(owner.read_text()) != identity:
                    raise ValueError('调度目录不属于此数据源')
            else:
                if any(p.name != 'schedule.lock' for p in destination.iterdir()):
                    raise ValueError('新调度目录必须为空')
                fd = os.open(owner, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(vault.seal(identity))
            backups = []
            for path in destination.iterdir():
                match = NAME.fullmatch(path.name)
                if match:
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('备份类型无效')
                    backups.append((int(match[1]) / 1000, path))
                elif path.name not in ('owner', 'schedule.lock'):
                    raise ValueError('专属调度目录包含未知文件，停止自动清理')
            if len(backups) > 101:
                raise ValueError('调度目录超出有界扫描数量')
            now = time.time() if now is None else now
            if backups and now - max(t for t, _ in backups) < interval_s:
                return 'not_due'
            output = destination / f'scheduled-{int(now * 1000):016d}-{uuid.uuid4().hex}.zip'
            try:
                create_backup(directory, output, vault)
            except Timeout:
                return 'busy'
            backups.append((now, output))
            # Validate every candidate before deleting anything. Corruption stops retention.
            for _, path in backups:
                with tempfile.TemporaryDirectory(prefix='xy-schedule-check-') as stage:
                    with zipfile.ZipFile(path) as archive:
                        validate_archive(archive, Path(stage), vault)
            for _, path in sorted(backups, key=lambda entry: (entry[0], entry[1].name))[:-keep]:
                path.unlink()
            return 'created'
    except Timeout:
        return 'busy'
