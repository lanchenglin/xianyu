import os
import subprocess
import sys
import zipfile

import pytest
from cryptography.fernet import Fernet

from xianyu_workbench.backup import create_backup, validate_archive
from xianyu_workbench.db import DB
from xianyu_workbench.security import Vault


@pytest.mark.parametrize('encoding', ['cp1252', 'ascii', 'utf-8'])
@pytest.mark.parametrize('operation', ['backup', 'restore'])
def test_private_cli_success_with_redirected_output(tmp_path, encoding, operation):
    root = tmp_path / '虚构数据'
    key = Fernet.generate_key().decode()
    vault = Vault(key)
    db = DB(root, vault)
    db.execute("INSERT INTO accounts(id,label,mode,created) VALUES('a','fake','demo',1)")
    archive = tmp_path / 'backup.zip'
    if operation == 'restore':
        create_backup(root, archive, vault)
        db.execute("UPDATE accounts SET label='damaged'")
    args = ['--output', str(archive)] if operation == 'backup' else ['--archive', str(archive), '--offline']
    result = subprocess.run([sys.executable, '-m', 'xianyu_workbench.cli', operation,
                             '--data-dir', str(root), *args], cwd=tmp_path,
                            env={**os.environ, 'XY_VAULT_KEY': key, 'PYTHONIOENCODING': encoding},
                            capture_output=True)
    # Validate actual data even if the CLI falsely reports failure after a successful write.
    stage = tmp_path / 'validated'
    stage.mkdir()
    with zipfile.ZipFile(archive) as package:
        validate_archive(package, stage, vault)
    assert db.one('SELECT label FROM accounts')['label'] == 'fake'
    if operation == 'restore':
        assert db.one('SELECT paused FROM accounts')['paused'] == 1
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode(encoding).strip()
    assert result.stderr == b''
    assert key.encode() not in result.stdout + result.stderr


@pytest.mark.parametrize('encoding', ['cp1252', 'ascii', 'utf-8'])
def test_private_cli_failure_stays_sanitized_with_redirected_output(tmp_path, encoding):
    key = Fernet.generate_key().decode()
    root = tmp_path / 'data'
    vault = Vault(key)
    db = DB(root, vault)
    archive = tmp_path / 'backup.zip'
    create_backup(root, archive, vault)
    before = db.path.read_bytes()
    wrong_key = Fernet.generate_key().decode()
    result = subprocess.run([sys.executable, '-m', 'xianyu_workbench.cli', 'restore',
                             '--data-dir', str(root), '--archive', str(archive), '--offline'],
                            cwd=tmp_path, capture_output=True,
                            env={**os.environ, 'XY_VAULT_KEY': wrong_key, 'PYTHONIOENCODING': encoding})
    assert result.returncode == 1
    assert result.stdout == b''
    assert result.stderr.decode(encoding).strip()
    for secret in (key.encode(), wrong_key.encode(), b'Traceback', b'InvalidToken'):
        assert secret not in result.stdout + result.stderr
    assert db.path.read_bytes() == before
