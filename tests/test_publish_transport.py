"""Exercise the bridge with synthetic upstream modules, no network."""
import sys
from types import ModuleType, SimpleNamespace

import pytest

from xianyu_workbench.bridge import dispatch


@pytest.fixture
def upstream(monkeypatch):
    calls = []
    class HTTP:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            assert kwargs.get('allow_redirects') is False
            return SimpleNamespace(json=lambda: {'object': {'url': 'https://img.alicdn.com/test.png', 'pix': '40x30'}},
                                   raise_for_status=lambda: None)
    session = SimpleNamespace(unb='12345', http=HTTP())
    modules = {name: ModuleType(name) for name in ['goofish_cli', 'goofish_cli.core', 'goofish_cli.core.mtop', 'goofish_cli.core.session']}
    modules['goofish_cli.core'].Session = SimpleNamespace(load=lambda: session)
    modules['goofish_cli.core.session'].USER_AGENT = 'fixture'
    def call(session, **kwargs):
        calls.append(kwargs)
        assert kwargs['_auto_refresh'] is False
        return {'ret': ['SUCCESS::fixture'], 'data': {'itemId': '777'}}
    modules['goofish_cli.core.mtop'].call = call
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv('XY_PUBLISH_ENABLED', 'true')
    monkeypatch.setenv('XY_OPERATION_UID', '12345')
    return calls


def test_bridge_explicit_submit_never_imports_implicit_publish(upstream):
    result = dispatch('publish.submit', {'uniqueCode': 'fixture', 'itemPriceDTO': {'priceInCent': '1230'}})
    assert result['data']['itemId'] == '777'
    assert upstream[0]['api'] == 'mtop.idle.pc.idleitem.publish'
    assert upstream[0]['data']['itemPriceDTO']['priceInCent'] == '1230'


def test_bridge_single_upload(upstream, tmp_path):
    path = tmp_path / 'test.png'
    path.write_bytes(b'fictional-image')
    import hashlib
    result = dispatch('publish.upload', {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    assert result['width'] == 40 and result['height'] == 30
    assert len(upstream) == 1


def test_upload_rechecks_frozen_hash_before_external_write(upstream, tmp_path):
    path = tmp_path / 'changed.png'
    path.write_bytes(b'changed')
    with pytest.raises(ValueError):
        dispatch('publish.upload', {'path': str(path), 'sha256': '0' * 64})
    assert not upstream


def test_bridge_readback_fixed_api(upstream):
    dispatch('publish.readback', {'itemId': '777'})
    assert upstream[0]['api'] == 'mtop.taobao.idle.pc.detail'
    assert upstream[0]['data'] == {'itemId': '777'}


@pytest.mark.parametrize('change', ['disabled', 'uid'])
def test_bridge_requires_enabled_same_identity(upstream, monkeypatch, change):
    monkeypatch.setenv('XY_PUBLISH_ENABLED' if change == 'disabled' else 'XY_OPERATION_UID', 'false' if change == 'disabled' else '999')
    with pytest.raises(ValueError):
        dispatch('publish.submit', {})
    assert not upstream
