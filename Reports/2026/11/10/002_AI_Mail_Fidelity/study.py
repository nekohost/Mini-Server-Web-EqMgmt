"""Grade real sequential Qwen replies via the isolated assistant admission, worker and storage paths."""
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

from evaluate_live import MODEL, Measurements, evaluate_one, live_environment


def sha(s):
    return hashlib.sha256(s.encode('utf8')).hexdigest()


def main():
    os.umask(0o077)
    folder = Path(sys.argv[1]).resolve()
    arm = sys.argv[2]
    assert arm in ('baseline', 'candidate')
    root = folder / arm
    rows = json.loads((folder / 'cases.json').read_bytes())
    assert all(set(r) == {'id', 'direction', 'original', 'split'} for r in rows)
    os.environ['EQ_TEST_PROJECT_ROOT'] = str(root)
    sys.path[:0] = [str(root / 'tests'), str(root)]
    from test_equipment_ai import AssistantTests
    from utils.ai_assistant import worker
    from utils.ai_assistant import translation
    settings = live_environment()
    key = settings['USER_AI_STRATA_KEY']

    class Checked(Measurements):
        def append(self, suffix, value):
            if suffix == 'wire':
                payload = value['payload']
                assert payload['model'] == MODEL and not payload.get('tools') and payload['stream']
                msgs = payload['messages']
                assert len(msgs) == 2 and [m['role'] for m in msgs] == ['system','user']
                assert msgs[1]['content'] == self.case['original']
                assert payload['reasoning_effort'] == {'en-ko':'xhigh','ko-en':'low'}[self.case['direction']]
                value = {'id': self.case['id'], 'model': MODEL, 'effort': payload['reasoning_effort'],
                         'source_sha256': sha(msgs[1]['content']), 'instruction_sha256': sha(msgs[0]['content']),
                         'tools': 0, 'stream': True}
            super().append(suffix, value)

    with (folder / 'exclusive.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        out = folder / (arm + '-results.jsonl')
        history = [json.loads(v) for v in out.read_text().splitlines()] if out.exists() else []
        done = {v['case'] for v in history}
        events = folder / (arm + '-events.jsonl')
        submitted = {v['case'] for v in map(json.loads, events.read_text().splitlines()) if v.get('event') == 'admit'} if events.exists() else set()
        if len(done) != len(history) or submitted != done:
            raise RuntimeError('Unresolved prior admission: inspect before resubmitting')
        meter = Checked(folder, arm, key)
        meter.sample()
        meter.thread.start()
        try:
            for row in rows:
                if row['id'] in done:
                    continue
                meter.case = row
                meter.wait_idle()
                fixture = AssistantTests(methodName='runTest')
                fixture.setUp()
                try:
                    result = evaluate_one(fixture, worker, meter, row, key)
                    meter.append('results', result)
                finally:
                    fixture.tearDown()
                    fixture.doCleanups()
                print(row['id'], result['state'], result['elapsed'], flush=True)
                if result['state'] not in ('done', 'failed'):
                    raise RuntimeError('Ambiguous completion; inspect first')
        finally:
            meter.stop.set()
            meter.thread.join(8)
            meter.sample()


if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    main()
