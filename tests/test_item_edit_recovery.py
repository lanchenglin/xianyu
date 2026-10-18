import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from tests.test_item_edit import ready
from tests.test_workbench import ADMIN, AGENT
from xianyu_workbench.app import create_app
from xianyu_workbench.backup import create_backup, restore_backup
from xianyu_workbench.config import Settings
from xianyu_workbench.service import Service


@pytest.mark.parametrize('state,expected', [('approved', 'expired'), ('running', 'unconfirmed'), ('submitted', 'submitted')])
def test_restore_revokes_edit_protocol_and_approval(tmp_path, state, expected):
    settings = Settings(tmp_path / 'data', ADMIN, AGENT, Fernet.generate_key().decode(),
                        worker_enabled=False, read_interval=0, write_interval=0)
    app = create_app(settings)
    with TestClient(app, headers={'Authorization': 'Bearer ' + ADMIN}) as client:
        service = app.state.service
        aid, action, _ = ready(client, service)
        vault = service.vault
        if state != 'approved':
            service.db.execute('UPDATE actions SET state=?,result=? WHERE id=?',
                               (state, vault.seal({'stage': 'submitting'}), action['id']))
    archive = tmp_path / 'edit.zip'
    create_backup(settings.data_dir, archive, vault)
    restore_backup(settings.data_dir, archive, vault)
    restored = Service(settings)
    assert restored.db.one('SELECT value FROM settings WHERE key=?', ('edit-protocol:' + aid,)) is None
    assert restored.db.one('SELECT state FROM actions WHERE id=?', (action['id'],))['state'] == expected
    assert not restored.run_once()
    if state == 'running':
        from tests.test_item_edit import protocol
        from xianyu_workbench.item_edit import EditProtocol, history_guard, save_protocol
        from xianyu_workbench.provider import Problem
        with pytest.raises(Problem, match='不确定编辑'):
            save_protocol(restored, aid, EditProtocol.model_validate(protocol()))
        p = protocol()
        p['revision'] = 'new-after-restore'
        with pytest.raises(Problem, match='不确定提交'):
            history_guard(restored, aid, {'item_id': '777', '_edit_snapshot': {'protocol': p}}, 'new-key')
