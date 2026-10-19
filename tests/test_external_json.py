"""Raw external HTTP fixtures, never real services or credentials."""
import hashlib
import io
import json
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest
import requests

from tests.test_workbench import workbench as workbench

BAD = ['NaN', 'Infinity', '-Infinity', '1e999', 'duplicate', 'oversize', 'structure']


def raw_response(kind, bad):
    value = {'upload': {'object': {'url': 'https://img.alicdn.com/test.png', 'pix': '40x30'}},
             'llm': {'choices': [{'message': {'content': '{"text":"fixture"}'}}]},
             'mcp': {'items': []}, 'cli': {'enabled': False}}[kind]
    text = json.dumps(value)
    if bad == 'structure':
        return b'"DO_NOT_ECHO"'
    if bad == 'duplicate':
        text = '{"private":"DO_NOT_ECHO","private":0,' + text[1:]
    elif bad == 'oversize':
        text = text[:-1] + ',"padding":"' + 'x' * 5_000_000 + '"}'
    elif bad:
        text = text[:-1] + ',"private":' + bad + '}'
    return text.encode()


@pytest.mark.parametrize('bad', [None, *BAD])
def test_upload_raw_json_boundary(monkeypatch, tmp_path, bad):
    from xianyu_workbench.bridge import dispatch
    calls = []
    def post(*a, **kw):
        calls.append(kw)
        response = requests.Response()
        response.status_code = 200
        response.raw = io.BytesIO(raw_response('upload', bad))
        return response
    modules = {n: ModuleType(n) for n in ['goofish_cli.core', 'goofish_cli.core.mtop', 'goofish_cli.core.session']}
    modules['goofish_cli.core'].Session = SimpleNamespace(load=lambda: SimpleNamespace(unb='12345', http=SimpleNamespace(post=post)))
    modules['goofish_cli.core.mtop'].call = lambda *a, **k: pytest.fail('no publish after upload failure')
    modules['goofish_cli.core.session'].USER_AGENT = 'fixture'
    for n, m in modules.items():
        monkeypatch.setitem(sys.modules, n, m)
    monkeypatch.setenv('XY_PUBLISH_ENABLED', 'true')
    monkeypatch.setenv('XY_OPERATION_UID', '12345')
    path = tmp_path / 'image'
    path.write_bytes(b'fictional')
    payload = {'path': str(path), 'sha256': hashlib.sha256(b'fictional').hexdigest()}
    if bad:
        with pytest.raises(ValueError):
            dispatch('publish.upload', payload)
    else:
        assert dispatch('publish.upload', payload)['width'] == 40
    assert len(calls) == 1
    assert calls[0].get('stream') is True


@pytest.mark.parametrize('bad', BAD)
def test_mcp_identity_raw_json_blocks_business_request(monkeypatch, bad):
    from xianyu_workbench.mcp_server import api
    real_client = httpx.Client
    calls = []
    def handler(request):
        calls.append(request.url.path)
        raw = raw_response('mcp', bad).replace(b'"items": []', b'"role":"agent"')
        return httpx.Response(200, content=raw)
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler)))
    monkeypatch.setenv('XY_AGENT_TOKEN', 'f' * 40)
    monkeypatch.setenv('XY_API_URL', 'https://fictional.invalid')
    with pytest.raises(ValueError):
        api('POST', '/api/actions', {})
    assert calls == ['/api/me']


def test_bounded_reader_stops_before_remaining_chunks():
    from xianyu_workbench.security import bounded_json
    def chunks():
        yield b' ' * 9
        yield b' ' * 9
        pytest.fail('must stop reading at limit')
    with pytest.raises(ValueError):
        bounded_json(chunks(), 10)


@pytest.mark.parametrize('kind', ['llm', 'mcp', 'cli'])
@pytest.mark.parametrize('bad', [None, *BAD])
def test_httpx_raw_json_boundaries(workbench, monkeypatch, capsys, kind, bad):
    client, service = workbench
    real_client = httpx.Client
    calls = []
    def handler(request):
        calls.append(request.url.path)
        raw = b'{"role":"agent"}' if request.url.path == '/api/me' else raw_response(kind, bad)
        return httpx.Response(200, content=raw)
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real_client(**kw, transport=httpx.MockTransport(handler)))
    if kind == 'llm':
        from xianyu_workbench.models import AssistIn
        from xianyu_workbench.provider import Problem
        service.db.execute('INSERT INTO settings VALUES(?,?)', ('llm', service.vault.seal({
            'base_url': 'https://fictional.invalid', 'api_key': 'fictional', 'model': 'fixture'})))
        if bad:
            with pytest.raises(Problem, match='模型调用失败'):
                service.assist(AssistIn(purpose='reply', facts='fictional'))
        else:
            assert service.assist(AssistIn(purpose='reply', facts='fictional'))['draft']['text'] == 'fixture'
    elif kind == 'mcp':
        from xianyu_workbench.mcp_server import api
        monkeypatch.setenv('XY_AGENT_TOKEN', 'f' * 40)
        monkeypatch.setenv('XY_API_URL', 'https://fictional.invalid')
        if bad:
            with pytest.raises(ValueError) as exc:
                api('GET', '/api/items')
            assert 'DO_NOT_ECHO' not in str(exc.value)
        else:
            assert api('GET', '/api/items') == {'items': []}
    else:
        from xianyu_workbench.cli import main
        monkeypatch.setenv('XY_ADMIN_TOKEN', 'f' * 40)
        monkeypatch.setattr(sys, 'argv', ['cli', 'daily-publish', 'status', '--url', 'https://fictional.invalid', '--account-id', 'fixture'])
        if bad:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert 'DO_NOT_ECHO' not in capsys.readouterr().err
        else:
            main()
            assert json.loads(capsys.readouterr().out) == {'enabled': False}
    assert len(calls) == (2 if kind == 'mcp' else 1)
