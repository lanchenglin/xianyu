"""Offline recovery of fictional publish snapshots, never platform transport."""
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tests.test_publish_executor import ready
from tests.test_workbench import ADMIN, AGENT
from xianyu_workbench.app import create_app
from xianyu_workbench.backup import create_backup, restore_backup
from xianyu_workbench.config import Settings
from xianyu_workbench.provider import Problem
from xianyu_workbench.security import canonical
from xianyu_workbench.service import Service


@pytest.mark.parametrize('stage', ['prepared', 'uploading', 'submitting', 'verifying', 'verified'])
def test_publish_restore_preserves_private_stage_without_replay(tmp_path, monkeypatch, stage):
    settings = Settings(tmp_path / "data", ADMIN, AGENT, Fernet.generate_key().decode(),
                        worker_enabled=False, read_interval=0, write_interval=0)
    app = create_app(settings)
    with TestClient(app, headers={"Authorization": "Bearer " + ADMIN}) as client:
        service = app.state.service
        aid, action = ready(client, service)
        frozen = action['payload']
        result = {'stage': stage, 'uploads': [{'url': 'https://img.alicdn.com/private-fixture.png'}],
                  'ownership_verified': stage == 'verified', 'item_id': '777'}
        state = 'submitted' if stage == 'verified' else 'running'
        service.db.execute('UPDATE actions SET state=?,result=? WHERE id=?',
                           (state, service.vault.seal(result), action['id']))
        settings, vault = service.s, service.vault
    archive = tmp_path / 'publish-backup.zip'
    create_backup(settings.data_dir, archive, vault)
    restore_backup(settings.data_dir, archive, vault)
    restored = Service(settings)
    restored.start()
    try:
        row = restored.db.one('SELECT * FROM actions WHERE id=?', (action['id'],))
        assert row['state'] == ('submitted' if stage == 'verified' else 'unconfirmed')
        assert vault.open(row['payload']) == frozen
        assert vault.open(row['result']) == result
        protocol = restored.db.one('SELECT value FROM settings WHERE key=?', ('publish-protocol:' + aid,))
        assert vault.open(protocol['value'])['readback_status'] == frozen['_publish_snapshot']['executor']['readback_status']
        public = canonical(restored.action_view(row, 'agent'))
        for private in ('private-fixture.png', 'private-poi', 'credential_digest', 'fictional-once'):
            assert private not in public
        assert restored.provider.account(aid)['paused'] == 1
        assert not restored.db.one("SELECT id FROM actions WHERE state IN ('pending','approved','running')")
        monkeypatch.setattr(restored.provider, '_live', lambda *a, **k: pytest.fail('recovery must not transmit'))
        restored.db.execute('UPDATE accounts SET paused=0 WHERE id=?', (aid,))
        assert restored.run_once() is False
        with pytest.raises(Problem, match='不可执行'):
            restored.execute_one(action['id'], action['digest'])
    finally:
        restored.close()
