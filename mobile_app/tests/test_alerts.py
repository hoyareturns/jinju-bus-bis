import base64
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import json
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from mobile_app.alerts import AlertManager
from mobile_app.tago import TagoError


def encoded(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def moment(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


class Service:
    def __init__(self):
        self.now = moment('2026-10-08T08:40:00+09:00')
        self.route_rows = [{'busNo': '10', 'routeId': 'forward', 'directionLabel': '종점 방면',
            'source': 'tago', 'stale': False, 'stops': [
                {'nodeId': 'stop-5', 'nodeOrd': 5, 'name': '시청', 'lat': None, 'lon': None}]}]
        self.live_rows = [{'busNo': '10', 'routeId': 'forward', 'status': 'ok', 'stale': False,
            'updatedAt': self.now.isoformat(), 'vehicles': [
                {'nodeOrd': 5, 'nodeId': 'stop-5', 'id': 'vehicle', 'lat': None, 'lon': None}]}]
        self.busy = False
        self.requested = []

    def routes(self, buses):
        self.requested.append(buses)
        return {'routes': deepcopy(self.route_rows), 'errors': []}

    def locations(self, buses):
        self.requested.append(buses)
        if self.busy:
            raise TagoError('BUSY', 'private error')
        return {'routes': deepcopy(self.live_rows), 'errors': []}


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'alerts.db'
        self.service = Service()
        self.sent = []
        self.manager = self.make_manager()
        self.token = self.manager.create_client()

    def make_manager(self, sender=None):
        manager = AlertManager(self.path, self.service, sender=sender or (lambda **data: self.sent.append(data)))
        self.addCleanup(manager.stop)
        return manager

    def payload(self):
        return {'registeredBuses': ['10'], 'subscription': {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test',
            'keys': {'auth': encoded(b'a' * 16), 'p256dh': encoded(b'\x04' + b'b' * 64)}},
            'rule': {'busNo': '10', 'directionLabel': '종점 방면', 'stopName': '시청',
                'targets': [{'routeId': 'forward', 'nodeOrd': 5, 'nodeId': 'stop-5'}],
                'startTime': '08:30', 'endTime': '09:00', 'days': list(range(7)),
                'timezone': 'Asia/Seoul'}}

    def tick(self, when):
        now = moment(when)
        for route in self.service.live_rows:
            route['updatedAt'] = now.isoformat()
        self.manager.tick(now)

    def test_send_without_browser_and_short_ttl(self):
        saved = self.manager.save(self.token, self.payload())
        self.tick('2026-10-08T08:40:00+09:00')
        self.assertEqual(len(self.sent), 1)
        self.assertLessEqual(self.sent[0]['ttl'], 60)
        data = json.loads(self.sent[0]['data'])
        self.assertEqual(data['url'], '/apps/bus/')
        self.assertIn('시청', data['body'])
        alarm = self.manager.get(self.token)['alarms'][0]
        self.assertEqual(alarm['id'], saved['id'])
        self.assertEqual(alarm['deliveryStatus'], 'sent')
        self.assertIsNotNone(alarm['lastSentAt'])

    def test_window_start_included_end_excluded_and_daily_reset(self):
        self.manager.save(self.token, self.payload())
        for when, count in [('2026-10-08T08:29:59+09:00', 0),
                            ('2026-10-08T08:30:00+09:00', 1),
                            ('2026-10-08T08:59:59+09:00', 1),
                            ('2026-10-09T09:00:00+09:00', 1),
                            ('2026-10-10T08:30:00+09:00', 2)]:
            self.tick(when)
            self.assertEqual(len(self.sent), count, when)

    def test_weekdays_and_overnight_use_starting_day(self):
        payload = self.payload()
        payload['rule'].update(startTime='23:30', endTime='00:30', days=[4])
        self.manager.save(self.token, payload)
        for when, count in [('2026-10-09T00:10:00+09:00', 0),
                            ('2026-10-10T00:10:00+09:00', 1),
                            ('2026-10-10T00:30:00+09:00', 1),
                            ('2026-10-11T00:10:00+09:00', 1)]:
            self.tick(when)
            self.assertEqual(len(self.sent), count, when)

    def test_stale_wrong_route_wrong_stop_and_old_observation_are_ignored(self):
        self.manager.save(self.token, self.payload())
        baseline = deepcopy(self.service.live_rows)
        changes = [{'stale': True}, {'status': 'error'}, {'routeId': 'reverse'},
                   {'updatedAt': '2026-10-07T23:38:00+00:00'},
                   {'updatedAt': '2026-10-08T23:40:00+00:00'},
                   {'vehicles': [{'nodeOrd': 6, 'nodeId': 'stop-5'}]},
                   {'vehicles': [{'nodeOrd': 5, 'nodeId': 'other-side'}]}]
        for change in changes:
            self.service.live_rows = deepcopy(baseline)
            self.service.live_rows[0].update(change)
            self.manager.tick(self.service.now)
            self.assertEqual(self.sent, [], change)

    def test_dedup_survives_restart_and_rule_resave(self):
        payload = self.payload()
        saved = self.manager.save(self.token, payload)
        self.tick('2026-10-08T08:40:00+09:00')
        self.manager.stop()
        self.manager = self.make_manager()
        payload['id'] = saved['id']
        self.manager.save(self.token, payload)
        self.tick('2026-10-08T08:41:00+09:00')
        self.assertEqual(len(self.sent), 1)

    def test_multiple_alarms_deliver_independently_and_delete_one(self):
        first = self.manager.save(self.token, self.payload())
        second = self.manager.save(self.token, self.payload())
        self.assertNotEqual(first['id'], second['id'])
        self.tick('2026-10-08T08:40:00+09:00')
        self.assertEqual(len(self.sent), 2)
        self.manager.delete(self.token, first['id'])
        self.assertEqual([row['id'] for row in self.manager.get(self.token)['alarms']], [second['id']])

    def test_tokens_and_alarm_ownership_are_enforced_and_tokens_hashed(self):
        saved = self.manager.save(self.token, self.payload())
        other = self.manager.create_client()
        self.assertEqual(self.manager.get(other)['alarms'], [])
        for token in ['', 'unknown', 'x' * 1000]:
            with self.assertRaises(PermissionError):
                self.manager.get(token)
        payload = self.payload()
        payload['id'] = saved['id']
        with self.assertRaises(PermissionError):
            self.manager.save(other, payload)
        with self.assertRaises(PermissionError):
            self.manager.delete(other, saved['id'])
        with closing(sqlite3.connect(self.path)) as db:
            dump = '\n'.join(db.iterdump())
        self.assertNotIn(self.token, dump)

    def test_rejects_unregistered_bus_wrong_stop_and_untrusted_routes(self):
        for change in ['bus', 'route', 'order', 'id', 'name', 'stale']:
            payload = self.payload()
            if change == 'bus': payload['registeredBuses'] = ['11']
            if change == 'route': payload['rule']['targets'][0]['routeId'] = 'attacker-route'
            if change == 'order': payload['rule']['targets'][0]['nodeOrd'] = 6
            if change == 'id': payload['rule']['targets'][0]['nodeId'] = 'other-side'
            if change == 'name': payload['rule']['stopName'] = 'other'
            if change == 'stale': self.service.route_rows[0]['stale'] = True
            with self.assertRaises(ValueError, msg=change):
                self.manager.save(self.token, payload)
        self.assertTrue(all(buses == ['10'] for buses in self.service.requested))

    def test_subscription_blocks_ssrf_and_invalid_keys(self):
        for endpoint in ['http://fcm.googleapis.com/push', 'https://127.0.0.1/a',
                         'https://fcm.googleapis.com.evil.test/a', 'https://user@fcm.googleapis.com/a',
                         'https://fcm.googleapis.com:8443/a', 'https://example.com/a']:
            payload = self.payload()
            payload['subscription']['endpoint'] = endpoint
            with self.assertRaises(ValueError, msg=endpoint):
                self.manager.save(self.token, payload)
        for key in ['auth', 'p256dh']:
            payload = self.payload()
            payload['subscription']['keys'][key] = 'bad'
            with self.assertRaises(ValueError):
                self.manager.save(self.token, payload)

    def test_cannot_mix_opposite_road_stops_with_identical_names(self):
        reverse = deepcopy(self.service.route_rows[0])
        reverse['routeId'] = 'reverse'
        reverse['stops'][0]['nodeId'] = 'other-side'
        self.service.route_rows.append(reverse)
        payload = self.payload()
        payload['rule']['targets'].append({'routeId': 'reverse', 'nodeOrd': 5, 'nodeId': 'other-side'})
        with self.assertRaises(ValueError):
            self.manager.save(self.token, payload)

    def test_invalid_schedules_and_limits(self):
        for change in [{'days': []}, {'days': [7]}, {'days': [True]},
                       {'startTime': '9:00'}, {'endTime': '24:00'},
                       {'startTime': '09:00'}, {'timezone': 'UTC'}, {'targets': []}]:
            payload = self.payload()
            payload['rule'].update(change)
            with self.assertRaises(ValueError, msg=change):
                self.manager.save(self.token, payload)
        for _ in range(20):
            self.manager.save(self.token, self.payload())
        with self.assertRaises(ValueError):
            self.manager.save(self.token, self.payload())

    def test_busy_does_not_send_then_recovers(self):
        self.manager.save(self.token, self.payload())
        self.service.busy = True
        self.tick('2026-10-08T08:40:00+09:00')
        self.assertEqual(self.sent, [])
        self.service.busy = False
        self.tick('2026-10-08T08:40:15+09:00')
        self.assertEqual(len(self.sent), 1)

    def test_send_failure_is_explicit_and_not_retried_repeatedly(self):
        def broken(**_):
            raise RuntimeError('secret-key-and-private-endpoint')
        self.manager = self.make_manager(broken)
        self.manager.save(self.token, self.payload())
        self.tick('2026-10-08T08:40:00+09:00')
        state = self.manager.get(self.token)['alarms'][0]
        self.assertEqual(state['deliveryStatus'], 'failed')
        self.assertNotIn('secret', json.dumps(state))
        self.manager = self.make_manager()
        self.tick('2026-10-08T08:41:00+09:00')
        self.assertEqual(self.sent, [])

    def test_expired_subscription_disables_all_its_alarms(self):
        class Gone(Exception):
            response = type('Response', (), {'status_code': 410})()
        def gone(**_): raise Gone()
        self.manager = self.make_manager(gone)
        self.manager.save(self.token, self.payload())
        self.manager.save(self.token, self.payload())
        self.tick('2026-10-08T08:40:00+09:00')
        self.assertTrue(all(row['deliveryStatus'] == 'subscription_expired'
                            for row in self.manager.get(self.token)['alarms']))

    def test_without_push_configuration_reports_unavailable(self):
        manager = AlertManager(Path(self.folder.name) / 'disabled.db', self.service)
        self.addCleanup(manager.stop)
        self.assertFalse(manager.config()['available'])
        self.assertEqual(manager.config()['publicKey'], '')

    def test_worker_runs_independently_and_only_one_worker_owns_database(self):
        delivered = threading.Event()
        def sender(**data):
            self.sent.append(data)
            delivered.set()
        self.manager = self.make_manager(sender)
        self.manager.save(self.token, self.payload())
        service_now = self.service.now
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return service_now
        with patch('mobile_app.alerts.datetime', Clock):
            self.manager.start()
            self.assertTrue(delivered.wait(3), 'Background worker did not deliver')
            contender = self.make_manager()
            with self.assertRaises(RuntimeError):
                contender.start()
            self.manager.stop()
            contender.start()
            contender.stop()
        self.assertEqual(len(self.sent), 1)

    def test_expiry_never_extends_past_active_window(self):
        self.manager.save(self.token, self.payload())
        self.tick('2026-10-08T08:59:45+09:00')
        self.assertLessEqual(self.sent[0]['ttl'], 15)
        self.assertEqual(json.loads(self.sent[0]['data'])['expiresAt'], '2026-10-08T00:00:00+00:00')

    def test_route_lookup_that_outlasts_window_does_not_send(self):
        self.manager.save(self.token, self.payload())
        with patch('mobile_app.alerts.time.monotonic', side_effect=[0, 31]):
            self.tick('2026-10-08T08:59:30+09:00')
        self.assertEqual(self.sent, [])

    def test_key_cli_writes_private_file_without_printing_or_overwriting_keys(self):
        path = Path(self.folder.name) / '.env.vapid'
        command = [sys.executable, '-m', 'mobile_app.push_keys', '--output', str(path)]
        created = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertEqual(created.stdout.strip(), str(path.resolve()))
        contents = path.read_text(encoding='utf-8')
        values = dict(line.split('=', 1) for line in contents.splitlines() if '=' in line)
        self.assertEqual(len(base64.urlsafe_b64decode(values['VAPID_PRIVATE_KEY'] + '=')), 32)
        self.assertEqual(len(base64.urlsafe_b64decode(values['VAPID_PUBLIC_KEY'] + '=')), 65)
        self.assertNotIn(values['VAPID_PRIVATE_KEY'], created.stdout + created.stderr)
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(path.read_text(encoding='utf-8'), contents)

    def test_slow_location_lookup_does_not_block_list_or_delete_or_send_deleted_alarm(self):
        saved = self.manager.save(self.token, self.payload())
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        errors = []
        original = self.service.locations
        def slow(buses):
            entered.set()
            release.wait(4)
            return original(buses)
        self.service.locations = slow
        worker = threading.Thread(target=lambda: self.manager.tick(self.service.now))
        def manage():
            try:
                self.manager.get(self.token)
                self.manager.delete(self.token, saved['id'])
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()
        worker.start()
        self.assertTrue(entered.wait(2))
        request = threading.Thread(target=manage)
        request.start()
        try:
            self.assertTrue(finished.wait(0.5), 'List/delete blocked on upstream lookup')
        finally:
            release.set()
            worker.join(3)
            request.join(3)
        self.assertEqual(errors, [])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.manager.get(self.token)['alarms'], [])

    def test_slow_send_does_not_block_other_alarm_and_delete_waits_for_own_send(self):
        entered, release = threading.Event(), threading.Event()
        deleted, other_done = threading.Event(), threading.Event()
        errors = []
        def send(**data):
            entered.set()
            release.wait(4)
            self.sent.append(data)
        self.manager = self.make_manager(send)
        first = self.manager.save(self.token, self.payload())
        second = self.manager.save(self.token, self.payload())
        worker = threading.Thread(target=lambda: self.manager.tick(self.service.now))
        def remove(alarm_id, event):
            try:
                self.manager.get(self.token)
                self.manager.delete(self.token, alarm_id)
            except Exception as error:
                errors.append(error)
            finally:
                event.set()
        worker.start()
        self.assertTrue(entered.wait(2))
        same_request = threading.Thread(target=remove, args=(first['id'], deleted))
        other_request = threading.Thread(target=remove, args=(second['id'], other_done))
        same_request.start()
        other_request.start()
        try:
            self.assertTrue(other_done.wait(0.5), 'Unrelated alarm blocked by sender')
            self.assertFalse(deleted.is_set(), 'Deletion acknowledged before its in-flight send finished')
        finally:
            release.set()
            worker.join(3)
            same_request.join(3)
            other_request.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(deleted.is_set())
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.manager.get(self.token)['alarms'], [])

    def test_slow_rule_validation_does_not_block_delete_or_recreate_deleted_alarm(self):
        saved = self.manager.save(self.token, self.payload())
        entered, release, deleted = threading.Event(), threading.Event(), threading.Event()
        errors = []
        original = self.service.routes
        def slow(buses):
            entered.set()
            release.wait(4)
            return original(buses)
        self.service.routes = slow
        payload = self.payload()
        payload['id'] = saved['id']
        def save():
            try:
                self.manager.save(self.token, payload)
            except Exception as error:
                errors.append(error)
        def remove():
            self.manager.delete(self.token, saved['id'])
            deleted.set()
        saving = threading.Thread(target=save)
        saving.start()
        self.assertTrue(entered.wait(2))
        deleting = threading.Thread(target=remove)
        deleting.start()
        try:
            self.assertTrue(deleted.wait(0.5), 'Deletion blocked by route validation')
        finally:
            release.set()
            saving.join(3)
            deleting.join(3)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PermissionError)
        self.assertEqual(self.manager.get(self.token)['alarms'], [])

    @unittest.skipUnless(importlib.util.find_spec('pywebpush'), 'Requires mobile_app/requirements.txt')
    def test_real_push_library_encrypts_and_disallows_redirects_without_network(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        private = ec.generate_private_key(ec.SECP256R1())
        public = private.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        manager = AlertManager(self.path, self.service, public_key=encoded(public),
            private_key=encoded(private.private_numbers().private_value.to_bytes(32, 'big')),
            subject='mailto:operator@example.com')
        self.addCleanup(manager.stop)
        self.assertTrue(manager.config()['available'])
        payload = self.payload()
        payload['subscription']['keys']['p256dh'] = encoded(public)
        manager.save(self.token, payload)
        import requests
        response = requests.Response()
        response.status_code = 201
        response._content = b''
        # Block OS socket connections in addition to replacing requests' final
        # transport: this test cannot send a real push even if its adapter changes.
        with patch('socket.socket.connect', side_effect=AssertionError('Network disabled')), \
             patch('socket.create_connection', side_effect=AssertionError('Network disabled')), \
             patch('requests.Session.send', return_value=response) as transport:
            manager.tick(self.service.now)
        self.assertEqual(manager.get(self.token)['alarms'][0]['deliveryStatus'], 'sent')
        self.assertEqual(transport.call_count, 1)
        self.assertFalse(transport.call_args.kwargs['allow_redirects'])
        request = transport.call_args.args[0]
        self.assertTrue(request.body)
        self.assertNotIn('시청'.encode(), request.body)
        self.assertLessEqual(int(request.headers['ttl']), 60)


if __name__ == '__main__':
    unittest.main()
