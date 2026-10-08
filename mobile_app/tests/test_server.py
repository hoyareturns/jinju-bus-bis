import json
import threading
import unittest
from types import SimpleNamespace
from http.client import HTTPConnection

from mobile_app.server import Config, create_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(Config(base_path='/apps/bus/', hub_path='../../'), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, headers=None, method='GET'):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        status, headers, body = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, headers, body

    def test_mount_redirect_and_unrelated_paths(self):
        self.assertEqual(self.get('/apps/bus')[1]['Location'], '/apps/bus/')
        self.assertEqual(self.get('/')[0], 404)
        self.assertEqual(self.get('/apps/bus/')[0], 200)
        self.assertEqual(self.get('/apps/bus/api/bootstrap')[0], 200)

    def test_config_and_auth_are_truthful(self):
        status, _, body = self.get('/apps/bus/api/bootstrap', {'X-User-Id': 'admin'})
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data['defaultBuses'], ['10'])
        self.assertEqual(data['basePath'], '/apps/bus/')
        self.assertEqual(data['hubPath'], '../../')
        self.assertEqual(data['storageMode'], 'device')
        self.assertFalse(data['apiConfigured'])
        self.assertEqual(self.get('/apps/bus/api/account/preferences')[0], 404)

    def test_missing_key_is_not_live_success_and_empty_selection_is_valid(self):
        self.assertEqual(self.get('/apps/bus/api/v2/locations?buses=10')[0], 503)
        status, _, body = self.get('/apps/bus/api/v2/locations?buses=')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['routes'], [])

    def test_browser_cancellation_on_windows_is_a_normal_disconnect(self):
        handler = object.__new__(self.server.RequestHandlerClass)
        handler.command = 'GET'
        handler.send_response = lambda *args: None
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        def aborted(_):
            raise ConnectionAbortedError('Browser canceled its request')
        handler.wfile = SimpleNamespace(write=aborted)
        handler.respond(200, {'routes': []})

    def test_bad_inputs_and_traversal_do_not_expose_files(self):
        for path in ['../.git/config', '%2e%2e/.git/config', '%5c..%5c.git/config', 'server.py']:
            self.assertEqual(self.get('/apps/bus/' + path)[0], 404)
        for query in ['buses=%3Cscript%3E', 'buses=' + ','.join(str(i) for i in range(11))]:
            self.assertEqual(self.get('/apps/bus/api/v2/locations?' + query)[0], 400)

    def test_worker_scope_and_api_cache_policy(self):
        status, headers, _ = self.get('/apps/bus/sw.js')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Service-Worker-Allowed'], '/apps/bus/')
        self.assertEqual(self.get('/apps/bus/api/health')[1]['Cache-Control'], 'no-store')

    def test_hub_and_install_manifests_point_to_real_scoped_assets(self):
        status, _, body = self.get('/apps/bus/app-manifest.json')
        self.assertEqual(status, 200)
        manifest = json.loads(body)
        self.assertEqual(manifest['launchPath'], '/apps/bus/')
        self.assertFalse(manifest['demoData'])
        for field in ('banner', 'icon', 'healthPath'):
            self.assertEqual(self.get(manifest[field])[0], 200)
        status, _, body = self.get('/apps/bus/manifest.webmanifest')
        self.assertEqual(status, 200)
        pwa = json.loads(body)
        self.assertEqual(pwa['scope'], '/apps/bus/')
        self.assertEqual(self.get(pwa['icons'][0]['src'])[0], 200)

    def test_root_mount_and_configuration_validation(self):
        self.assertEqual(Config(base_path='/').base_path, '/')
        self.assertEqual(Config(base_path='/tools/bus').base_path, '/tools/bus/')
        for base in ['//evil/', '/a/../', '/a?b', '/a\\b']:
            with self.assertRaises(ValueError):
                Config(base_path=base)
        for hub in ['https://evil.test', '//evil.test', 'javascript:alert(1)', '\\evil']:
            with self.assertRaises(ValueError):
                Config(hub_path=hub)

    def test_manifests_and_bootstrap_follow_custom_and_root_mounts(self):
        for base in ['/', '/tools/transport/']:
            server = create_server(Config(base_path=base), port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                for name in ['api/bootstrap', 'manifest.webmanifest', 'app-manifest.json', 'sw.js']:
                    conn.request('GET', base + name)
                    response = conn.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200)
                    if name == 'manifest.webmanifest':
                        self.assertEqual(json.loads(body)['scope'], base)
                    elif name == 'app-manifest.json':
                        self.assertEqual(json.loads(body)['banner'], base + 'assets/banner.svg')
                    elif name == 'api/bootstrap':
                        self.assertEqual(json.loads(body)['basePath'], base)
                    else:
                        self.assertEqual(response.getheader('Service-Worker-Allowed'), base)
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
