import sys
from types import ModuleType, SimpleNamespace

import pytest

from tests.test_workbench import workbench as workbench
from xianyu_workbench.bridge import dispatch_edit
from xianyu_workbench.provider import Problem


def test_bridge_disabled_before_import(monkeypatch):
    monkeypatch.delenv('XY_EDIT_ENABLED', raising=False)
    with pytest.raises(ValueError, match='edit_disabled'):
        dispatch_edit('edit.submit', {})


@pytest.mark.parametrize('operation,api', [('edit.read', 'mtop.idle.pc.idleitem.editDetail'),
                                         ('edit.submit', 'mtop.idle.pc.idleitem.edit')])
def test_bridge_fixed_endpoint_single_attempt(monkeypatch, operation, api):
    monkeypatch.setenv('XY_EDIT_ENABLED', 'true')
    monkeypatch.setenv('XY_OPERATION_UID', '12345')
    posts = []
    session = SimpleNamespace(unb='12345', http=SimpleNamespace(post=lambda *a, **kw: posts.append(kw)))
    core = ModuleType('goofish_cli.core')
    core.Session = SimpleNamespace(load=lambda: session)
    mtop = ModuleType('goofish_cli.core.mtop')
    calls = []
    def call(s, **kwargs):
        calls.append(kwargs)
        s.http.post('https://fictional.invalid', allow_redirects=True)
        return {'ret': ['SUCCESS::fictional']}
    mtop.call = call
    monkeypatch.setitem(sys.modules, 'goofish_cli.core', core)
    monkeypatch.setitem(sys.modules, 'goofish_cli.core.mtop', mtop)
    payload = {'item_id': '777', 'api_version': '3.2'}
    if operation == 'edit.submit':
        payload['template'] = {'itemId': '777', 'fixture': 'exact'}
    dispatch_edit(operation, payload)
    assert calls == [{'api': api, 'data': payload.get('template', {'itemId': '777'}),
                      'version': '3.2', '_auto_refresh': False}]
    assert posts == [{'allow_redirects': False}]


def test_provider_rejects_unselected_transport(workbench):
    _, service = workbench
    with pytest.raises(Problem, match='指定队列'):
        service.provider._live({'id': 'not-selected'}, 'edit.submit', {}, write=True)
