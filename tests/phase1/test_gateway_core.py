#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / 'services' / 'xapi-v1-wrapper' / 'gateway_core.py'
spec = importlib.util.spec_from_file_location('gateway_core', CORE_PATH)
assert spec is not None and spec.loader is not None
core = importlib.util.module_from_spec(spec)
sys.modules['gateway_core'] = core
spec.loader.exec_module(core)


class GatewayCoreTests(unittest.TestCase):
    def test_request_id_accepts_safe_incoming(self):
        self.assertEqual(core.make_request_id_from_headers({'X-Request-Id': 'abc-123_:.XYZ'}), 'abc-123_:.XYZ')

    def test_request_id_rejects_bad_incoming(self):
        rid = core.make_request_id_from_headers({'X-Request-Id': 'bad value with space'})
        self.assertTrue(rid.startswith('req_'))
        self.assertEqual(len(rid), 28)

    def test_client_ip_xff_first(self):
        self.assertEqual(core.client_ip_from_headers({'X-Forwarded-For': '1.2.3.4, 5.6.7.8'}, '9.9.9.9'), '1.2.3.4')

    def test_extract_bearer_token(self):
        self.assertEqual(core.extract_bearer_token({'Authorization': 'Bearer sk-test'}), 'sk-test')
        self.assertEqual(core.extract_bearer_token({'Authorization': 'Basic abc'}), '')

    def test_model_from_json_body(self):
        self.assertEqual(core.model_from_json_body(b'{"model":"gpt-5.5"}', 'application/json'), 'gpt-5.5')
        self.assertEqual(core.model_from_json_body(b'bad', 'application/json'), '')
        self.assertEqual(core.model_from_json_body(b'{"model":"x"}', 'text/plain'), '')

    def test_normalize_request(self):
        req = core.normalize_request('POST', '/v1/chat/completions', {
            'Authorization': 'Bearer sk-test',
            'Content-Type': 'application/json',
            'X-Forwarded-For': '10.0.0.1',
            'X-Request-Id': 'rid-1',
        }, b'{"model":"gpt-5.4-mini"}', '127.0.0.1')
        self.assertEqual(req.api_key, 'sk-test')
        self.assertEqual(req.model, 'gpt-5.4-mini')
        self.assertEqual(req.client_ip, '10.0.0.1')
        self.assertEqual(req.request_id, 'rid-1')

    def test_build_model_list_payload_sorted(self):
        body = core.build_model_list_payload({'b', 'a'})
        data = json.loads(body.decode())
        self.assertEqual([m['id'] for m in data['data']], ['a', 'b'])

    def test_route_helpers(self):
        self.assertEqual(core.path_without_query('/v1/models?x=1'), '/v1/models')
        self.assertTrue(core.is_models_request('GET', '/v1/models?x=1'))
        self.assertTrue(core.is_models_request('HEAD', '/v1/models/'))
        self.assertFalse(core.is_models_request('POST', '/v1/models'))
        self.assertFalse(core.is_models_request('GET', '/v1/chat/completions'))
        self.assertEqual(core.build_upstream_url('http://127.0.0.1:18066/', '/v1/models'), 'http://127.0.0.1:18066/v1/models')

    def test_proxy_headers(self):
        headers = core.proxy_request_headers({'Host': 'x', 'Authorization': 'Bearer sk', 'Accept-Encoding': 'gzip'}, 'rid')
        self.assertNotIn('Host', headers)
        self.assertNotIn('Accept-Encoding', headers)
        self.assertEqual(headers['Authorization'], 'Bearer sk')
        self.assertEqual(headers['X-Request-Id'], 'rid')

    def test_chunk_helpers(self):
        self.assertTrue(core.should_chunk_downstream(None, 'GET'))
        self.assertFalse(core.should_chunk_downstream(3, 'GET'))
        self.assertFalse(core.should_chunk_downstream(None, 'HEAD'))
        self.assertEqual(core.encode_chunk(b'abc'), b'3\r\nabc\r\n')

    def test_policy_result_helpers(self):
        ok = core.PolicyResult.allow(user_id=1)
        self.assertTrue(ok.allowed)
        self.assertEqual(ok.context['user_id'], 1)
        bad = core.PolicyResult.deny('NOPE', 'blocked', 403, rule='x')
        self.assertFalse(bad.allowed)
        self.assertEqual(bad.error_code, 'NOPE')
        self.assertEqual(bad.error_message, 'blocked')
        self.assertEqual(bad.http_status, 403)
        self.assertEqual(bad.context['rule'], 'x')

    def test_ip_risk_policy(self):
        req = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.2.3.4', 'rid')
        self.assertTrue(core.IPRiskPolicy(lambda ip: (True, '')).evaluate(req).allowed)
        r = core.IPRiskPolicy(lambda ip: (False, '1.2.3.0/24')).evaluate(req)
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'IP_BLOCKED')
        self.assertEqual(r.http_status, 403)

    def test_auth_policy_paths(self):
        req_missing = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.1.1.1', 'rid')
        r = core.AuthPolicy(lambda key: {'ok': True}, lambda uid: {'id': 7}).evaluate(req_missing)
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'INVALID_API_KEY')
        self.assertEqual(r.http_status, 401)

        req = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.1.1.1', 'rid', api_key='sk-ok')
        r = core.AuthPolicy(lambda key: {'ok': True, 'user_id': 9, 'key_id': 3}, lambda uid: {'id': 7}).evaluate(req)
        self.assertTrue(r.allowed)
        self.assertEqual(r.context['sub2_uid'], 9)
        self.assertEqual(r.context['key_id'], 3)
        self.assertEqual(r.context['portal_user']['id'], 7)

        r = core.AuthPolicy(lambda key: {'ok': False, 'code': 'BAD', 'message': 'bad key'}, lambda uid: None).evaluate(req)
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'BAD')
        self.assertEqual(r.error_message, 'bad key')

        r = core.AuthPolicy(lambda key: {'ok': True, 'user_id': 9, 'key_id': 3}, lambda uid: None).evaluate(req)
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'ACCOUNT_DISABLED')

        def boom(key):
            raise RuntimeError('down')
        r = core.AuthPolicy(boom, lambda uid: {'id': 7}).evaluate(req)
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'INVALID_API_KEY')

    def test_model_allow_policy(self):
        req = core.NormalizedRequest('POST', '/v1/chat/completions', {}, b'', '1.1.1.1', 'rid', model='gpt-5.5')
        r = core.ModelAllowPolicy(lambda uid: {'gpt-5.5'}).evaluate(req, {'portal_user': {'id': 7}})
        self.assertTrue(r.allowed)
        r = core.ModelAllowPolicy(lambda uid: {'gpt-5.4'}).evaluate(req, {'portal_user': {'id': 7}})
        self.assertFalse(r.allowed)
        self.assertEqual(r.error_code, 'MODEL_NOT_ALLOWED')
        self.assertEqual(r.http_status, 403)
        empty = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.1.1.1', 'rid')
        self.assertTrue(core.ModelAllowPolicy(lambda uid: set()).evaluate(empty, {}).allowed)

    def test_policy_pipeline_allows_and_merges_context(self):
        req = core.NormalizedRequest('POST', '/v1/chat/completions', {}, b'', '1.1.1.1', 'rid', api_key='sk-ok', model='gpt-5.5')
        pipeline = core.PolicyPipeline([
            core.IPRiskPolicy(lambda ip: (True, '')),
            core.AuthPolicy(lambda key: {'ok': True, 'user_id': 9, 'key_id': 3}, lambda uid: {'id': 7}),
            core.ModelAllowPolicy(lambda uid: {'gpt-5.5'}),
        ])
        result = pipeline.run(req)
        self.assertTrue(result.allowed)
        self.assertEqual(result.context['sub2_uid'], 9)
        self.assertEqual(result.context['key_id'], 3)
        self.assertEqual(result.context['portal_user']['id'], 7)
        self.assertEqual(result.context['model'], 'gpt-5.5')

    def test_policy_pipeline_short_circuits(self):
        calls = []
        req = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.1.1.1', 'rid', api_key='sk-ok')

        class FirstDeny:
            def evaluate(self, req, ctx=None):
                calls.append('first')
                return core.PolicyResult.deny('DENIED', 'denied', 403, marker='x')

        class Second:
            def evaluate(self, req, ctx=None):
                calls.append('second')
                return core.PolicyResult.allow()

        result = core.PolicyPipeline([FirstDeny(), Second()]).run(req)
        self.assertFalse(result.allowed)
        self.assertEqual(result.error_code, 'DENIED')
        self.assertEqual(result.context['marker'], 'x')
        self.assertEqual(calls, ['first'])

    def test_policy_pipeline_uses_initial_context(self):
        req = core.NormalizedRequest('GET', '/v1/models', {}, b'', '1.1.1.1', 'rid')

        class NeedsContext:
            def evaluate(self, req, ctx=None):
                return core.PolicyResult.allow(extra=ctx['existing'] + '-ok')

        result = core.PolicyPipeline([NeedsContext()]).run(req, {'existing': 'seed'})
        self.assertTrue(result.allowed)
        self.assertEqual(result.context['existing'], 'seed')
        self.assertEqual(result.context['extra'], 'seed-ok')

    def test_normalize_request_without_body_keeps_auth_and_empty_model(self):
        req = core.normalize_request(
            'POST',
            '/v1/chat/completions',
            {'Authorization': 'Bearer sk-test', 'Content-Type': 'application/json', 'X-Forwarded-For': '1.2.3.4'},
            b'',
            '127.0.0.1',
        )
        self.assertEqual(req.api_key, 'sk-test')
        self.assertEqual(req.client_ip, '1.2.3.4')
        self.assertEqual(req.model, '')
        self.assertTrue(req.request_id.startswith('req_') or req.request_id)

    def test_access_log_record_defaults(self):
        rec = core.build_access_log_record()
        self.assertIsNone(rec.user_id)
        self.assertIsNone(rec.key_id)
        self.assertEqual(rec.ip, '')
        self.assertEqual(rec.method, '')
        self.assertEqual(rec.path, '')
        self.assertEqual(rec.model, '')
        self.assertEqual(rec.status, 0)
        self.assertEqual(rec.error_code, '')
        self.assertEqual(rec.latency_ms, 0)
        self.assertEqual(rec.request_id, '')

    def test_access_log_record_insert_values(self):
        rec = core.build_access_log_record(
            user_id=1, key_id=11, ip='127.0.0.1', method='POST',
            path='/v1/chat/completions', model='gpt-5.5', status=200,
            error_code='', latency_ms=12, request_id='req_test',
        )
        self.assertEqual(
            rec.insert_values(123456),
            (1, 11, '127.0.0.1', 'POST', '/v1/chat/completions', 'gpt-5.5', 200, '', 12, 123456, 'req_test'),
        )

    def test_access_log_record_normalizes_empty_values(self):
        rec = core.build_access_log_record(ip=None, method=None, path=None, model=None, error_code=None, status=None, latency_ms=None)
        self.assertEqual(rec.ip, '')
        self.assertEqual(rec.method, '')
        self.assertEqual(rec.path, '')
        self.assertEqual(rec.model, '')
        self.assertEqual(rec.error_code, '')
        self.assertEqual(rec.status, 0)
        self.assertEqual(rec.latency_ms, 0)

    def test_access_log_writer_protocol(self):
        calls = []

        class Writer:
            def write(self, record, created_at):
                calls.append((record, created_at))

        rec = core.build_access_log_record(status=401, error_code='INVALID_API_KEY', request_id='req_writer')
        core.write_access_log_record(Writer(), rec, 123)
        self.assertEqual(calls, [(rec, 123)])

    def test_upstream_http_error_code_mapping(self):
        cases = {
            429: 'UPSTREAM_RATE_LIMIT',
            502: 'UPSTREAM_UNAVAILABLE',
            503: 'UPSTREAM_UNAVAILABLE',
            504: 'UPSTREAM_UNAVAILABLE',
            400: 'UPSTREAM_HTTP_ERROR',
            403: 'UPSTREAM_HTTP_ERROR',
            500: 'UPSTREAM_HTTP_ERROR',
        }
        for status, code in cases.items():
            with self.subTest(status=status):
                self.assertEqual(core.upstream_http_error_code(status), code)


if __name__ == '__main__':
    unittest.main(verbosity=2)
