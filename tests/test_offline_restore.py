"""New local structures survive offline restore without replaying approvals."""
from cryptography.fernet import Fernet

from xianyu_workbench.backup import create_backup, restore_backup
from xianyu_workbench.db import DB
from xianyu_workbench.security import Vault


def test_v12_local_records_restore_without_replay(tmp_path):
    vault = Vault(Fernet.generate_key().decode())
    root = tmp_path / 'data'
    db = DB(root, vault)
    with db.connect() as c:
        c.execute("INSERT INTO accounts(id,label,mode,created) VALUES('a','fiction','demo',1)")
        c.execute("INSERT INTO monitors(id,account_id,query,filters,interval_s) VALUES('m','a','fiction','{}',900)")
        c.execute("INSERT INTO price_samples(account_id,monitor_id,item_id,price,observed,mode) VALUES('a','m','123','10.00',1,'demo')")
        c.execute("INSERT INTO drafts(id,account_id,content,updated) VALUES('d','a',?,1)", (vault.seal({'title': 'fiction'}),))
        c.execute("INSERT INTO draft_imports VALUES('i','a','fixture-key','digest',1)")
        c.execute("INSERT INTO draft_import_rows VALUES('i',0,'d')")
    archive = tmp_path / 'private.zip'
    create_backup(root, archive, vault)
    restore_backup(root, archive, vault)
    assert db.one('SELECT COUNT(*) n FROM price_samples')['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM draft_import_rows')['n'] == 1
    assert db.one('SELECT enabled FROM monitors')['enabled'] == 0
    assert db.one('SELECT paused FROM accounts')['paused'] == 1
    assert db.one('SELECT COUNT(*) n FROM actions')['n'] == 0
