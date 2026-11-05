"""[MINI-COMMENT: ASSISTANT.SEARCH.PROVIDERS.TEST] [EN rev.1]
[Role] Tests fixed provider routing, public GitHub transport and optional isolated Google settings.
[Dependencies] Linux stdlib mocks and actual candidate child code; no network, accounts or production data.
[Impact] Checks SSRF/redirect/secret/rate-limit boundaries and genuine provider labels rather than implementation-only snapshots.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch,PropertyMock,MagicMock
import urllib.error

from utils.ai_assistant.web_search import CHILD,SearchService,WebSearchError,search_mode,public_searches


class SearchProviderTests(unittest.TestCase):
    """[Role] Verifies execution boundaries with deterministic public search envelopes."""
    def child(self,provider='github',scope='repositories',body=None,error=None):
        """[Role] Executes real fixed child code with only its HTTP/resource interfaces made inert.
        [Dependencies] Candidate CHILD and stdlib monkeypatches. [Impact] No process limits, network, logs or credentials leave this test.
        """
        request={'query':'Flask','max_results':2,'provider':provider,'scope':scope}
        if provider=='google':request['google']={'key':'synthetic-test-key','cx':'synthetic-engine'}
        opener=MagicMock()
        opener.open.side_effect=error
        opener.open.return_value=io.BytesIO(json.dumps(body or {'items':[]}).encode())
        output=io.StringIO();namespace={}
        with patch('resource.setrlimit'),patch('logging.disable'),patch('sys.stdin',SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode()))),contextlib.redirect_stdout(output),patch('urllib.request.build_opener',return_value=opener):
            try:exec(compile(CHILD,'<candidate-search-child>','exec'),namespace)
            except SystemExit as ended:self.assertEqual(ended.code,0)
        return json.loads(output.getvalue()),opener,namespace

    def test_github_is_public_fixed_origin_and_partial_results_stay_truthful(self):
        """[Role] Exercises actual GitHub parsing and request construction without a live API.
        [Dependencies] Real fixed child and inert HTTP response. [Impact] Private flags and arbitrary redirects never become public evidence.
        """
        result,opener,ns=self.child(scope='issues',body={'incomplete_results':True,'items':[{'title':'Bug','html_url':'https://github.com/example/repo/issues/1','body':'Public issue'},{'title':'Private','html_url':'https://github.com/example/secret','private':True}]})
        self.assertTrue(result['partial']);self.assertEqual(len(result['results']),1)
        request=opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith('https://api.github.com/search/issues?'));self.assertIn('is%3Apublic',request.full_url);self.assertIn('is%3Aissue',request.full_url)
        self.assertNotIn('Authorization',request.headers)
        with self.assertRaises(ValueError):ns['NoRedirect']().redirect_request(None,None,None,None,None,None)

    def test_github_rate_limit_is_not_a_success_or_generic_empty_result(self):
        """[Role] Preserves a provider rate-limit cause through both child and parent layers.
        [Dependencies] Real HTTP error handling. [Impact] No busy retry or invented sources are emitted.
        """
        error=urllib.error.HTTPError('https://api.github.com/search/repositories',403,'limited',{'X-RateLimit-Remaining':'0'},None)
        result,_,_=self.child(error=error);self.assertEqual(result,{'error':'WEB_SEARCH_RATE_LIMIT'})
        with patch.object(SearchService,'available',new_callable=PropertyMock,return_value=True),patch('utils.ai_assistant.web_search.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(result).encode())):
            with self.assertRaises(WebSearchError) as caught:SearchService('/synthetic').search('Flask',provider='github')
        self.assertEqual(caught.exception.code,'WEB_SEARCH_RATE_LIMIT')

    def test_provider_scope_length_and_unconfigured_google_fail_before_process(self):
        """[Role] Rejects model-selected endpoints/scopes and unavailable Google before any child starts.
        [Dependencies] Actual parent validator and no Google configuration. [Impact] Google CAPTCHA is never retried or bypassed by tool calls.
        """
        with patch.object(SearchService,'available',new_callable=PropertyMock,return_value=True),patch('utils.ai_assistant.web_search.subprocess.run') as run:
            service=SearchService('/synthetic')
            for kwargs in [{'provider':'https://evil.example'},{'provider':'github','scope':'code'},{'provider':'yahoo','scope':'issues'},{'provider':'github','scope':'repositories','query':'a '*130}]:
                with self.assertRaises(WebSearchError):service.search(**{'query':'Flask',**kwargs})
            with self.assertRaises(WebSearchError) as caught:service.search('Flask',provider='google')
            self.assertEqual(caught.exception.code,'WEB_SEARCH_PROVIDER_UNAVAILABLE');run.assert_not_called()
            google=next(p for p in service.providers if p['id']=='google');self.assertFalse(google['available']);self.assertTrue(google['reason'])

    def test_google_credentials_are_dedicated_private_and_not_exported_as_status(self):
        """[Role] Validates an optional future authorized API route without reusing Hermes/Git credentials.
        [Dependencies] Owned Linux temporary file and inert subprocess. [Impact] Unsafe mode/symlink fails; only the Google child receives its own key.
        """
        with tempfile.TemporaryDirectory() as tmp:
            service=SearchService(tmp);service.google_config.parent.mkdir(parents=True)
            secret={'key':'synthetic-test-key','cx':'synthetic-engine'};service.google_config.write_text(json.dumps(secret));service.google_config.chmod(0o600)
            self.assertEqual(service.google_settings(),secret)
            with patch.object(SearchService,'available',new_callable=PropertyMock,return_value=True),patch('utils.ai_assistant.web_search.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'{"results":[]}')) as run:
                self.assertNotIn(secret['key'],json.dumps(service.providers))
                result=service.search('Flask',provider='google');self.assertEqual(result['engine'],'Google')
                self.assertEqual(json.loads(run.call_args.kwargs['input'])['google'],secret)
                self.assertNotIn(secret['key'],json.dumps(run.call_args.kwargs['env']))
                service.search('Flask',provider='github');self.assertNotIn('google',json.loads(run.call_args.kwargs['input']))
            service.google_config.chmod(0o644);self.assertIsNone(service.google_settings())
            service.google_config.unlink();service.google_config.symlink_to('/etc/passwd');self.assertIsNone(service.google_settings())

    def test_google_fixed_api_parser_does_not_copy_keys_into_results(self):
        """[Role] Verifies the authorized adapter's fixed Google API boundary with synthetic credentials.
        [Dependencies] Actual child transport and inert JSON. [Impact] Neither cookies nor arbitrary provider origins are accepted.
        """
        result,opener,_=self.child(provider='google',scope='web',body={'items':[{'title':'Docs','link':'https://docs.example.org','snippet':'Public'}]})
        self.assertEqual(len(result['results']),1);self.assertNotIn('synthetic-test-key',json.dumps(result))
        self.assertTrue(opener.open.call_args.args[0].full_url.startswith('https://www.googleapis.com/customsearch/v1?'))

    def test_source_projection_and_legacy_mode_do_not_relabel_providers(self):
        """[Role] Preserves original source identity and immutable legacy required/off snapshots.
        [Dependencies] Real evidence projection and route-mode helper. [Impact] Unknown engines never masquerade as Yahoo or Google.
        """
        base={'kind':'web_search','version':1,'engine':'GitHub','scope':'issues','status':'partial','query':'Flask','results':[]}
        def project(value):
            """[Role] Supplies a genuine correlated tool envelope without unrelated content."""
            return public_searches([{'role':'assistant','tool_calls':[{'id':'a','function':{'name':'web_search'}}]},{'role':'tool','tool_call_id':'a','content':json.dumps(value)}])
        self.assertEqual(project(base)[0]['engine'],'GitHub');self.assertEqual(project(base)[0]['status'],'partial')
        self.assertEqual(project({**base,'engine':'fake-google'}),[])
        self.assertEqual(search_mode({'web_search_allowed':True}),'required');self.assertEqual(search_mode({}),'off')
        self.assertEqual(search_mode({'web_search_allowed':True,'web_search_mode':'auto'}),'auto')
