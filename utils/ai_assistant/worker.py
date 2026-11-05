"""[MINI-COMMENT: ASSISTANT.WORKER]
[EN rev.8]
[Role] Dispatches only equipment queue steps using immutable routes and DB-authoritative group slots.
[Dependencies] requests, private loopback worker API and server-only environment credentials.
[Impact] Delivers small SSE batches within 150ms when frames arrive, preserves monotonic offsets and drains only its own cancelled response; group occupancy remains server-controlled.
"""
import argparse
import json
import logging
import os
import signal
import threading
import time
from urllib.parse import urlsplit
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import nullcontext

import requests

from .policy import MAX_CONTENT, MAX_REASONING
from .providers import PROTOCOL
from .transport import EndpointPolicy, model_request

LOG=logging.getLogger('equipment_assistant_worker')


class DispatchCancelled(Exception):
    """[Role] Ends a known not-dispatched own request. [Dependencies] Server admission. [Impact] No upstream request."""


def sse(response):
    """[Role] Parses bounded SSE frames, including an exact terminal marker at EOF without a final blank separator.
    [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
    [Impact] Only an explicit [DONE] can end a stream; a stop frame or EOF alone still fails closed.
    """
    response.encoding='utf-8'
    data=[]
    size=0
    # Avoid waiting for an arbitrary byte buffer after a complete upstream SSE line.
    for line in response.iter_lines(chunk_size=1,decode_unicode=True):
        if len(line)>262144:
            raise ValueError('oversized SSE line')
        if not line:
            if data:
                raw='\n'.join(data)
                if raw=='[DONE]':
                    yield '[DONE]'
                    return
                yield json.loads(raw)
            else:
                yield None
            data,size=[],0
        elif line.startswith('data:'):
            value=line[5:].lstrip(' ')
            size+=len(value)
            if size>262144:
                raise ValueError('oversized SSE frame')
            data.append(value)
        elif line.startswith(':'):
            yield None
    if data==['[DONE]']:
        yield '[DONE]'
        return
    raise ValueError('incomplete SSE response')


class Worker:
    """[Role] Uses server-selected tools/context; upstream keys are never included in model messages."""
    def __init__(self, equipment_url, token, strata_url, strata_key, model, read_timeout=1800):
        """[Role] Validates fixed origins and installs independent private credentials.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        local=urlsplit(equipment_url)
        upstream=urlsplit(strata_url)
        if local.scheme not in ('http','https') or local.hostname not in ('127.0.0.1','localhost','::1') or local.path not in ('','/') or local.username or local.query or local.fragment:
            raise ValueError('worker API must be a local configured origin')
        if upstream.scheme not in ('http','https') or not upstream.hostname or upstream.path not in ('','/') or upstream.username or upstream.query or upstream.fragment:
            raise ValueError('invalid configured Strata origin')
        if len(token)<32 or not model or not 60<=read_timeout<=7200:
            raise ValueError('missing credentials/model or invalid timeout')
        self.base,self.token,self.strata,self.key,self.model=equipment_url.rstrip('/'),token,strata_url.rstrip('/'),strata_key,model
        self.timeout=read_timeout
        self.worker=uuid.uuid4().hex
        self.stop=threading.Event()
        self.policy=EndpointPolicy(json.loads(os.environ.get('USER_AI_ALLOWED_ENDPOINTS','null')) or [strata_url])
        self.parallelism=int(os.environ.get('USER_AI_DISPATCHERS','8'))
        if not 1<=self.parallelism<=32:
            raise ValueError('invalid bounded dispatcher count')

    def post(self, path, data):
        """[Role] Calls only fixed internal assistant endpoints without redirects, proxies or cookies.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        with requests.Session() as client:
            client.trust_env=False
            r=client.post(self.base+path,json=data,headers={'Authorization':'Bearer '+self.token},timeout=(3,15),allow_redirects=False)
            r.raise_for_status()
            value=r.json()
            if value.get('success') is not True:
                raise ValueError('equipment API rejected request')
            return value

    def heartbeat(self, job, complete, cancelled):
        """[Role] Keeps an own lease observable during long prefill without extending browser sessions.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        while not complete.wait(5):
            try:
                result=self.post('/internal/ai/jobs/'+job['id']+'/event',{'lease':job['lease']})
                if result.get('cancel'):
                    cancelled.set()
            except Exception as error:
                LOG.warning('heartbeat job=%s type=%s',job['id'],type(error).__name__)

    def run_job(self, job):
        """[MINI-COMMENT: ASSISTANT.WORKER.STEP]
        [EN rev.6]
        [Role] Verifies dispatch admission, applies only the server's fixed required decision/search tool and submits completed live calls.
        [Dependencies] Strata Chat Completions SSE; an HTTP EOF without DONE is not a completed request.
        [Impact] Flushes display batches at 150ms or 4096 characters without changing final content, stop reasons or uncertain-request locks.
        """
        complete,cancelled=threading.Event(),threading.Event()
        pulse=threading.Thread(target=self.heartbeat,args=(job,complete,cancelled),daemon=True)
        pulse.start()
        reasoning,content,total_content,total_reasoning=[],[],[],[]
        calls={}
        last_flush=time.monotonic()
        outcome='recovery_required'
        dispatched=False
        finish_reason=None
        done=False
        error_code='STREAM_INCOMPLETE'
        reasoning_offset=content_offset=0
        total_r=total_c=0

        def flush():
            """[Role] Persists bounded display chunks; errors do not kill another service's model request.
            [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
            [Impact] Preserves the module's owner/validation/transaction boundary described above.
            """
            nonlocal last_flush,reasoning_offset,content_offset
            if cancelled.is_set() or (not reasoning and not content):
                return
            payload={'lease':job['lease'],'reasoning':''.join(reasoning),'content':''.join(content),
                     'reasoning_offset':reasoning_offset,'content_offset':content_offset}
            result=self.post('/internal/ai/jobs/'+job['id']+'/event',payload)
            if result.get('cancel'):
                cancelled.set()
            if result.get('accepted',not job.get('protocol')):
                acknowledged_r=result.get('reasoning_offset',reasoning_offset+len(payload['reasoning']))
                acknowledged_c=result.get('content_offset',content_offset+len(payload['content']))
                if type(acknowledged_r) is not int or type(acknowledged_c) is not int or acknowledged_r!=reasoning_offset+len(payload['reasoning']) or acknowledged_c!=content_offset+len(payload['content']):
                    cancelled.set()
                    raise ValueError('invalid server stream acknowledgement')
                reasoning_offset,content_offset=acknowledged_r,acknowledged_c
            else:
                cancelled.set()
            reasoning.clear()
            content.clear()
            last_flush=time.monotonic()

        try:
            admission=self.post('/internal/ai/jobs/'+job['id']+'/event', {'lease':job['lease']})
            if admission.get('cancel') or admission.get('accepted') is False:
                cancelled.set()
                outcome='cancelled'
                error_code='USER_CANCELLED'
                raise DispatchCancelled()
            if job.get('protocol') and admission.get('accepted') is not True:
                raise ValueError('missing server dispatch admission')
            route=job.get('route')
            payload={'model':route['model'] if route else self.model,'messages':job['messages'],'stream':True,
                     'max_tokens':job.get('max_tokens',4096),
                     'temperature':0.6,'top_p':0.95}
            if job['tools']:
                payload['tools']=job['tools']
            required_tool=job.get('required_tool')
            if required_tool is not None:
                if required_tool!='plan_web_search' or job.get('web_search_required') is True or not any(tool.get('function',{}).get('name')==required_tool for tool in job['tools']):
                    raise ValueError('invalid required planning tool')
                payload['tool_choice']={'type':'function','function':{'name':required_tool}}
            elif job.get('web_search_required') is True:
                if not any(tool.get('function',{}).get('name')=='web_search' for tool in job['tools']):
                    raise ValueError('required search tool is unavailable')
                payload['tool_choice']={'type':'function','function':{'name':'web_search'}}
            if job.get('reasoning_effort') is not None:
                payload['reasoning_effort']=job['reasoning_effort']
            if not route or route['adapter']=='strata':
                payload['strata_mcp']=False
            # Compatibility branch is only for historical direct fixtures; v3 claim always supplies a route.
            with nullcontext(None) if route else requests.Session() as client:
                dispatched=True
                if route:
                    response_context=model_request(self.policy,route['base_url'],'/chat/completions',
                        self.key if route.get('legacy_worker_key') else route.get('api_key',''),payload,self.timeout)
                else:
                    client.trust_env=False
                    response_context=client.post(self.strata+'/v1/chat/completions',json=payload,
                        headers={'Authorization':'Bearer '+self.key},timeout=(5,self.timeout),stream=True,allow_redirects=False)
                with response_context as response:
                    if response.status_code in (400,401,403,404,413,429,503):
                        outcome='failed'  # Definitively rejected, without running a model step.
                        error_code='UPSTREAM_REJECTED'
                        raise ValueError('upstream rejected request')
                    response.raise_for_status()
                    if 'text/event-stream' not in response.headers.get('Content-Type',''):
                        raise ValueError('upstream did not return SSE')
                    for item in sse(response):
                        if item=='[DONE]':
                            done=True
                            break
                        if cancelled.is_set():
                            reasoning.clear()
                            content.clear()
                            total_reasoning.clear()
                            total_content.clear()
                            calls.clear()
                            continue
                        if item is not None:
                            if not isinstance(item,dict) or item.get('error'):
                                raise ValueError('invalid model frame')
                            choices=item.get('choices',[])
                            if choices:
                                choice=choices[0]
                                finish_reason=choice.get('finish_reason') or finish_reason
                                delta=choice.get('delta',{})
                                reason=delta.get('reasoning_content',delta.get('reasoning','')) or ''
                                answer=delta.get('content','') or ''
                                if not isinstance(reason,str) or not isinstance(answer,str):
                                    raise ValueError('invalid model text')
                                reasoning.append(reason)
                                total_reasoning.append(reason)
                                content.append(answer)
                                total_content.append(answer)
                                total_r+=len(reason)
                                total_c+=len(answer)
                                if total_r>MAX_REASONING or total_c>MAX_CONTENT:
                                    error_code='LENGTH_LIMIT'
                                    raise ValueError('model text limit exceeded')
                                for call in delta.get('tool_calls',[]) or []:
                                    index=call.get('index')
                                    if type(index) is not int or not 0<=index<4:
                                        raise ValueError('invalid tool index')
                                    target=calls.setdefault(index,{'id':'','name':'','arguments':''})
                                    target['id']+=call.get('id','') or ''
                                    function=call.get('function',{})
                                    target['name']+=function.get('name','') or ''
                                    target['arguments']+=function.get('arguments','') or ''
                                    if len(target['arguments'])>16384 or len(target['id'])>100 or len(target['name'])>100:
                                        raise ValueError('oversized tool call')
                        # Bound display latency without flooding the app with one write per token.
                        elapsed = time.monotonic()-last_flush
                        buffered = sum(map(len,reasoning))+sum(map(len,content))
                        if buffered and (elapsed>=0.15 or buffered>=4096):
                            flush()
                        # No global cancellation API is used. A cancelled job drains its own response.
                    if done:
                        outcome='complete' if finish_reason in ('stop','tool_calls') else 'failed'
                        error_code='LENGTH_LIMIT' if finish_reason=='length' else 'INVALID_RESPONSE'
                        if calls and finish_reason!='tool_calls':
                            outcome='failed'
                            error_code='INVALID_TOOL_CALL'
                    flush()
            if cancelled.is_set():
                outcome='cancelled' if done else 'recovery_required'
                error_code='USER_CANCELLED'
        except DispatchCancelled:
            pass
        except Exception as error:
            if not dispatched:
                outcome='failed'
                error_code='PROCESSING_FAILED'
            elif isinstance(error,requests.Timeout):
                error_code='CONNECTION_TIMEOUT'
            elif isinstance(error,requests.ConnectionError):
                error_code='CONNECTION_FAILED'
            LOG.warning('model step job=%s type=%s outcome=%s',job['id'],type(error).__name__,outcome)
        finally:
            complete.set()
            pulse.join(timeout=16)
        report={'lease':job['lease'],'outcome':outcome,'error_code':error_code,
                'content':'' if cancelled.is_set() else ''.join(total_content)[:MAX_CONTENT],
                'reasoning':'' if cancelled.is_set() else ''.join(total_reasoning)[:MAX_REASONING],
                'calls':[calls[k] for k in sorted(calls)] if outcome=='complete' else []}
        for attempt in range(3):
            try:
                self.post('/internal/ai/jobs/'+job['id']+'/finish',report)
                break
            except Exception as error:
                # Retry only delivery of this fixed report. Never repeat a model request/tool step.
                LOG.error('finish report job=%s type=%s attempt=%s',job['id'],type(error).__name__,attempt+1)
                if isinstance(error,requests.HTTPError) and error.response is not None and error.response.status_code<500 and error.response.status_code not in (404,409):
                    break
                if attempt<2:
                    self.stop.wait(attempt+1)

    def run(self):
        """[Role] Dispatches only app-local queued steps; signal handling stops after its current response.
        [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
        [Impact] Preserves the module's owner/validation/transaction boundary described above.
        """
        pending=set()
        with ThreadPoolExecutor(max_workers=self.parallelism,thread_name_prefix='equipment-ai') as pool:
            while not self.stop.is_set():
                finished={f for f in pending if f.done()}
                for future in finished:
                    try:
                        future.result()
                    except Exception as error:
                        LOG.error('dispatcher step type=%s',type(error).__name__)
                pending-=finished
                if len(pending)>=self.parallelism:
                    wait(pending,timeout=1,return_when=FIRST_COMPLETED)
                    continue
                try:
                    job=self.post('/internal/ai/claim',{'worker':self.worker,'protocol':PROTOCOL}).get('job')
                    if job:
                        if job.get('protocol')!=PROTOCOL:
                            raise ValueError('server/worker protocol mismatch')
                        pending.add(pool.submit(self.run_job,job))
                    else:
                        self.stop.wait(1)
                except Exception as error:
                    LOG.warning('queue unavailable type=%s',type(error).__name__)
                    self.stop.wait(3)


def main():
    """[Role] Starts the standalone Linux worker or explicitly acknowledges a finished own recovery job.
    [Dependencies] This module's fixed helpers and explicitly injected resources; no caller-selected service.
    [Impact] Preserves the module's owner/validation/transaction boundary described above.
    """
    parser=argparse.ArgumentParser()
    parser.add_argument('--acknowledge-finished',metavar='OWN_JOB_ID')
    args=parser.parse_args()
    worker=Worker(os.environ.get('USER_AI_INTERNAL_URL','http://127.0.0.1:5000'),
        os.environ.get('USER_AI_WORKER_TOKEN',''),os.environ.get('USER_AI_STRATA_URL','http://192.168.0.14:8080'),
        os.environ.get('USER_AI_STRATA_KEY',''),os.environ.get('USER_AI_MODEL','qwen3.8-flash-next-iq3_xxs'),
        int(os.environ.get('USER_AI_READ_TIMEOUT','1800')))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if args.acknowledge_finished:
        if len(args.acknowledge_finished)!=32 or any(c not in '0123456789abcdef' for c in args.acknowledge_finished):
            parser.error('job ID must be a 32-character hexadecimal own job ID')
        worker.post('/internal/ai/jobs/'+args.acknowledge_finished+'/acknowledge-finished',{'acknowledgement':'OWN_REQUEST_CONFIRMED_FINISHED'})
        return
    for signum in (signal.SIGTERM,signal.SIGINT):
        signal.signal(signum,lambda *_:worker.stop.set())
    worker.run()


if __name__=='__main__':
    main()
