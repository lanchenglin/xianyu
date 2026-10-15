"""Private, offline administrator backups. Never exposed through HTTP or MCP."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile
from contextlib import closing
from pathlib import Path

from cryptography.fernet import InvalidToken
from filelock import FileLock

from .db import DB, MIGRATIONS
from .security import Vault, canonical

MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILES = 10000


def validate_archive(archive, stage, vault):
    entries = archive.infolist()
    names = [entry.filename for entry in entries]
    check_limits([entry.file_size for entry in entries])
    if len(set(names)) != len(names):
        raise ValueError('备份超过大小/数量限制或包含重复项')
    for entry in entries:
        name = entry.filename
        if (name not in ('manifest.json', 'workbench.db')
                and not (name.startswith('assets/') and len(name.split('/')) == 2
                         and name.split('/')[1] not in ('', '.', '..'))):
            raise ValueError('备份路径无效')
        if ('\\' in name or ':' in name or entry.is_dir()
                or (entry.external_attr >> 16) & 0o170000 not in (0, 0o100000)
                or entry.flag_bits & 1):
            raise ValueError('备份文件类型无效')
    if 'manifest.json' not in names or archive.getinfo('manifest.json').file_size > 2 * 1024 * 1024:
        raise ValueError('备份 manifest 缺失或过大')
    manifest = json.loads(archive.read('manifest.json'))
    if (manifest.get('format') != 1 or not isinstance(manifest.get('schema'), int)
            or not 1 <= manifest['schema'] <= len(MIGRATIONS)
            or set(names) != {'manifest.json', *manifest.get('files', {})}
            or 'workbench.db' not in manifest['files']):
        raise ValueError('备份格式/版本/文件清单无效')
    try:
        if vault.open(manifest['key_check']) != {'purpose': 'xianyu-backup-v1'}:
            raise ValueError('备份密钥校验失败')
    except InvalidToken:
        raise ValueError('备份密钥校验失败') from None
    for name, expected in manifest['files'].items():
        if archive.getinfo(name).file_size != expected['size']:
            raise ValueError('备份大小不符')
        target = stage / name
        target.parent.mkdir(exist_ok=True, mode=0o700)
        digest = hashlib.sha256()
        with archive.open(name) as source, target.open('xb') as dest:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                dest.write(chunk)
        target.chmod(0o600)
        if digest.hexdigest() != expected['sha256']:
            raise ValueError('备份哈希不符')
    with closing(sqlite3.connect(stage / 'workbench.db')) as c:
        if (c.execute('PRAGMA user_version').fetchone()[0] != manifest['schema']
                or c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok'
                or c.execute('PRAGMA foreign_key_check').fetchone()):
            raise ValueError('备份数据库校验失败')
        DB.validate_key(c, vault)
        assets = set()
        for filename, expected in c.execute('SELECT filename,sha256 FROM assets'):
            name = 'assets/' + filename
            if name not in manifest['files'] or manifest['files'][name]['sha256'] != expected:
                raise ValueError('备份素材关系无效')
            assets.add(name)
        if set(manifest['files']) != {'workbench.db', *assets}:
            raise ValueError('备份含非素材数据')


def check_local_paths(directory):
    for path in (directory, *directory.parents):
        if path.is_symlink():
            raise ValueError('数据路径不可包含符号链接')
    for name in ('server.lock', 'restore-in-progress', 'workbench.db', 'workbench.db-wal', 'workbench.db-shm', 'assets', 'runtime'):
        if (directory / name).is_symlink():
            raise ValueError('数据文件不可为符号链接')


def check_limits(sizes):
    if (len(sizes) > MAX_FILES or any(size < 0 or size > MAX_TOTAL_BYTES for size in sizes)
            or sum(sizes) > MAX_TOTAL_BYTES):
        raise ValueError('备份超过恢复支持的大小/数量限制')


def hash_file(path, expected_size):
    digest = hashlib.sha256()
    remaining = expected_size
    with path.open('rb') as stream:
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError('备份文件大小变化')
            digest.update(chunk)
            remaining -= len(chunk)
        if stream.read(1):
            raise ValueError('备份文件大小变化')
    return digest.hexdigest()


def create_backup(directory: Path, output: Path, vault: Vault) -> None:
    check_local_paths(directory)
    with FileLock(str(directory / 'server.lock'), timeout=0):
        database = directory / 'workbench.db'
        check_limits([database.stat().st_size, 0])  # Reserve the manifest entry before copying.
        with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as source:
            version = source.execute('PRAGMA user_version').fetchone()[0]
            if version != len(MIGRATIONS):
                raise ValueError('备份数据库版本无效')
            # page_count includes committed WAL pages not yet reflected in the DB file's stat.
            db_size = source.execute('PRAGMA page_count').fetchone()[0] * source.execute('PRAGMA page_size').fetchone()[0]
            check_limits([db_size, 0])
            files = {'workbench.db': database}
            metadata = {'workbench.db': {'size': db_size, 'sha256': '0' * 64}}
            expected_hashes = {}
            for filename, expected in source.execute('SELECT filename,sha256 FROM assets'):
                path = directory / 'assets' / filename
                if (Path(filename).name != filename or '\\' in filename or ':' in filename
                        or path.is_symlink() or not path.is_file()):
                    raise ValueError('素材路径无效')
                name = 'assets/' + filename
                files[name] = path
                metadata[name] = {'size': path.stat().st_size, 'sha256': '0' * 64}
                expected_hashes[name] = expected
                check_limits([0, *(entry['size'] for entry in metadata.values())])
            manifest = {'format': 1, 'schema': version,
                        'key_check': vault.seal({'purpose': 'xianyu-backup-v1'}), 'files': metadata}
            manifest_size = len(canonical(manifest).encode('utf-8'))
            if manifest_size > 2 * 1024 * 1024:
                raise ValueError('备份 manifest 超过大小限制')
            check_limits([manifest_size, *(entry['size'] for entry in metadata.values())])
            # All size/count checks precede validation scans, hashing and snapshot allocation.
            if (source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok'
                    or source.execute('PRAGMA foreign_key_check').fetchone()):
                raise ValueError('备份数据库完整性无效')
            DB.validate_key(source, vault)
            with tempfile.TemporaryDirectory(prefix='xy-backup-') as temporary:
                snapshot = Path(temporary) / 'workbench.db'
                with closing(sqlite3.connect(snapshot)) as target:
                    source.backup(target)
                if snapshot.stat().st_size != db_size:
                    raise ValueError('备份数据库大小变化')
                files['workbench.db'] = snapshot
                for name, path in files.items():
                    actual = hash_file(path, metadata[name]['size'])
                    if name in expected_hashes and actual != expected_hashes[name]:
                        raise ValueError('素材校验失败')
                    metadata[name]['sha256'] = actual
                fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(fd, 'wb') as stream, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
                        archive.writestr('manifest.json', canonical(manifest))
                        for name, path in files.items():
                            remaining = metadata[name]['size']
                            digest = hashlib.sha256()
                            with path.open('rb') as src, archive.open(name, 'w') as dest:
                                while remaining:
                                    chunk = src.read(min(1024 * 1024, remaining))
                                    if not chunk:
                                        raise ValueError('备份文件大小变化')
                                    dest.write(chunk)
                                    digest.update(chunk)
                                    remaining -= len(chunk)
                                if src.read(1) or digest.hexdigest() != metadata[name]['sha256']:
                                    raise ValueError('备份文件内容变化')
                except BaseException:
                    output.unlink(missing_ok=True)
                    raise


def restore_backup(directory: Path, archive_path: Path, vault: Vault) -> Path:
    check_local_paths(directory)
    with FileLock(str(directory / 'server.lock'), timeout=0):
        with tempfile.TemporaryDirectory(prefix='.restore-', dir=directory.parent) as temporary:
            stage = Path(temporary)
            with zipfile.ZipFile(archive_path) as archive:
                validate_archive(archive, stage, vault)
            db = DB(stage, vault)
            with db.connect() as c:
                c.execute("UPDATE accounts SET paused=1,pause_reason='备份恢复后需人工核实'")
                c.execute('UPDATE monitors SET enabled=0')
                notification_config = c.execute("SELECT value FROM settings WHERE key='notifications'").fetchone()
                if notification_config:
                    value = vault.open(notification_config['value'])
                    value['enabled'] = False
                    c.execute("UPDATE settings SET value=? WHERE key='notifications'", (vault.seal(value),))
                c.execute("UPDATE notification_deliveries SET state='cancelled' WHERE state IN ('pending','retry')")
                c.execute("UPDATE notification_deliveries SET state='unknown',error='interrupted' WHERE state='sending'")
                c.execute("UPDATE actions SET state='expired',error='恢复后旧申请失效；禁止直接重放' WHERE state IN ('pending','approved')")
                c.execute("UPDATE actions SET state='unconfirmed',error='恢复时执行结果不确定；禁止重试' WHERE state='running'")
                c.execute('INSERT INTO audit(created,actor,event,target,detail) VALUES(?,?,?,?,?)',
                          (time.time(), 'local-admin', 'backup.restored', '', '{}'))
            rollback = directory.parent / ('restore-rollback-' + uuid.uuid4().hex)
            rollback.mkdir(mode=0o700)
            marker = directory / 'restore-in-progress'
            previous_marker = marker.read_bytes() if marker.exists() else None
            with marker.open('w', encoding='utf-8') as stream:
                stream.write(str(rollback))
                stream.flush()
                os.fsync(stream.fileno())
            marker.chmod(0o600)
            moved = []
            installed = []
            try:
                for name in ('workbench.db', 'workbench.db-wal', 'workbench.db-shm', 'assets', 'runtime'):
                    path = directory / name
                    if path.exists():
                        os.replace(path, rollback / name)
                        moved.append(name)
                for name in ('workbench.db', 'assets'):
                    if (stage / name).exists():
                        os.replace(stage / name, directory / name)
                        installed.append(name)
            except BaseException:
                for name in installed:
                    path = directory / name
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                for name in moved:
                    os.replace(rollback / name, directory / name)
                if previous_marker is not None:
                    marker.write_bytes(previous_marker)
                else:
                    marker.unlink()
                raise
            marker.unlink()
            return rollback
