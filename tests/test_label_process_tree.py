"""Real isolated process groups, descendants, pipes and deterministic readiness."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from xianyu_workbench.edit_labels import bounded_communicate


@pytest.mark.parametrize('mode', ['stdout', 'stderr', 'timeout', 'normal', 'decode'])
def test_bridge_descendants_are_not_left_running(tmp_path, mode):
    pidfile = tmp_path / 'descendant.pid'
    child = 'import time; time.sleep(60)'
    source = f'''import subprocess,sys,time
from pathlib import Path
p=subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
Path({str(pidfile)!r}).write_text(str(p.pid))
sys.stdin.read()
mode={mode!r}
if mode=='stdout': sys.stdout.write('x'*100000)
elif mode=='stderr': sys.stderr.write('x'*100000)
elif mode=='timeout': time.sleep(60)
elif mode=='decode': sys.stdout.buffer.write(b'\\xff')
else: print('ok')
'''
    p = subprocess.Popen([sys.executable, '-c', source], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        if mode == 'normal':
            assert bounded_communicate(p, '{}', 2) == 'ok\n'
        else:
            with pytest.raises((ValueError, subprocess.TimeoutExpired)):
                bounded_communicate(p, '{}', .5 if mode == 'timeout' else 2)
        pid = int(pidfile.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            stat = Path(f'/proc/{pid}/stat')
            if not stat.exists() or stat.read_text().split(') ')[1].startswith('Z'):
                break
            time.sleep(.01)
        else:
            pytest.fail('isolated bridge descendant is still active')
        assert p.poll() is not None
        assert p.stdin.closed and p.stdout.closed and p.stderr.closed
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=5)
