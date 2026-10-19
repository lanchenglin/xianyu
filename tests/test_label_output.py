"""Recommendation subprocess output is bounded while reading, not after capture."""
import subprocess
import sys

import pytest


def test_recommend_http_stream_stops_before_complete_consumption():
    from xianyu_workbench.edit_labels import bounded_response
    class Response:
        closed = False
        chunks = 0
        def iter_content(self, chunk_size):
            assert chunk_size == 8192
            for _ in range(100):
                self.chunks += 1
                yield b'x' * 8192
        def close(self):
            self.closed = True
    response = Response()
    with pytest.raises(ValueError, match='response limit'):
        bounded_response(response)
    assert response.chunks == 8
    assert response.closed


def test_recommend_output_timeout_reaps_child():
    from xianyu_workbench.edit_labels import bounded_communicate
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with pytest.raises(subprocess.TimeoutExpired):
        bounded_communicate(p, '{}', .05)
    assert p.poll() is not None


def test_recommend_output_limit_stops_large_stdout():
    from xianyu_workbench.edit_labels import bounded_communicate
    p = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read(); sys.stdout.write("x"*200000)'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with pytest.raises(ValueError, match='output limit'):
        bounded_communicate(p, '{}', 5)
    assert p.poll() is not None


def test_recommend_output_normal_and_stderr_bound():
    from xianyu_workbench.edit_labels import bounded_communicate
    p = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read(); print("ok"); sys.stderr.write("x"*200000)'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with pytest.raises(ValueError, match='output limit'):
        bounded_communicate(p, '{}', 5)
    p = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read(); print("ok")'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert bounded_communicate(p, '{}', 5) == 'ok\n'
