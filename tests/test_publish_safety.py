import time

import pytest
from cryptography.fernet import Fernet

from xianyu_workbench.config import Settings
from xianyu_workbench.provider import Problem
from xianyu_workbench.service import Service


def test_live_publish_stops_before_bridge_when_snapshot_unavailable(tmp_path):
    service = Service(Settings(tmp_path, 'a' * 40, 'b' * 40, Fernet.generate_key().decode(),
                               live_enabled=True, worker_enabled=False))
    service.db.execute("INSERT INTO accounts(id,label,mode,secret,created) VALUES('a','fake','live',?,?)",
                       (service.vault.seal({'unb': '123'}), time.time()))
    with pytest.raises(Problem) as error:
        service.provider.call('a', 'item.publish', {}, write=True)
    assert error.value.code == 'publish_snapshot_unavailable'
    assert service.db.one("SELECT last_write FROM accounts WHERE id='a'")['last_write'] == 0
