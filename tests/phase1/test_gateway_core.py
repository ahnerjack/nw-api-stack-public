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


if __name__ == '__main__':
    unittest.main(verbosity=2)
