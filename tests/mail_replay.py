"""Drive recorded mail requests through the real worker with a synthetic transport."""
import json
from pathlib import Path
import time


def read_cases(split):
    if split not in ('regression', 'unused'):
        raise ValueError('unknown corpus')
    rows = json.loads((Path(__file__).resolve().parent / 'mail_inputs' / (split + '.json')).read_text(encoding='utf-8'))
    cases = {}
    for row in rows:
        if (set(row) != {'id', 'direction', 'source'} or row['direction'] not in ('en-ko', 'ko-en')
                or row['id'] in cases or not isinstance(row['source'], str) or not row['source'].strip()):
            raise ValueError('invalid public corpus')
        cases[row['id']] = row
    return cases


def submission(row):
    target = '한국어' if row['direction'] == 'en-ko' else '영어'
    return f'다음 이메일을 {target}로 번역해 주세요.\n\n' + row['source']


class EndPreview(BaseException):
    """Interrupt the fixture before consuming a reply or marking an attempt complete."""


def replay(fix, row, level, emit, read_reply, emit_only=False):
    start = time.monotonic()
    admission = fix.submit(submission(row), level=level)
    if admission.status_code != 202:
        emit('result', state='admission_rejected', http=admission.status_code,
             error=admission.get_json().get('message'), translation='', elapsed_s=time.monotonic()-start)
        return 'admission_rejected'
    receipt = admission.get_json()
    jid, cid = receipt['job_id'], receipt['conversation_id']
    emit('admitted', source=row['source'], submitted=submission(row), job=jid, conversation=cid)
    while True:
        job = fix.claim()
        if job is None:
            break
        if job['id'] != jid:
            raise RuntimeError('unexpected fixture admission')
        step_start = time.monotonic()
        step_info = {}

        def respond(payload):
            emit('request', step=job['steps'], method='POST', path='/v1/chat/completions', payload=payload)
            if emit_only:
                raise EndPreview()
            reply = read_reply()
            if not isinstance(reply, dict):
                raise ValueError('expected one JSON object per model step')
            if reply.get('transport_error') not in ('timeout', 'connection') and (
                    not isinstance(reply.get('lines'), list) or not all(isinstance(line, str) for line in reply['lines'])):
                raise ValueError('supply received SSE lines including blank separators')
            step_info['runtime_notice'] = reply.get('runtime_notice')
            step_info['status'] = reply.get('status', 200) if 'transport_error' not in reply else None
            return reply

        # Worker deliberately maps upstream errors to durable job outcomes. An
        # invalid replay envelope is a harness error, not an observed model failure.
        input_errors = []

        def checked_reply(payload):
            try:
                return respond(payload)
            except (ValueError, EOFError, StopIteration) as error:
                input_errors.append(error)
                raise

        prior_reports = len(fix.finish_reports)
        try:
            fix.drive(job, checked_reply)
        except EndPreview:
            return 'preview'
        if input_errors:
            raise ValueError('invalid or missing replay reply') from input_errors[0]
        if len(fix.finish_reports) != prior_reports + 1:
            raise RuntimeError('missing worker finish receipt')
        report, receipt = fix.finish_reports[-1]
        emit('step', step=job['steps'], termination=report['termination'], outcome=report['outcome'],
             worker_error_code=report['error_code'] if report['outcome'] != 'complete' else None,
             content=report['content'], calls=report['calls'], state=receipt['state'],
             elapsed_s=round(time.monotonic()-step_start, 3), **step_info)
        if receipt['state'] != 'queued':
            break
    view = fix.client.get('/api/ai/conversations/' + cid + '/messages').get_json()
    result = next(job for job in view['jobs'] if job['id'] == jid)
    output = next(msg['content'] for msg in view['messages'] if msg['job'] == jid and msg['role'] == 'assistant')
    emit('result', state=result['state'], error=result['error'], error_code=result['error_code'],
         stored_assistant=output, translation=output if result['state'] == 'done' else '',
         source_info=result['source'], blocked_tools=fix.blocked_tools, elapsed_s=round(time.monotonic()-start, 3))
    return result['state']
