"""Run the actual browser duration helpers with a controlled clock."""
import json
import re
import subprocess
from pathlib import Path


def test_completed_duration_stays_fixed_while_running_duration_advances():
    source = (Path(__file__).resolve().parents[1] / 'app/static/js/app.js').read_text()
    helpers = '\n'.join(re.findall(
        r'  function (?:parseTaskTime|elapsed|taskDuration)\([^)]*\) \{.*?\n  \}', source, re.S))
    script = helpers + '''
const task = {status:'succeeded', created_at:'2026-09-09T05:30:00', updated_at:'2026-09-09T05:32:15'};
Date.now = () => Date.parse('2026-09-13T05:30:00Z');
const before = taskDuration(task);
Date.now = () => Date.parse('2026-09-14T05:30:00Z');
const after = taskDuration(task);
task.status = 'running';
Date.now = () => Date.parse('2026-09-09T05:31:00Z');
const running = taskDuration(task);
Date.now = () => Date.parse('2026-09-09T05:31:10Z');
const runningLater = taskDuration(task);
task.status = 'succeeded';
task.created_at = '2026-09-09T13:30:00+08:00';
task.updated_at = '2026-09-09T05:32:15Z';
const offset = taskDuration(task);
task.updated_at = null;
const missing = taskDuration(task);
console.log(JSON.stringify([before,after,running,runningLater,offset,missing]));
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ['2m 15s', '2m 15s', '1m 0s', '1m 10s', '2m 15s', '—']
