import http.client
import json
import threading
import unittest
from campura_vision.samples import example
from campura_vision.server import LocalServer


class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, method='GET', body=None, headers=None, authorized=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        fields = {'X-Campura-Token': self.server.token} if authorized else {}
        fields.update(headers or {})
        connection.request(method, path, body=body, headers=fields)
        response = connection.getresponse()
        status, metadata, payload = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, metadata, payload

    def test_ui_has_no_external_assets_or_token(self):
        status, headers, body = self.request('/', authorized=False)
        self.assertEqual(status, 200)
        self.assertNotIn(self.server.token.encode(), body)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        for asset in ('/app.js', '/style.css'):
            self.assertEqual(self.request(asset)[0], 200)

    def test_health_requires_session(self):
        self.assertEqual(self.request('/api/health', authorized=False)[0], 401)
        self.assertEqual(self.request('/api/health', headers={'X-Campura-Token': 'wrong'})[0], 401)
        self.assertEqual(self.request('/api/health', headers={'X-Campura-Token': 'é'})[0], 401)
        status, _, body = self.request('/api/health')
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)['cloud_enabled'])

    def test_foreign_origins_and_hosts_rejected(self):
        self.assertEqual(self.request('/api/health', headers={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/', headers={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request('/api/health', headers={'Origin': self.server.origin})[0], 200)

    def test_estimate_roundtrip(self):
        data = example('dining')
        data['capacity']['variation'] = 0
        status, _, body = self.request('/api/estimate', 'POST', json.dumps(data), {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['preorder']['minutes'], [13.5, 13.5])

    def test_invalid_inputs_fail_with_clear_status(self):
        self.assertEqual(self.request('/api/estimate', 'POST', '{}')[0], 415)
        headers = {'Content-Type': 'application/json'}
        for raw in ('not json', '{}', '[]', 'null', '[' * 2000):
            with self.subTest(raw=raw[:20]):
                self.assertEqual(self.request('/api/estimate', 'POST', raw, headers)[0], 400)
        headers['Content-Length'] = '512001'
        self.assertEqual(self.request('/api/estimate', 'POST', '', headers)[0], 413)

    def test_examples_are_fresh_and_named(self):
        self.assertEqual(self.request('/api/example?name=unknown')[0], 400)
        status, _, body = self.request('/api/example?name=retail')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['kind'], 'retail')

    def test_no_file_traversal(self):
        self.assertEqual(self.request('/../README.md')[0], 404)
        self.assertEqual(self.request('/%2e%2e/README.md')[0], 404)


if __name__ == '__main__':
    unittest.main()
