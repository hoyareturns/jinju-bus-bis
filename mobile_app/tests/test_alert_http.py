import json
import threading
import unittest
from http.client import HTTPConnection
from mobile_app.server import Config, create_server

class FakeAlerts:
    def config(self): return {'available':True,'publicKey':'public','reason':''}
    def create_client(self): return 'new-token'
    def get(self, token):
        if token != 'owned': raise PermissionError()
        return {'alarms':[]}
    def save(self, token, payload):
        self.get(token)
        return {'id':'a','rule':payload['rule']}
    def delete(self, token, ident):
        self.get(token)
        return {'deleted':True}

class AlertHttpTests(unittest.TestCase):
    def setUp(self):
        self.server=create_server(Config(),port=0,alert_manager=FakeAlerts())
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.origin=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,path,method='GET',body=None,headers=None):
        c=HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        c.request(method,'/apps/bus/'+path,body=body,headers=headers or {})
        r=c.getresponse();result=(r.status,json.loads(r.read()));c.close();return result
    def test_read_config_and_owned_alarms(self):
        self.assertTrue(self.request('api/push/config')[1]['available'])
        self.assertEqual(self.request('api/alerts')[0],401)
        self.assertEqual(self.request('api/alerts',headers={'Authorization':'Bearer owned'})[0],200)
    def test_mutations_require_same_origin_and_json(self):
        self.assertEqual(self.request('api/alerts/session','POST','{}',{'Origin':'https://evil.test','Content-Type':'application/json'})[0],403)
        self.assertEqual(self.request('api/alerts/session','POST','{}',{'Origin':self.origin,'Content-Type':'text/plain'})[0],400)
        self.assertEqual(self.request('api/alerts/session','POST','{}',{'Origin':self.origin,'Content-Type':'application/json'})[0],201)
    def test_save_delete_ownership_and_payload(self):
        h={'Origin':self.origin,'Content-Type':'application/json','Authorization':'Bearer owned'}
        self.assertEqual(self.request('api/alerts','POST','{"rule":{}}',h)[0],200)
        self.assertEqual(self.request('api/alerts/a','DELETE',headers=h)[0],200)
        h['Authorization']='Bearer wrong'
        self.assertEqual(self.request('api/alerts/a','DELETE',headers=h)[0],401)
        self.assertEqual(self.request('api/alerts','POST','[1]',h)[0],400)
    def test_public_origin_validation(self):
        for value in ['http://example.com','https://example.com/path','https://user@example.com']:
            with self.assertRaises(ValueError): Config(public_origin=value)
        self.assertEqual(Config(public_origin='https://bus.example.com').public_origin,'https://bus.example.com')
