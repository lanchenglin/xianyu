import pytest
from filelock import FileLock
from test_workbench import workbench as workbench_fixture

workbench = pytest.fixture(workbench_fixture.__wrapped__)


def test_offline_schedule_disabled_due_retention_and_lock(workbench, tmp_path):
    from xianyu_workbench import backup_schedule
    _, service = workbench
    dest = tmp_path / 'scheduled'
    assert backup_schedule.tick(service.s.data_dir, dest, service.vault, now=100000) == 'disabled'
    assert not dest.exists()
    assert backup_schedule.tick(service.s.data_dir, dest, service.vault, enabled=True, now=100000) == 'busy'
    assert not list(dest.glob('*.zip'))


def test_schedule_offline_success_due_and_bounded_retention(tmp_path):
    from cryptography.fernet import Fernet

    from xianyu_workbench import backup_schedule
    from xianyu_workbench.db import DB
    from xianyu_workbench.security import Vault
    vault = Vault(Fernet.generate_key().decode())
    data, dest = tmp_path / 'data', tmp_path / 'scheduled'
    DB(data, vault)
    for now in (100000, 104000, 108000):
        assert backup_schedule.tick(data, dest, vault, enabled=True, interval_s=3600, keep=2, now=now) == 'created'
    assert len(list(dest.glob('*.zip'))) == 2
    assert backup_schedule.tick(data, dest, vault, enabled=True, interval_s=3600, now=108001) == 'not_due'
    with FileLock(str(data / 'server.lock')):
        assert backup_schedule.tick(data, dest, vault, enabled=True, now=200000) == 'busy'
    assert len(list(dest.glob('*.zip'))) == 2
    unrelated = dest / 'manual.zip'
    unrelated.write_bytes(b'fiction')
    with pytest.raises(ValueError, match='未知'):
        backup_schedule.tick(data, dest, vault, enabled=True, now=300000)
    assert unrelated.read_bytes() == b'fiction'
    unrelated.unlink()
    (data / 'restore-in-progress').write_text('fiction')
    with pytest.raises(ValueError):
        backup_schedule.tick(data, dest, vault, enabled=True, now=300000)
    assert len(list(dest.glob('*.zip'))) == 2
